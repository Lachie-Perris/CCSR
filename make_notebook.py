"""Build the reproducible forecast inspection notebook."""
from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parent
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook(cells=[
    md('# Two-day surf forecast\n\nReal ECMWF IFS wave/wind data, a fixed nearshore transfer matrix, and BOM high/low tides. '
       'Wave heights are **feet**, period is **peak period**, wind is knots, and tides are metres LAT. '
       'Times display in Australia/Sydney with daylight saving.\n\n'
       'The default test replays a saved forecast, so reopening this notebook does not download data or repeat the grid search. '
       'GitHub deployment is deferred.'),
    code('from pathlib import Path\nimport json\nimport numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\n'
         'from IPython.display import display, Markdown\n'
         'from surf_forecast import (ROOT, GRID_FILE, TZ, fetch_forecast, load_forecast, save_forecast,\n'
         '                           transform_waves, load_tide_events, tide_curve)\n'
         'LIVE = False  # Set True to download a fresh model forecast.\n'
         'INCLUDE_TIDES = True  # Requires the BOM table to cover the entire requested window.\n'
         'OUTPUT = ROOT / "output"\nOUTPUT.mkdir(exist_ok=True)'),
    md('## Saved offshore point\n\nThe nearest valid ocean wave cell was selected once. '
       'This cell only reads the saved coordinates; it does not perform a geographic search. '
       'The grid signature is checked against every new GRIB field.'),
    code('grid = json.loads(GRID_FILE.read_text())\n'
         'display(pd.Series({k: grid[k] for k in ["latitude", "longitude", "distance_km", "selected_at_utc"]}, name="Saved grid selection"))'),
    md('## Test 1: real two-day forecast\n\nThe offline example uses the **29 September 2026, 06 UTC** run. '
       'It spans 29 September 21 UTC to 4 October 21 UTC (41 samples). '
       'The model initialization and validity window below are authoritative; this saved example does not automatically become a current forecast.'),
    code('if LIVE:\n'
         '    forecast = fetch_forecast()\n'
         '    save_forecast(forecast, OUTPUT / "latest_forecast.csv")\n'
         'else:\n'
         '    forecast = load_forecast(ROOT / "data/test_forecast.csv").iloc[:17].copy()\n'
         'assert len(forecast) == 17\n'
         'assert forecast.index[-1] - forecast.index[0] == pd.Timedelta(days=2)\n'
         'assert forecast.index.to_series().diff().dropna().eq(pd.Timedelta(hours=3)).all()\n'
         'assert np.isfinite(forecast.select_dtypes(include="number")).all().all()\n'
         'display(pd.Series({"model_run_utc": forecast.attrs["run_utc"],\n'
         '                   "start_local": str(forecast.index[0].tz_convert(TZ)),\n'
         '                   "end_local": str(forecast.index[-1].tz_convert(TZ)), "samples": len(forecast)}))\n'
         'columns = ["offshore_height_ft", "peak_period_s", "wave_direction_deg",\n'
         '           "matrix_period_s", "matrix_direction_deg", "transfer_coefficient",\n'
         '           "nearshore_height_ft", "wind_speed_kn", "wind_direction_deg"]\n'
         'display(forecast[columns].head(10).round(2))'),
    md('## BOM tides\n\nThe included CSV contains **published BOM high/low predictions**, station NSW_TP004, '
       '28 September-7 October 2026, as a regional coastal proxy. Python requests to BOM returned HTTP 403, '
       'so automatic tide refresh is **not yet working**.\n\n'
       'Dots on the figure mark published extrema. The connecting half-cosine curve is an approximation generated here, '
       'not a BOM interval forecast. The code refuses to extrapolate outside the supplied dates. '
       'Tides do not modify the fixed wave transformation matrix. '
       'See [source and conditions](https://www.bom.gov.au/oceanography/projects/ntc/nsw_tide_tables.shtml) and `SOURCES.md`.'),
    code('events = load_tide_events() if INCLUDE_TIDES else None\n'
         'if events is not None:\n'
         '    tide = tide_curve(events, forecast.index[0], forecast.index[-1])\n'
         '    display(events.loc[forecast.index[0]:forecast.index[-1], ["time_local", "height_m"]].head(8))'),
    md('## Single two-day figure\n\nInstagram portrait format: **1080 x 1350 pixels (4:5)** with large labels for phone screens. '
       'The design follows the useful forecast hierarchy seen in Surfline and Swellnet: day cards, height, swell direction/period, wind, and tide. '
       'ECMWF open data does not include primary and secondary swell partitions, so those panels are explicitly marked unavailable. '
       'Hs is significant wave height, not breaking-wave face height.'),
    code('from forecast_plot import render_forecast\n'
         'tide = tide_curve(events, forecast.index[0], forecast.index[-1]) if events is not None else None\n'
         'fig = render_forecast(forecast, tide=tide, events=events, output=OUTPUT / "forecast.png")\n'
         'fig.savefig(OUTPUT / "forecast.svg", facecolor=fig.get_facecolor())\n'
         'display(fig)\nplt.close(fig)\n'
         'from build_preview import build_page\n'
         'page = build_page(OUTPUT)\n'
         'print("Mobile page:", page.name, "| PNG: 1080 x 1350")'),
    md('## Test 2: controlled matrix cases\n\nRows use 15-degree FROM directions, '
       'with north in the last row. Peak periods round half-up and clip to 4-24 seconds. '
       'The original period-to-column lookup is intentionally preserved, including skipped columns 12 and 14. '
       'These are labelled synthetic inputs for testing the transform, not forecast data.'),
    code('cases = pd.DataFrame({"offshore_height_m": [1.] * 8,\n'
         '                      "peak_period_s": [15, 10, 8, 4, 7, 6, 3, 25],\n'
         '                      "wave_direction_deg": [90, 180, 270, 0, 7.5, 352.5, 90, 90]})\n'
         'display(transform_waves(cases).round(4))'),
    md('## Verification\n\nRun the scientific checks and inspect the real forecast ranges.'),
    code('import unittest\n'
         'suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))\n'
         'result = unittest.TextTestRunner(verbosity=2).run(suite)\n'
         'assert result.wasSuccessful(), "Scientific checks failed"\n'
         'display(forecast[["offshore_height_ft", "nearshore_height_ft", "peak_period_s", "wind_speed_kn"]].agg(["min", "max"]).round(2))\n'
         'print("Periods outside matrix range:", int(forecast.period_clipped.sum()))'),
])
nb.metadata = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
               'language_info': {'name': 'python', 'version': '3.12'}}
nbf.write(nb, root / 'forecast_check.ipynb')
