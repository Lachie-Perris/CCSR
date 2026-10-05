"""Fetch published BOM high/low predictions for the existing regional proxy."""
from html.parser import HTMLParser
import re

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from surf_forecast import ROOT, TZ, atomic_json, utc, validate_tide_events

STATION = 'NSW_TP004'
ENDPOINT = 'https://reg.bom.gov.au/australia/tides/scripts/getTidesTable.php'


class TideTableParser(HTMLParser):
    """Pair each explicitly timestamped event with its following metre height."""
    def __init__(self):
        super().__init__()
        self.events = []
        self.pending = None
        self.height_text = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != 'td':
            return
        if 'data-time-utc' in attrs:
            if self.pending is not None:
                raise ValueError('BOM event is missing its height')
            stamp = pd.Timestamp(attrs['data-time-utc'])
            local = pd.Timestamp(attrs['data-time-local'])
            if stamp.tzinfo is None or local.tzinfo is None or stamp != local:
                raise ValueError('BOM UTC and local timestamps disagree')
            self.pending = (stamp.tz_convert('UTC'), local.isoformat())
        if 'height' in attrs.get('class', '').split():
            self.height_text = ''

    def handle_data(self, text):
        if self.height_text is not None:
            self.height_text += text

    def handle_endtag(self, tag):
        if tag == 'td' and self.height_text is not None:
            if self.pending is not None:
                match = re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s+m\s*', self.height_text)
                if not match:
                    raise ValueError('BOM height is missing or not in metres')
                self.events.append((*self.pending, float(match[1])))
                self.pending = None
            self.height_text = None


def parse_predictions(html, start, end):
    parser = TideTableParser()
    parser.feed(html)
    if parser.pending is not None or not parser.events:
        raise ValueError('BOM returned an empty or incomplete prediction table')
    events = pd.DataFrame(parser.events, columns=['time_utc', 'time_local', 'height_m'])
    events = validate_tide_events(events.set_index('time_utc').sort_index())
    if events.index.min() > utc(start) or events.index.max() < utc(end):
        raise ValueError('Fresh BOM predictions do not bracket the requested weekend')
    return events


def fetch_tide_events(start, end, output=ROOT / 'output/bom_tides.csv'):
    """Fetch anew on every live run; never silently reuse an expired snapshot."""
    first = utc(start).tz_convert(TZ).normalize() - pd.DateOffset(days=1)
    params = {'type': 'tide', 'aac': STATION, 'date': first.strftime('%d-%m-%Y'),
              'days': 7, 'region': 'NSW', 'tz': 'Australia/Sydney', 'tz_js': 'Australia/Sydney'}
    with requests.Session() as session:
        session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
        tables, urls = [], []
        cursor = first
        while cursor <= utc(end).tz_convert(TZ).normalize() + pd.DateOffset(days=1):
            params['date'] = cursor.strftime('%d-%m-%Y')
            response = session.get(ENDPOINT, params=params, timeout=45)
            response.raise_for_status()
            tables.append(response.text)
            urls.append(response.url)
            cursor += pd.DateOffset(days=7)
    events = parse_predictions(''.join(tables), start, end)
    events.attrs = {'station': STATION, 'source_urls': urls, 'datum': 'LAT',
                    'retrieved_at_utc': pd.Timestamp.now(tz='UTC').isoformat(),
                    'curve': 'Local half-cosine interpolation of BOM high/low predictions'}
    if output is not None:
        from pathlib import Path
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        events[['time_local', 'height_m']].to_csv(output, index=False)
        atomic_json(output.with_suffix('.json'), events.attrs)
    print(f'Fresh BOM tides: {STATION}, {len(events)} events; '
          f'{events.index.min().isoformat()} to {events.index.max().isoformat()}')
    return events
