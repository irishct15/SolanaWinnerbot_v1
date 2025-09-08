param([ValidateSet("setup","smoke","ab","clean")]$t="smoke")
switch ($t) {
  "setup" {
    py -3.13 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
  }
  "smoke" {
    if (!(Test-Path .\.venv\Scripts\python.exe)) { py -3.13 -m venv .venv }
    .\.venv\Scripts\Activate.ps1
    $env:PYTHONPATH = (Get-Location).Path
    python tools\run_cfg.py -c .\configs\quick.yaml -o .\artifacts\trades.quick.csv
  }
  "ab" {
    if (!(Test-Path .\.venv\Scripts\python.exe)) { py -3.13 -m venv .venv }
    .\.venv\Scripts\Activate.ps1
    $env:PYTHONPATH = (Get-Location).Path
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\quick_ab.ps1
  }
  "clean" {
    Remove-Item -Recurse -Force artifacts\* -ErrorAction SilentlyContinue
  }
}
