"""Generate a minimal mobile page around the Python-rendered forecast graphic."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build_page(folder=ROOT / 'output'):
    folder = Path(folder)
    if not (folder / 'ec_forecast.png').exists() and not (folder / 'forecast.png').exists():
        raise FileNotFoundError('Generate an EC or GFS forecast graphic first')
    if not (folder / 'ec_forecast.png').exists() or not (folder / 'gfs_forecast.png').exists():
        raise FileNotFoundError('Generate both ec_forecast.png and gfs_forecast.png first')
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
      <button id="ec" class="active" role="tab" aria-selected="true">EC</button>
      <button id="gfs" role="tab" aria-selected="false">GFS</button>
    </div>
    <div class="graphic">
      <img id="forecast" src="ec_forecast.png" width="1080" height="1350" alt="Two-day surf forecast graphic.">
      <a class="terms" href="https://www.bom.gov.au/oceanography/projects/ntc/nsw_tide_tables.shtml" aria-label="BOM tide copyright and conditions of use"></a>
    </div>
    <a id="download" class="download" href="ec_forecast.png" download="surf-forecast-ec.png">Download .png</a>
  </main>
  <script>
    const image = document.getElementById('forecast');
    const download = document.getElementById('download');
    for (const model of ['ec', 'gfs']) document.getElementById(model).addEventListener('click', () => {
      const isGfs = model === 'gfs';
      image.src = isGfs ? 'gfs_forecast.png' : 'ec_forecast.png';
      download.href = image.src;
      download.download = `surf-forecast-${model}.png`;
      for (const other of ['ec', 'gfs']) {
        document.getElementById(other).classList.toggle('active', other === model);
        document.getElementById(other).setAttribute('aria-selected', other === model);
      }
    });
  </script>
</body>
</html>
'''
    path = folder / 'index.html'
    path.write_text(page, encoding='utf-8')
    return path


if __name__ == '__main__':
    print(build_page())
