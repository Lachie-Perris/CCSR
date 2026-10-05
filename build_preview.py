"""Build a mobile page from the forecast graphics available in this run."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build_page(folder=ROOT / 'output'):
    folder = Path(folder)
    available = {}
    for view in ('week', 'weekend'):
        available[view] = {}
        for model in ('ec', 'gfs'):
            name = f'{model}_week_forecast.png' if view == 'week' else f'{model}_forecast.png'
            path = folder / name
            if path.is_file() and path.stat().st_size:
                available[view][model] = name
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CCSR Forecast</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fa;font-family:system-ui,sans-serif;color:#172f40}
main{max-width:600px;margin:auto;padding:12px 0 24px}.tabs{display:flex;gap:8px;padding:0 12px 10px}
button{flex:1;min-height:46px;border:0;border-radius:10px;background:#dce8ee;color:#172f40;font:700 17px system-ui;cursor:pointer}
button.active{background:#007f7c;color:white}button small{display:block;font-size:12px;font-weight:400}
img{display:block;width:100%;height:auto}.download{display:block;margin:12px;padding:15px;border-radius:12px;background:#007f7c;color:white;text-align:center;text-decoration:none;font-weight:650}
#unavailable{text-align:center;padding:80px 12px;font-size:22px}[hidden]{display:none!important}
button:focus-visible,a:focus-visible{outline:3px solid #e29145;outline-offset:2px}
</style></head><body><main>
<div class="tabs" role="tablist" aria-label="Forecast period">
<button id="week" role="tab">This week</button><button id="weekend" role="tab">The weekend</button></div>
<div class="tabs" role="tablist" aria-label="Forecast model">
<button id="ec" role="tab">EC</button><button id="gfs" role="tab">GFS</button></div>
<p id="unavailable" hidden>coming soon</p>
<a id="download" class="download" hidden>Download .png</a>
<img id="forecast" alt="Surf forecast" hidden>
<noscript>Please enable JavaScript to select a forecast.</noscript>
</main><script>
const available = __AVAILABLE__;
let view='week', model=available.week.ec?'ec':(available.week.gfs?'gfs':'ec');
const image=document.getElementById('forecast'), download=document.getElementById('download');
function render(){
  for(const name of ['week','weekend']){
    const button=document.getElementById(name);
    button.classList.toggle('active',name===view);button.setAttribute('aria-selected',name===view);
  }
  for(const name of ['ec','gfs']){
    const button=document.getElementById(name), exists=Boolean(available[view][name]);
    button.innerHTML=name.toUpperCase()+(exists?'':'<small>coming soon</small>');
    button.classList.toggle('active',name===model);button.setAttribute('aria-selected',name===model);
  }
  const src=available[view][model];
  image.hidden=download.hidden=!src;document.getElementById('unavailable').hidden=Boolean(src);
  if(src){image.src=src;image.alt=model.toUpperCase()+' '+view+' forecast';
    download.href=src;download.download='ccsr-'+view+'-'+model+'.png';
  }else{image.removeAttribute('src');download.removeAttribute('href');}
}
for(const name of ['week','weekend'])document.getElementById(name).onclick=()=>{
  view=name;if(!available[view][model])model=Object.keys(available[view])[0]||model;render();
};
for(const name of ['ec','gfs'])document.getElementById(name).onclick=()=>{model=name;render();};
render();
</script></body></html>'''
    page = page.replace('__AVAILABLE__', json.dumps(available))
    path = folder / 'index.html'
    path.write_text(page, encoding='utf-8')
    return path


if __name__ == '__main__':
    print(build_page())
