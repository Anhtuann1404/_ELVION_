"""Explicit browser dependency setup into a separate project environment."""
from pathlib import Path
import subprocess
import venv

root = Path(__file__).resolve().parents[1]
environment = root/'.venv-browser'
if not (environment/'bin/python').exists():
    venv.EnvBuilder(with_pip=True).create(environment)
python = str(environment/'bin/python')
subprocess.run([python, '-m', 'pip', 'install', '--retries', '0', '--timeout', '15', 'playwright>=1.48,<2'], check=True)
subprocess.run([python, '-m', 'playwright', 'install', 'chromium'], check=True)
(environment/'browser-ready').write_text('playwright-chromium\n')
print('Browser environment ready. Use ./elvion or ./elvion --gui from this repository.')
