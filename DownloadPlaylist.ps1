[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Reload PATH so py and yt-dlp are found
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

# Explicitly add Python and Scripts directories to path if they exist
$PythonPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
$ScriptsPath = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
if (Test-Path $PythonPath) { $env:PATH = "$PythonPath;$env:PATH" }
if (Test-Path $ScriptsPath) { $env:PATH = "$ScriptsPath;$env:PATH" }

# Find working Python command
$PythonCmd = "py"
if (-not (Get-Command "py" -ErrorAction SilentlyContinue)) {
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        $PythonCmd = "python"
    } else {
        Write-Warning "Python was installed, but it is not yet detected on your PATH."
        Write-Warning "Please CLOSE this PowerShell window and open a NEW one to let the system load Python."
        Write-Warning "Alternatively, restart your computer if the new terminal still doesn't find it."
        Read-Host "Press Enter to close script..."
        return
    }
}

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "         🎶 PLAYLIST DOWNLOADER            " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Paste a YouTube or Spotify Playlist link!" -ForegroundColor White
Write-Host "Type 'exit' to quit." -ForegroundColor DarkGray
Write-Host ""

while ($true) {
    Write-Host ""
    $link = Read-Host "🔗 Playlist Link"

    if ($link -eq 'exit' -or $link -eq 'quit') {
        break
    }

    if ($link -ne "") {
        & $PythonCmd "$PSScriptRoot\DownloadPlaylist.py" "$link"
    }
}