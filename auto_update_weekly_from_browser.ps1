$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ApiUrl = "https://www.tf2easy.com/api/proxy/myapi/affiliate/getReferredUsers?page=1&status=&sortField=wagered&sortOrder=desc&range=7"
$BrowserUrl = "view-source:$ApiUrl"
$SourceFile = Join-Path $ProjectDir "weekly_source.json"
$Updater = Join-Path $ProjectDir "update_weekly_data.py"
$LogFile = Join-Path $ProjectDir "auto_update_weekly.log"

Set-Location $ProjectDir

function Write-Log {
  param([string]$Message)
  $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
  Add-Content -Path $LogFile -Value $line -Encoding UTF8
  Write-Host $Message
}

trap {
  Write-Log "FAILED: $($_.Exception.Message)"
  exit 1
}

function Get-BrowserPath {
  $browserCommands = @("firefox.exe", "msedge.exe", "chrome.exe")

  foreach ($command in $browserCommands) {
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    if ($resolved) {
      return $resolved.Source
    }
  }

  $browserPaths = @(
    "$env:ProgramFiles\Mozilla Firefox\firefox.exe",
    "${env:ProgramFiles(x86)}\Mozilla Firefox\firefox.exe",
    "$env:LocalAppData\Mozilla Firefox\firefox.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:LocalAppData\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
  )

  foreach ($path in $browserPaths) {
    if ($path -and (Test-Path $path)) {
      return $path
    }
  }

  throw "Could not find Firefox, Edge, or Chrome in PATH."
}

function Focus-BrowserWindow {
  $shell = New-Object -ComObject WScript.Shell
  $titles = @("tf2easy", "getReferredUsers", "Mozilla Firefox", "Firefox", "Microsoft Edge", "Google Chrome")

  foreach ($title in $titles) {
    if ($shell.AppActivate($title)) {
      Write-Log "Focused browser by title: $title"
      return $shell
    }
  }

  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class WindowTools {
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@ -ErrorAction SilentlyContinue

  $processNames = @("firefox", "msedge", "chrome")
  foreach ($processName in $processNames) {
    $process = Get-Process -Name $processName -ErrorAction SilentlyContinue |
      Where-Object { $_.MainWindowHandle -ne 0 } |
      Select-Object -Last 1

    if ($process) {
      [WindowTools]::ShowWindow($process.MainWindowHandle, 9) | Out-Null
      [WindowTools]::SetForegroundWindow($process.MainWindowHandle) | Out-Null
      Write-Log "Focused browser by process: $processName"
      return $shell
    }
  }

  throw "Could not focus the browser window. Bring the TF2Easy tab to the front and run again."
}

function Click-PageBody {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class MouseTools {
  [DllImport("user32.dll")]
  public static extern bool SetCursorPos(int X, int Y);

  [DllImport("user32.dll")]
  public static extern void mouse_event(int dwFlags, int dx, int dy, int cButtons, int dwExtraInfo);

  public const int MOUSEEVENTF_LEFTDOWN = 0x0002;
  public const int MOUSEEVENTF_LEFTUP = 0x0004;
}
"@ -ErrorAction SilentlyContinue

  [MouseTools]::SetCursorPos(320, 220) | Out-Null
  [MouseTools]::mouse_event([MouseTools]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
  Start-Sleep -Milliseconds 80
  [MouseTools]::mouse_event([MouseTools]::MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
}

function Copy-PageJson {
  param($shell)

  for ($attempt = 1; $attempt -le 3; $attempt++) {
    $shell.SendKeys("{ESC}")
    Start-Sleep -Milliseconds 350
    Click-PageBody
    Start-Sleep -Milliseconds 350
    $shell.SendKeys("^a")
    Start-Sleep -Milliseconds 500
    $shell.SendKeys("^c")
    Start-Sleep -Seconds 1

    $value = Get-Clipboard -Raw
    if ($value -and $value.TrimStart().StartsWith("{")) {
      return $value
    }

    if ($value -and $value.TrimStart().StartsWith("http")) {
      Write-Log "Attempt $attempt copied the address bar instead of the page. Retrying..."
    } else {
      Write-Log "Attempt $attempt did not copy JSON. Retrying..."
    }
  }

  throw "Could not copy JSON from the browser page. Click the JSON body once and run this script again."
}

Write-Log "Starting weekly browser update."
Write-Log "Opening TF2Easy weekly API source in your real browser..."
$browserPath = Get-BrowserPath
Write-Log "Using browser: $browserPath"
Start-Process -FilePath $browserPath -ArgumentList $BrowserUrl

Write-Log "Waiting for the API page to load..."
Start-Sleep -Seconds 15

$shell = Focus-BrowserWindow
Start-Sleep -Milliseconds 500

$clipboard = Copy-PageJson $shell
Write-Log "Copied $($clipboard.Length) characters from browser."
$startIndex = $clipboard.IndexOf("{")
$endIndex = $clipboard.LastIndexOf("}")

if ($startIndex -lt 0 -or $endIndex -le $startIndex) {
  throw "Clipboard did not contain JSON. Make sure the browser page shows the raw API JSON."
}

$json = $clipboard.Substring($startIndex, $endIndex - $startIndex + 1)
$payload = $json | ConvertFrom-Json

if ($null -eq $payload.data) {
  throw "Copied JSON does not contain a data array."
}

if ($payload.data.Count -eq 0) {
  throw "Copied JSON has no leaderboard entries. Refusing to overwrite the weekly leaderboard."
}

$firstEntry = $payload.data | Select-Object -First 1
Write-Log "First entry copied: $($firstEntry.username), wagered=$($firstEntry.wagered)"

Set-Content -Path $SourceFile -Value $json -Encoding UTF8
Write-Log "Saved fresh API response to weekly_source.json"

python $Updater
Write-Log "Weekly leaderboard refresh complete."
