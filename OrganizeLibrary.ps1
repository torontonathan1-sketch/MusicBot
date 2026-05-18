[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Reload PATH so py and git are found
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
Write-Host "     🎵 ULTIMATE MUSIC BOT (NOTION SYNC)  " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

$outputPath = $PSScriptRoot
$tracksFile = Join-Path $PSScriptRoot "tracks.txt"

# Option to sync with Notion
$syncChoice = Read-Host "🔄 Sync with your Notion checklist first? (y/n)"
if ($syncChoice -eq 'y') {
    & $PythonCmd "$PSScriptRoot\SyncNotion.py"
}

if (Test-Path $tracksFile) {
    $count = (Get-Content $tracksFile).Count
    Write-Host "✨ Found $count songs in your list!" -ForegroundColor Green
    $choice = Read-Host "Start the Power Download now? (y/n)"
    if ($choice -eq 'y') {
        & $PythonCmd "$PSScriptRoot\PowerDownload.py" --file $tracksFile
        
        Write-Host ""
        if (Test-Path "$PSScriptRoot\organize_music.py") {
            Write-Host "🧹 Final Polish: Organizing folders by Artist/Album..." -ForegroundColor Cyan
            & $PythonCmd "$PSScriptRoot\organize_music.py"
        }
        
        Write-Host "✅ ALL DONE! Your library is updated and organized." -ForegroundColor Green
    }
}

while ($true) {
    Write-Host ""
    Write-Host "Update your Notion checklist anytime, then run this again!" -ForegroundColor Gray
    $exit = Read-Host "Type 'exit' to quit"
    if ($exit -eq 'exit') { break }
}