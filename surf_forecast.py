"""ECMWF point forecasts, fixed wave transfer, BOM tides and one five-day figure."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo

import eccodes as ec
from ecmwf.opendata import Client
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TARGET = (-33.281989967844346, 151.58462413473455)
GRID_FILE = ROOT / 'config/offshore_grid.json'
TZ = ZoneInfo('Australia/Sydney')
FEET_PER_METRE = 1 / 0.3048
# Exact legacy lookup: nearest 15 degrees, half-up integer periods, then lookup.
PERIOD_COLUMNS = {24: 0, 23: 1, 22: 1, 21: 2, 20: 2, 19: 3, 18: 3,
                  17: 4, 16: 4, 15: 5, 14: 6, 13: 7, 12: 7, 11: 8,
                  10: 9, 9: 10, 8: 11, 7: 13, 6: 15, 5: 16, 4: 17}
GRID_KEYS = ('gridType', 'Ni', 'Nj', 'latitudeOfFirstGridPointInDegrees',
             'longitudeOfFirstGridPointInDegrees', 'iDirectionIncrementInDegrees',
             'jDirectionIncrementInDegrees', 'scanningMode')
PARAMS = {'wave': ['swh', 'mwd', 'pp1d'], 'oper': ['10u', '10v']}
PARAM_COLUMNS = {140229: 'offshore_height_m', 140230: 'wave_direction_deg',
                 140231: 'peak_period_s', 165: 'u10_ms', 166: 'v10_ms'}
ECCODES_LOCK = Lock()


def utc(value):
    value = pd.Timestamp(value)
    return value.tz_localize('UTC') if value.tzinfo is None else value.tz_convert('UTC')


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    temp.replace(path)


def grid_signature(gid):
    return {key: ec.codes_get(gid, key) for key in GRID_KEYS}


def lock_offshore_grid(grib_path, lock_path=GRID_FILE):
    """Search once, persist index and grid identity; existing locks never re-search."""
    lock_path = Path(lock_path)
    if lock_path.exists():
        return json.loads(lock_path.read_text(encoding='utf-8'))
    with open(grib_path, 'rb') as stream:
        gid = ec.codes_grib_new_from_file(stream)
        if gid is None:
            raise ValueError('No GRIB field found')
        try:
            if ec.codes_get(gid, 'paramId') != 140229:
                raise ValueError('Grid discovery requires a significant wave height field first')
            lat = ec.codes_get_array(gid, 'latitudes')
            lon = ec.codes_get_array(gid, 'longitudes')
            values = ec.codes_get_values(gid)
            valid = np.isfinite(values) & (values >= 0) & (values < 100)
            if ec.codes_get(gid, 'bitmapPresent'):
                valid &= ec.codes_get_array(gid, 'bitmap').astype(bool)
            # Great-circle distances to every nonmissing ocean wave cell.
            dlat = np.deg2rad(lat - TARGET[0])
            dlon = np.deg2rad((lon - TARGET[1] + 180) % 360 - 180)
            a = np.sin(dlat / 2)**2 + np.cos(np.deg2rad(TARGET[0])) * np.cos(np.deg2rad(lat)) * np.sin(dlon / 2)**2
            distance = 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            distance[~valid] = np.inf
            index = int(np.argmin(distance))
            if not np.isfinite(distance[index]):
                raise ValueError('No valid ocean wave cells')
            payload = {'latitude': float(lat[index]), 'longitude': float(lon[index]),
                       'index': index, 'distance_km': float(distance[index]),
                       'grid': grid_signature(gid), 'target': list(TARGET),
                       'selected_at_utc': datetime.now(timezone.utc).isoformat(),
                       'method': 'Global great-circle minimum over valid swh ocean cells'}
        finally:
            ec.codes_release(gid)
    atomic_json(lock_path, payload)
    return payload


def client(source='ecmwf'):
    return Client(source=source, model='ifs', resol='0p25', maximum_retries=2, retry_after=3)


def latest_complete_run(source='ecmwf'):
    """Choose a common wave/wind cycle with the full 144-hour horizon present."""
    c = client(source)
    wave = utc(c.latest(stream='wave', type='fc', step=144, param='swh'))
    wind = utc(c.latest(stream='oper', type='fc', step=144, param='10u'))
    return min(wave, wind)


def retrieve_fields(run, step, stream, source='ecmwf'):
    run = utc(run)
    folder = ROOT / 'data/cache' / run.strftime('%Y%m%dT%H%MZ')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{stream}_{step:03d}.grib2'
    if not path.exists():
        temp = path.with_suffix('.part')
        client(source).retrieve(date=run.strftime('%Y%m%d'), time=run.hour, stream=stream,
                                type='fc', step=step, param=PARAMS[stream], target=str(temp))
        temp.replace(path)
    return path


def extract_fields(path, grid, run, step):
    # Windows ecCodes definition loading is not safe across simultaneous decoders.
    with ECCODES_LOCK:
        return _extract_fields(path, grid, run, step)


def _extract_fields(path, grid, run, step):
    result = {}
    with open(path, 'rb') as stream:
        while (gid := ec.codes_grib_new_from_file(stream)) is not None:
            try:
                if grid_signature(gid) != grid['grid']:
                    raise ValueError('ECMWF grid changed: saved point requires explicit review; no automatic search')
                actual_run = pd.to_datetime(f"{ec.codes_get(gid, 'dataDate')}{ec.codes_get(gid, 'dataTime'):04d}", format='%Y%m%d%H%M', utc=True)
                if actual_run != utc(run) or int(ec.codes_get(gid, 'endStep')) != step:
                    raise ValueError('GRIB cycle/lead time does not match the requested forecast')
                value = float(ec.codes_get_elements(gid, 'values', [grid['index']])[0])
                if not np.isfinite(value) or value == ec.codes_get(gid, 'missingValue'):
                    raise ValueError('Saved offshore point has missing data; refusing to relocate it')
                result[PARAM_COLUMNS[int(ec.codes_get(gid, 'paramId'))]] = value
            finally:
                ec.codes_release(gid)
    return result


def transform_waves(frame, matrix_path=ROOT / 'matrix/east_matrix.txt'):
    matrix = np.loadtxt(matrix_path)
    if matrix.shape != (24, 18) or not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError('Expected a finite, nonnegative 24 by 18 matrix')
    result = frame.copy()
    values = result[['offshore_height_m', 'peak_period_s', 'wave_direction_deg']].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, 0] < 0).any() or (values[:, 1] <= 0).any():
        raise ValueError('Wave height, peak period and direction must be valid')
    direction = (np.floor((values[:, 2] % 360) / 15 + 0.5).astype(int) * 15) % 360
    direction[direction == 0] = 360
    period = np.clip(np.floor(values[:, 1] + 0.5), 4, 24).astype(int)
    rows = direction // 15 - 1
    columns = np.array([PERIOD_COLUMNS[p] for p in period])
    result['matrix_direction_deg'] = direction
    result['matrix_period_s'] = period
    result['matrix_row'] = rows
    result['matrix_column'] = columns
    result['period_clipped'] = (values[:, 1] < 4) | (values[:, 1] > 24)
    result['transfer_coefficient'] = matrix[rows, columns]
    result['offshore_height_ft'] = values[:, 0] * FEET_PER_METRE
    result['nearshore_height_ft'] = result.offshore_height_ft * result.transfer_coefficient
    return result


def fetch_forecast(run=None, start=None, source='ecmwf', workers=2, horizon_hours=48):
    run = latest_complete_run(source) if run is None else utc(run)
    start = utc(pd.Timestamp.now(tz='UTC') if start is None else start).ceil('3h')
    first = int((start - run) / pd.Timedelta(hours=1))
    if horizon_hours not in (48, 120) or first < 0 or first + horizon_hours > 144 or first % 3:
        raise ValueError('Forecast window must be 48 or 120 hours, at three-hour intervals, through hour 144')
    steps = list(range(first, first + horizon_hours + 1, 3))
    if GRID_FILE.exists():
        grid = json.loads(GRID_FILE.read_text())
    else:
        grid = lock_offshore_grid(retrieve_fields(run, steps[0], 'wave', source))
    folder = ROOT / 'data/cache' / run.strftime('%Y%m%dT%H%MZ')
    folder.mkdir(parents=True, exist_ok=True)

    def one(step):
        point_file = folder / f'point_{step:03d}.json'
        if point_file.exists():
            payload = json.loads(point_file.read_text())
            if payload['grid'] != grid:
                raise ValueError('Cached point does not match the locked grid')
            return step, payload['values']
        result = {}
        for stream in PARAMS:
            path = retrieve_fields(run, step, stream, source)
            result.update(extract_fields(path, grid, run, step))
        if set(result) != set(PARAM_COLUMNS.values()):
            raise ValueError(f'Incomplete forecast at lead {step}')
        atomic_json(point_file, {'grid': grid, 'values': result})
        return step, result

    rows = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, step) for step in steps]
        for future in as_completed(futures):
            step, row = future.result()
            rows[step] = row
            print(f'Forecast {len(rows)}/{len(steps)}: lead {step} h', flush=True)
    frame = pd.DataFrame([rows[s] for s in steps], index=pd.DatetimeIndex([run + pd.Timedelta(hours=s) for s in steps], name='time_utc'))
    frame['wind_speed_kn'] = np.hypot(frame.u10_ms, frame.v10_ms) * 3600 / 1852
    frame['wind_direction_deg'] = (270 - np.rad2deg(np.arctan2(frame.v10_ms, frame.u10_ms))) % 360
    frame = transform_waves(frame)
    frame.attrs = {'run_utc': run.isoformat(), 'grid': grid, 'source': 'ECMWF IFS 0.25 degree',
                   'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
    return frame


def load_tide_events(path=ROOT / 'data/bom_tide_events.csv'):
    """Read published BOM high/low events, never extrapolating expired tables."""
    result = pd.read_csv(path)
    result['time_utc'] = pd.to_datetime(result.time_local, utc=True)
    result = result.set_index('time_utc').sort_index()
    if result.index.has_duplicates or not np.isfinite(result.height_m).all():
        raise ValueError('Invalid tide event table')
    if (result.height_m < -5).any() or (result.height_m > 15).any():
        raise ValueError('Invalid tide height units or values')
    gaps = result.index.to_series().diff().dropna().dt.total_seconds() / 3600
    if len(result) < 3 or (gaps > 9).any() or (gaps < 2).any():
        raise ValueError('Missing or implausibly spaced high/low tides')
    return result


def tide_curve(events, start, end):
    """Half-cosine interpolation of published extrema; not an hourly BOM product."""
    start, end = utc(start), utc(end)
    if events.index.min() > start or events.index.max() < end:
        raise ValueError('BOM tide table does not cover the requested window. Update the event CSV; no extrapolation is allowed.')
    times = pd.date_range(start, end, freq='10min')
    x = events.index.as_unit('ns').asi8
    target = times.as_unit('ns').asi8
    j = np.searchsorted(x, target, side='right') - 1
    j = np.clip(j, 0, len(x) - 2)
    fraction = (target - x[j]) / (x[j + 1] - x[j])
    heights = events.height_m.to_numpy()
    y = heights[j] + (heights[j + 1] - heights[j]) * (1 - np.cos(np.pi * fraction)) / 2
    return pd.Series(y, index=times, name='tide_height_m')


def save_forecast(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path)
    atomic_json(path.with_suffix('.json'), frame.attrs)


def load_forecast(path):
    path = Path(path)
    frame = pd.read_csv(path, index_col='time_utc', parse_dates=['time_utc'])
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.attrs = json.loads(path.with_suffix('.json').read_text())
    return frame


def plot_forecast(frame, events=None, output=None):
    if len(frame) != 41 or frame.index[-1] - frame.index[0] != pd.Timedelta(days=5):
        raise ValueError('Expected 41 three-hour samples spanning exactly five days')
    t = frame.index.tz_convert(TZ)
    with plt.rc_context({'font.family': 'DejaVu Sans', 'font.size': 12, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.labelcolor': '#264354', 'text.color': '#183343'}):
        # 6 x 7.5 inches at 180 dpi = 1080 x 1350, Instagram portrait (4:5).
        fig, axes = plt.subplots(4, 1, figsize=(6, 7.5), dpi=180, sharex=True,
                                 gridspec_kw={'height_ratios': [1.7, 1, 1, 1]})
        fig.patch.set_facecolor('#f6f9fb')
        fig.subplots_adjust(left=.09, right=.97, bottom=.17, top=.79, hspace=.66)
        fig.text(.06, .946, 'SURF FORECAST', fontsize=25, weight='bold')
        run = utc(frame.attrs['run_utc'])
        fig.text(.06, .904, f"5 DAYS   /   {t[0]:%d %b} - {t[-1]:%d %b %Y}".upper(), fontsize=15, color='#007f7c', weight='bold')
        fig.text(.06, .868, f"Model: {run:%d %b}, {run:%H} UTC  |  Local time: Sydney", fontsize=12, color='#56707e')
        fig.text(.06, .827, 'Nearshore', color='#007f7c', fontsize=13, weight='bold')
        fig.text(.31, .827, '- - Offshore', color='#7196b0', fontsize=13)
        fig.text(.97, .827, 'WAVES / ft', ha='right', fontsize=13, weight='bold')
        axes[0].fill_between(t, frame.nearshore_height_ft, color='#059e9a', alpha=.16)
        axes[0].plot(t, frame.nearshore_height_ft, color='#007f7c', lw=2.4, label='Nearshore Hs')
        axes[0].plot(t, frame.offshore_height_ft, color='#7196b0', lw=1.6, ls='--', label='Offshore Hs')
        axes[0].set_ylim(bottom=0)
        axes[1].plot(t, frame.peak_period_s, color='#da8640', lw=2)
        axes[1].set_title('PEAK PERIOD / s', loc='left', fontsize=13, weight='bold', pad=8)
        axes[1].set_ylim(bottom=0, top=max(frame.peak_period_s.max() * 1.55, 8))
        axes[2].plot(t, frame.wind_speed_kn, color='#4975ad', lw=2)
        axes[2].fill_between(t, frame.wind_speed_kn, color='#4975ad', alpha=.10)
        axes[2].set_title('WIND / kn', loc='left', fontsize=13, weight='bold', pad=8)
        axes[2].set_ylim(bottom=0, top=max(frame.wind_speed_kn.max() * 1.7, 5))
        # Labels are meteorological FROM bearings, not ambiguous arrow directions.
        compass = np.array(['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'])
        daily_ticks = pd.date_range(t[0].normalize(), t[-1].normalize(), freq='D') + pd.DateOffset(hours=12)
        daily_ticks = daily_ticks[(daily_ticks >= t[0]) & (daily_ticks <= t[-1])]
        for ax, column in [(axes[1], 'wave_direction_deg'), (axes[2], 'wind_direction_deg')]:
            for tick in daily_ticks:
                i = int(np.argmin(np.abs(t - tick)))
                bearing = frame[column].iloc[i]
                label = compass[int(np.floor(bearing / 22.5 + .5)) % 16]
                ax.text(tick, .84, label, transform=ax.get_xaxis_transform(), ha='center', va='center', fontsize=12, color='#617681')
        if events is None:
            axes[3].text(.5, .5, 'BOM tides unavailable', transform=axes[3].transAxes, ha='center')
        else:
            curve = tide_curve(events, frame.index[0], frame.index[-1])
            axes[3].plot(curve.index.tz_convert(TZ), curve, color='#7164a0', lw=1.5, label='Interpolated between high/low tides')
            shown = events.loc[frame.index[0]:frame.index[-1]]
            axes[3].scatter(shown.index.tz_convert(TZ), shown.height_m, color='#7164a0', s=17, zorder=3, label='BOM published high/low')
            axes[3].set_ylim(bottom=0, top=max(curve.max()*1.12, 1))
        axes[3].set_title('TIDE / m LAT', loc='left', fontsize=13, weight='bold', pad=8)
        for ax in axes:
            ax.set_facecolor('white')
            ax.grid(axis='y', color='#e1e8ed', lw=.7)
            ax.grid(axis='x', color='#e1e8ed', lw=.7)
            ax.set_axisbelow(True)
            ax.spines['left'].set_color('#c9d5dd')
            ax.spines['bottom'].set_color('#c9d5dd')
            ax.set_xlim(t[0], t[-1])
            ax.yaxis.set_major_locator(MaxNLocator(nbins=3, min_n_ticks=2))
            ax.tick_params(axis='y', labelsize=12, length=0)
            ax.tick_params(axis='x', length=0)
        axes[-1].set_xticks(daily_ticks)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%a\n%d %b', tz=TZ))
        axes[-1].tick_params(axis='x', labelsize=12, pad=8)
        fig.text(.06, .083, 'Hs estimate | Directions: FROM near noon', fontsize=12, color='#647986')
        fig.text(.06, .051, 'Tide: regional high/low + interpolated curve', fontsize=11.5, color='#647986')
        fig.text(.06, .019, 'ECMWF (CC BY 4.0) | BOM*', fontsize=11.5, color='#647986')
        fig.text(.97, .019, '*BOM terms', ha='right', fontsize=11.5, color='#647986')
        if output is not None:
            output = Path(output)
            output.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output, dpi=180, facecolor=fig.get_facecolor())
        return fig
