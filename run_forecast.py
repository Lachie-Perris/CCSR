"""Generate a two-day phone and Instagram forecast graphic."""
import argparse
from pathlib import Path
import matplotlib
import pandas as pd

matplotlib.use('Agg')
from surf_forecast import ROOT, fetch_forecast, load_forecast, load_tide_events, save_forecast, tide_curve
from forecast_plot import render_forecast, render_full_forecast, weekend_window


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Download a fresh ECMWF forecast')
    parser.add_argument('--model', choices=('EC', 'GFS'), default='EC', help='Model to render')
    parser.add_argument('--view', choices=('weekend', 'week'), default='weekend')
    parser.add_argument('--run', help='Optional explicit UTC model initialization (ISO timestamp)')
    parser.add_argument('--start', help='Optional forecast start (ISO timestamp; rounded up to 3 h)')
    parser.add_argument('--no-tides', action='store_true', help='Explicitly omit tides')
    parser.add_argument('--tides', type=Path, help='Explicit saved tide table; live runs otherwise fetch BOM')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/forecast.png')
    args = parser.parse_args()
    if (args.run or args.start) and not args.live:
        parser.error('--run and --start require --live')
    window = weekend_window()
    # Request enclosing native three-hour samples; display only Saturday/Sunday.
    first = window[0].tz_convert('UTC').floor('3h')
    last = window[1].tz_convert('UTC').ceil('3h')
    if args.start:
        first = pd.Timestamp(args.start)
        first = first.tz_localize('UTC') if first.tzinfo is None else first.tz_convert('UTC')
        window = None
    hours = 48 if window is None else int((last - first).total_seconds() / 3600)
    if args.view == 'week':
        first = pd.Timestamp.now(tz='UTC').ceil('3h')
        hours = None  # Entire available model horizon, not a fixed seven-day crop.
        window = None
    if args.live and args.model == 'EC':
        frame = fetch_forecast(run=args.run, start=first, horizon_hours=hours)
        frame.attrs['model'] = 'ECMWF'
        save_forecast(frame, ROOT / 'output/ec_forecast.csv')
    elif args.live and args.model == 'GFS':
        from gfs_forecast import fetch_gfs_forecast
        frame = fetch_gfs_forecast(start=first, horizon_hours=hours)
        frame.attrs['model'] = 'GFS'
        save_forecast(frame, ROOT / 'output/gfs_forecast.csv')
    else:
        frame = load_forecast(ROOT / 'data/test_forecast.csv').copy()
        window = weekend_window(frame.index[0]) if args.view == 'weekend' else None
        frame.attrs['model'] = 'ECMWF'
    bounds = window or (frame.index[0], frame.index[-1])
    if args.no_tides:
        events = None
    elif args.tides:
        events = load_tide_events(args.tides)
    elif args.live:
        from bom_tides import fetch_tide_events
        events = fetch_tide_events(*bounds)
    else:
        events = load_tide_events()
    tide = tide_curve(events, *bounds) if events is not None else None
    if args.view == 'week':
        render_full_forecast(frame, events=events, output=args.output)
    else:
        render_forecast(frame, tide=tide, events=events, output=args.output, window=window)
    print(f'Created {args.output}')


if __name__ == '__main__':
    main()
