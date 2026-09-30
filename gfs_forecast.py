"""GFS Wave 0.25 degree forecast adapter using Open-Meteo's public API."""
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
import requests

from surf_forecast import ROOT, TARGET, transform_waves, utc

MARINE_URL = 'https://marine-api.open-meteo.com/v1/marine'
WIND_URL = 'https://api.open-meteo.com/v1/forecast'
MARINE_VARIABLES = ','.join([
    'wave_height', 'wave_direction', 'wave_period',
    'swell_wave_height', 'swell_wave_direction', 'swell_wave_period',
    'secondary_swell_wave_height', 'secondary_swell_wave_direction',
    'secondary_swell_wave_period',
])


def _get(url, params):
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if 'hourly' not in payload:
        raise ValueError(f'GFS API returned no hourly data: {payload}')
    return payload


def _series(payload, key, index):
    values = payload['hourly'].get(key)
    if values is None:
        return pd.Series(np.nan, index=index, dtype=float)
    return pd.Series(values, index=pd.to_datetime(payload['hourly']['time'], utc=True), dtype=float).reindex(index)


def _offshore_location():
    """Use the one-time locked offshore point for both model requests."""
    lock = ROOT / 'config/offshore_grid.json'
    if lock.exists():
        saved = json.loads(lock.read_text(encoding='utf-8'))
        return float(saved['latitude']), float(saved['longitude'])
    return TARGET


def fetch_gfs_forecast(start=None, horizon_hours=48):
    """Return the same normalized columns as the ECMWF adapter plus swell partitions."""
    start = utc(pd.Timestamp.now(tz='UTC') if start is None else start).ceil('3h')
    end = start + pd.Timedelta(hours=horizon_hours)
    latitude, longitude = _offshore_location()
    # Explicit dates cover the inclusive endpoint even when start rounds to midnight.
    window = {'start_date': start.strftime('%Y-%m-%d'), 'end_date': end.strftime('%Y-%m-%d')}
    base = {'latitude': latitude, 'longitude': longitude, **window,
            # Open-Meteo's current model identifier for the global 0.25° GFS wave run.
            # (The older ``gfs_wave_025`` alias now returns HTTP 400.)
            'models': 'ncep_gfswave025', 'timezone': 'GMT', 'cell_selection': 'sea',
            'hourly': MARINE_VARIABLES}
    marine = _get(MARINE_URL, base)
    wind = _get(WIND_URL, {'latitude': latitude, 'longitude': longitude, **window,
                           'models': 'gfs_global', 'cell_selection': 'nearest',
                           'timezone': 'GMT', 'hourly': 'wind_speed_10m,wind_direction_10m'})
    index = pd.date_range(start, end, freq='3h', tz='UTC', name='time_utc')
    frame = pd.DataFrame(index=index)
    frame['offshore_height_m'] = _series(marine, 'wave_height', index)
    frame['wave_direction_deg'] = _series(marine, 'wave_direction', index)
    # GFS wave_period maps to NOAA PERPW (peak period); wave_peak_period is null.
    # Source: open-meteo/Sources/App/Gfs/GfsWaveVariable.swift, gribIndexName.
    frame['peak_period_s'] = _series(marine, 'wave_period', index)
    frame['wind_speed_kn'] = _series(wind, 'wind_speed_10m', index) * 0.5399568
    frame['wind_direction_deg'] = _series(wind, 'wind_direction_10m', index)
    for prefix, name in [('swell_wave', 'primary_swell'), ('secondary_swell_wave', 'secondary_swell')]:
        frame[f'{name}_height_m'] = _series(marine, f'{prefix}_height', index)
        frame[f'{name}_direction_deg'] = _series(marine, f'{prefix}_direction', index)
        frame[f'{name}_period_s'] = _series(marine, f'{prefix}_period', index)
    required = ['offshore_height_m', 'wave_direction_deg', 'peak_period_s', 'wind_speed_kn', 'wind_direction_deg']
    if frame[required].isna().any().any():
        missing = {column: int(frame[column].isna().sum()) for column in required}
        raise ValueError(f'GFS forecast returned missing core wave or wind values: {missing}')
    frame = transform_waves(frame)
    frame.attrs = {'run_utc': datetime.now(timezone.utc).isoformat(), 'source': 'GFS Wave 0.25 via Open-Meteo',
                   'grid': {'latitude': float(marine.get('latitude', TARGET[0])),
                            'longitude': float(marine.get('longitude', TARGET[1]))},
                   'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
    return frame


def has_swell_partitions(frame):
    columns = ['primary_swell_height_m', 'primary_swell_period_s', 'primary_swell_direction_deg',
               'secondary_swell_height_m', 'secondary_swell_period_s', 'secondary_swell_direction_deg']
    return all(c in frame and frame[c].notna().any() for c in columns)
