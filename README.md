# Five-day surf forecast

Python ECMWF wave/wind forecasts, a fixed direction/peak-period transformation matrix, and a single five-day plot with BOM tides. No beach name is stored in code or displayed on the plot. GitHub Pages and Actions are intentionally deferred until notebook review.

The final PNG is **1080 x 1350 pixels (4:5 portrait)** for Instagram. The generated mobile page contains only the graphic and a large **Download .png** button. The BOM terms label embedded in the graphic links to the source conditions. Generate `output/index.html` with `python build_preview.py` after plotting; the notebook also does this automatically. There is no JavaScript, account integration, tracking, or publishing step.

## Open the notebook

Open `forecast_check.ipynb` in VS Code or Jupyter and select the project `.venv` Python kernel. Run all cells. The default mode replays the saved real ECMWF example with no network access and creates `output/forecast.png` and `output/forecast.svg`.

For a new environment (Python 3.11+):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

An existing Jupyter/VS Code installation can use `.venv/Scripts/python.exe` directly. Install JupyterLab separately if a browser-based notebook server is needed.

## Live forecasts

To regenerate the saved example without opening Jupyter:

```powershell
.\.venv\Scripts\python.exe run_forecast.py
```

Add `--live` for a fresh run, optionally `--run 2026-09-29T06:00Z --start 2026-09-29T21:00Z` while that run remains in ECMWF's rolling archive. Explicit dates must lie inside the selected model's forecast horizon.

The notebook has an opt-in `LIVE = True` switch to download a fresh two-day ECMWF forecast. The default start is the next three-hour UTC boundary. Downloading global GRIB fields is necessary with this feed; only the requested variables are fetched. Local raw-field and extracted-point caches prevent repeat downloads. Two concurrent download workers are used, with serialized GRIB decoding for Windows compatibility.

The GitHub Actions workflow runs after the ECMWF dissemination windows, generates both ECMWF and GFS forecasts, and deploys a minimal page with an EC/GFS switch plus PNG downloads. It reconstructs the private transformation matrix from the encrypted `WAVE_TRANSFER_MATRIX_B64` repository secret; the matrix file is ignored and never committed.

GFS uses Open-Meteo's explicitly selected GFS Wave 0.25° model at the same fixed target point. Its primary and secondary swell fields are displayed only when the response contains complete values. ECMWF's public open subset currently supplies combined wave fields but no swell partitions, so the EC graphic has no empty swell panels.

`config/offshore_grid.json` is the persistent one-time grid selection. Keep it. Forecasts reuse that location and reject grid changes. Do not delete it during cache cleanup.

Tide predictions currently come from a verified BOM table snapshot covering 28 September-7 October 2026. Automatic BOM access returned HTTP 403. The notebook clearly distinguishes this snapshot from a live feed and refuses to extrapolate it. For dates outside coverage, supply an updated BOM event CSV with `time_local` (ISO timestamp including offset) and `height_m` (metres LAT), or explicitly run the wave/wind plot without tides. Automatic tides remain to be resolved before deployment.

## Scientific checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Checks cover legacy matrix bins, rounding and north wrap, period clipping, feet conversion, missing inputs, saved-grid reuse, tide extrema, expiry and daylight saving. The notebook also shows an auditable table for the live example and controlled transformation cases.

See `SOURCES.md` for data provenance, the exact legacy lookup, and the limitations of bulk-wave transformation and interpolated tides.
