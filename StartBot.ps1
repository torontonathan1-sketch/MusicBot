[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Reload PATH so Python is found
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
$PythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
$ScriptsPath = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
if (Test-Path $PythonPath) { $env:PATH = "$PythonPath;$env:PATH" }
if (Test-Path $ScriptsPath) { $env:PATH = "$ScriptsPath;$env:PATH" }

$PythonCmd = "py"
if (-not (Get-Command "py" -ErrorAction SilentlyContinue)) {
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        $PythonCmd = "python"
    } else {
        Write-Warning "Python was not detected on your PATH."
        Write-Warning "Please close this window, open a new PowerShell terminal, and try again."
        Read-Host "Press Enter to exit..."
        return
    }
}

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "         🎵 MUSIC BOT CONTROL CENTER       " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Choose which bot you want to run:" -ForegroundColor White
Write-Host "  [1] Main Bot (Sync Notion & Download Artists)" -ForegroundColor Yellow
Write-Host "  [2] Playlist Downloader (Spotify or YouTube Playlist Link)" -ForegroundColor Yellow
Write-Host "  [3] Retry Failed Downloads Watcher" -ForegroundColor Yellow
Write-Host ""

$choice = Read-Host "👉 Enter choice (1, 2, or 3)"

if ($choice -eq "1") {
    Clear-Host
    & "$PSScriptRoot\OrganizeLibrary.ps1"
}
elseif ($choice -eq "2") {
    Clear-Host
    & "$PSScriptRoot\DownloadPlaylist.ps1"
}
elseif ($choice -eq "3") {
    Clear-Host
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "     ⚙️ RETRY WATCHER RUNNING (failed_downloads.txt)   " -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    & $PythonCmd "$PSScriptRoot\RetryFailedDownloads.py"
}
else {
    Write-Host "Invalid choice. Exiting." -ForegroundColor Red
    Start-Sleep -Seconds 2
}
