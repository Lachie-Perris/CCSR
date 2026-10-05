"""Generate a minimal mobile page around the Python-rendered forecast graphic."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent


def build_page(folder=ROOT / 'output'):
    folder = Path(folder)
    models = [model for model in ('ec', 'gfs')
              if (folder / f'{model}_forecast.png').is_file()
              and (folder / f'{model}_forecast.png').stat().st_size > 0]
    if not models:
        raise FileNotFoundError('No successful forecasts; keep the existing published site')
    default = models[0]
    buttons = '\n'.join(
        f'<button id="{model}" class="{"active" if model == default else ""}" '
        f'role="tab" aria-selected="{str(model == default).lower()}">{model.upper()}</button>'
        for model in models)
    page = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f6f9fb">
  <title>Surf forecast</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f6f9fb; font-family: system-ui, sans-serif; }
    main { max-width: 600px; margin: 0 auto; padding: 8px 0 max(20px, env(safe-area-inset-bottom)); }
    .graphic { position: relative; }
    img { display: block; width: 100%; height: auto; }
    .terms { position: absolute; right: 2%; bottom: 0; width: 25%; height: 5%; }
    .switch { display: flex; gap: 8px; padding: 0 16px 10px; }
    .switch button { flex: 1; min-height: 46px; border: 0; border-radius: 10px; background: #dce8ee; color: #173344; font-size: 17px; font-weight: 700; }
    .switch button.active { background: #007f7c; color: white; }
    .download { display: block; margin: 12px 16px 0; padding: 15px 20px; min-height: 52px;
      border-radius: 12px; background: #007f7c; color: white; text-align: center;
      font-size: 18px; font-weight: 650; text-decoration: none; }
    a:focus-visible { outline: 3px solid #e29145; outline-offset: 3px; }
    .download:hover { background: #006865; }
  </style>
</head>
<body>
  <main>
    <div class="switch" role="tablist" aria-label="Forecast model">
      __BUTTONS__
    </div>
    <div class="graphic">
      <img id="forecast" src="__DEFAULT___forecast.png" width="1080" height="1350" alt="Two-day surf forecast graphic.">
      <a class="terms" href="https://www.bom.gov.au/oceanography/projects/ntc/nsw_tide_tables.shtml" aria-label="BOM tide copyright and conditions of use"></a>
    </div>
    <a id="download" class="download" href="__DEFAULT___forecast.png" download="surf-forecast-__DEFAULT__.png">Download .png</a>
  </main>
  <script>
    const image = document.getElementById('forecast');
    const download = document.getElementById('download');
    const models = __MODELS__;
    for (const model of models) document.getElementById(model).addEventListener('click', () => {
      const isGfs = model === 'gfs';
      image.src = isGfs ? 'gfs_forecast.png' : 'ec_forecast.png';
      download.href = image.src;
      download.download = `surf-forecast-${model}.png`;
      for (const other of models) {
        document.getElementById(other).classList.toggle('active', other === model);
        document.getElementById(other).setAttribute('aria-selected', other === model);
      }
    });
  </script>
</body>
</html>
'''
    page = page.replace('__BUTTONS__', buttons).replace('__DEFAULT__', default).replace('__MODELS__', json.dumps(models))
    path = folder / 'index.html'
    path.write_text(page, encoding='utf-8')
    return path


if __name__ == '__main__':
    print(build_page())
