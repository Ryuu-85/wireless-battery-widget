param(
  [string]$AtkHubPath = "",
  [string]$TaskName = "WirelessBatteryWidget-ATKHUB",
  [string]$HideTaskName = "WirelessBatteryWidget-HideATKHUB"
)

$ErrorActionPreference = "Stop"

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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$startScript = Join-Path $scriptDir "start_atk_hub_hidden.ps1"
$hideScript = Join-Path $scriptDir "hide_atk_hub_window.ps1"

if (-not (Test-Path $startScript)) {
  throw "Missing script: $startScript"
}
if (-not (Test-Path $hideScript)) {
  throw "Missing script: $hideScript"
}

$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$startScript`" -AtkHubPath `"$AtkHubPath`"" `
  -WorkingDirectory $AtkHubPath

$hideAction = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$hideScript`" -AtkHubPath `"$AtkHubPath`"" `
  -WorkingDirectory $AtkHubPath

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$principal = New-ScheduledTaskPrincipal `
  -UserId $currentUser `
  -LogonType Interactive `
  -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName $HideTaskName -ErrorAction SilentlyContinue

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Principal $principal `
  -Settings $settings `
  -Force | Out-Null

Register-ScheduledTask `
  -TaskName $HideTaskName `
  -Action $hideAction `
  -Principal $principal `
  -Settings $settings `
  -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Milliseconds 1200
Start-ScheduledTask -TaskName $HideTaskName
Write-Host "Installed and started scheduled tasks: $TaskName, $HideTaskName"
