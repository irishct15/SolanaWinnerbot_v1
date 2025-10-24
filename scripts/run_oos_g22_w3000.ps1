$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path $PSScriptRoot\..).Path
$preset   = Join-Path $RepoRoot 'scripts\preset_live_g22_w3000.ps1'

$since = ([datetime]::UtcNow.Date.AddDays(-1)).ToString('yyyy-MM-dd')
$until = ([datetime]::UtcNow.Date).ToString('yyyy-MM-dd')

$j = & $preset -Since $since -Until $until

# Optional Telegram if your helper exists
$tg = Join-Path $RepoRoot 'scripts\telegram.ps1'
if (Test-Path $tg) { . $tg }
if (Get-Command Send-Telegram -ErrorAction SilentlyContinue) {
  $txt = ("GO LIVE OOS {0}->{1}  n={2}  WR={3:P1}  PF={4}  PnL=${5:N2}" -f $since,$until,$j.n_trades,$j.wr,$j.pf,$j.pnl_usd)
  try { Send-Telegram -Text $txt } catch { Write-Warning "[tg] send failed: $_" }
}
