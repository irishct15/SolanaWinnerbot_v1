param(
  [string]$Since,
  [string]$Until,
  [string]$Mint = 'So11111111111111111111111111111111111111112',
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Resolve repo root robustly
$RepoRoot = (Resolve-Path $PSScriptRoot\..).Path
$py = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

# Defaults: yesterday->today if not provided
if (-not $Since) { $Since = ([datetime]::UtcNow.Date.AddDays(-7)).ToString('yyyy-MM-dd') }
if (-not $Until) { $Until = ([datetime]::UtcNow.Date).ToString('yyyy-MM-dd') }

$label = 'GO_LIVE_g22_s0p5_win3000_sl25_c1200_hrs2_10'
$out   = if ($OutDir) { $OutDir } else { Join-Path $RepoRoot "artifacts\backtests\$label" }

$args = @(
  '--source','auto','--mint',$Mint,'--since',$Since,'--until',$Until,
  '--every-sec','60','--flat-only','--dedupe-entries',
  '--ema-fast','5','--ema-slow','13',
  '--min-ema-gap-bps','22','--min-ema-slope-bps','0.5',
  '--min-gap-sec','1200',
  '--tp','0.0100','--sl','0.0025','--win','3000','--fee-bps','10',
  '--hour-start','2','--hour-end','10',
  '--out',$out
)

& $py -u -m app.backtest.run_backtest @args

$sumPath = Join-Path $out 'summary.json'
if (Test-Path $sumPath) {
  $j = Get-Content $sumPath -Raw | ConvertFrom-Json
  "{0}  n={1}  WR={2:P2}  PF={3}  PnL=${4:N2}  DD=${5:N2}" -f $label,$j.n_trades,$j.wr,$j.pf,$j.pnl_usd,$j.equity_drawdown | Write-Host
  return $j
} else {
  Write-Warning "no summary.json produced at $out"
}
