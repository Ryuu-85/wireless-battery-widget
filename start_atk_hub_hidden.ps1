param(
  [string]$AtkHubPath = ""
)

$ErrorActionPreference = "SilentlyContinue"

if (-not $AtkHubPath) {
  $candidates = @(
    "$env:ProgramFiles\ATK HUB",
    "${env:ProgramFiles(x86)}\ATK HUB",
    "$env:LOCALAPPDATA\ATK HUB",
    "C:\software\ATK HUB",
    "D:\software\ATK HUB",
    "E:\software\ATK HUB",
    "F:\software\ATK HUB"
  )
  foreach ($candidate in $candidates) {
    if (Test-Path (Join-Path $candidate "ATK HUB.exe")) {
      $AtkHubPath = $candidate
      break
    }
  }
}

$exe = Join-Path $AtkHubPath "ATK HUB.exe"
if (-not (Test-Path $exe)) {
  throw "ATK HUB.exe was not found. Path: $AtkHubPath"
}

Start-Process `
  -FilePath $exe `
  -WorkingDirectory $AtkHubPath `
  -ArgumentList @("--remote-debugging-port=9224", "--remote-allow-origins=*") `
  -WindowStyle Hidden

$hideScript = Join-Path $PSScriptRoot "hide_atk_hub_window.ps1"
for ($i = 0; $i -lt 12; $i++) {
  Start-Sleep -Milliseconds 500
  if (Test-Path $hideScript) {
    & $hideScript -AtkHubPath $AtkHubPath | Out-Null
  }
}
