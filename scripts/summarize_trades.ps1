param([string]$Csv = "artifacts\trades.engine.csv")
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe .\tools\summarize_trades.py $Csv
