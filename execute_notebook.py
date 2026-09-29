"""Execute the inspection notebook with the project's local Python kernel."""
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parent
os.environ['JUPYTER_PATH'] = str(root / '.venv/share/jupyter')
os.environ['JUPYTER_RUNTIME_DIR'] = str(root / '.venv/jupyter_runtime')
os.environ['IPYTHONDIR'] = str(root / '.venv/ipython')
path = root / 'forecast_check.ipynb'
nb = nbformat.read(path, as_version=4)
NotebookClient(nb, timeout=180, kernel_name='surf-forecast',
               resources={'metadata': {'path': str(root)}}).execute()
nbformat.write(nb, path)
print('Executed notebook:', path.name)
