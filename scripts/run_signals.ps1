param(
  [string]$TicksDir = "data\real\ticks",
  [string]$Out = "data\raw\events.jsonl",
  [int]$ma = 20,
  [int]$mom = 5,
  [int]$roi_len = 3,
  [double]$roi_min = 0.01,
  [int]$dedupe = 10
)
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m app.signals.confluence_v1 `
  --ticks-dir $TicksDir --out $Out `
  --ma $ma --mom $mom --roi-len $roi_len --roi-min $roi_min --dedupe-bars $dedupe
