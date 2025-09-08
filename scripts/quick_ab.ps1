# scripts\quick_ab.ps1
param(
  [string]$AOut = 'artifacts\A.csv',
  [string]$BOut = 'artifacts\B.csv'
)

$root = 'artifacts\proof2'
New-Item -Force -ItemType Directory $root | Out-Null

function Make-Yaml {
  param(
    [string]$name, [double]$tp, [int]$maxBars,
    [double]$lateFrac, [double]$lateAfter, [double]$beArm,
    [int]$fee, [string]$csvOut
  )
  $y = @"
mode: backtest
dataset:
  type: jsonl
  events_jsonl: data/raw/events.jsonl
  ticks_dir: data/real/ticks

backtest:
  max_bars: $maxBars
  tp_mult:  $tp
  sl_pct:   0.02

sim:
  slippage_bps: 10
  be_arm_frac: $beArm
  use_breakeven: true
  late_tp_frac: $lateFrac
  late_tp_after_frac: $lateAfter

risk:
  base_size_usd: 200
  fee_bps: $fee

params:
  max_bars: $maxBars
  tp_mult:  $tp
  sl_pct:   0.02
  be_arm_frac: $beArm
  use_breakeven: true
  late_tp_frac: $lateFrac
  late_tp_after_frac: $lateAfter

trade_log_csv: $csvOut
"@
  $path = Join-Path $root "$name.yaml"
  $y | Out-File $path -Encoding utf8
  return $path
}

$A = Make-Yaml -name 'A_easy' -tp 1.001 -maxBars 8  -lateFrac 2.0   -lateAfter 2.0  -beArm 0.0015 -fee 0   -csvOut (Join-Path $root 'A_easy.csv')
$B = Make-Yaml -name 'B_hard' -tp 1.050 -maxBars 60 -lateFrac 0.003 -lateAfter 0.55 -beArm 0.0030 -fee 200 -csvOut (Join-Path $root 'B_hard.csv')

$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe tools\run_cfg.py -c $A -o (Join-Path $root 'A_easy.csv')
.\.venv\Scripts\python.exe tools\run_cfg.py -c $B -o (Join-Path $root 'B_hard.csv')

'--- Exit mix (A) ---'
if (Test-Path (Join-Path $root 'A_easy.csv')) {
  Import-Csv (Join-Path $root 'A_easy.csv') | Group-Object exit | Sort-Object Count -Desc | ft -AutoSize
}
'--- Exit mix (B) ---'
if (Test-Path (Join-Path $root 'B_hard.csv')) {
  Import-Csv (Join-Path $root 'B_hard.csv') | Group-Object exit | Sort-Object Count -Desc | ft -AutoSize
}
