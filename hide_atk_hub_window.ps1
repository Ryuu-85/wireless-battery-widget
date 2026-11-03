param(
  [string]$AtkHubPath = ""
)

$ErrorActionPreference = "SilentlyContinue"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win32WindowTools {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
"@

$expectedRoot = ""
if ($AtkHubPath) {
  try {
    $expectedRoot = (Resolve-Path $AtkHubPath).Path.ToLowerInvariant()
  } catch {}
}

$hidden = 0
[Win32WindowTools]::EnumWindows({
  param([IntPtr]$hwnd, [IntPtr]$lparam)
  if (-not [Win32WindowTools]::IsWindowVisible($hwnd)) {
    return $true
  }
  [uint32]$pid = 0
  [void][Win32WindowTools]::GetWindowThreadProcessId($hwnd, [ref]$pid)
  try {
    $process = Get-Process -Id $pid -ErrorAction Stop
    $path = [string]$process.Path
    $pathLower = $path.ToLowerInvariant()
    if (-not $pathLower.EndsWith("\atk hub.exe")) {
      return $true
    }
    if ($expectedRoot -and -not $pathLower.StartsWith($expectedRoot)) {
      return $true
    }
    [void][Win32WindowTools]::ShowWindowAsync($hwnd, 0)
    $script:hidden += 1
  } catch {}
  return $true
}, [IntPtr]::Zero) | Out-Null

Write-Output $hidden
