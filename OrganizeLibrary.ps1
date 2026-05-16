# Reload PATH so py and git are found
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

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
    py "$PSScriptRoot\SyncNotion.py"
}

if (Test-Path $tracksFile) {
    $count = (Get-Content $tracksFile).Count
    Write-Host "✨ Found $count songs in your list!" -ForegroundColor Green
    $choice = Read-Host "Start the Power Download now? (y/n)"
    if ($choice -eq 'y') {
        py "$PSScriptRoot\PowerDownload.py" --file $tracksFile
        
        Write-Host ""
        Write-Host "🧹 Final Polish: Organizing folders by Artist/Album..." -ForegroundColor Cyan
        py "$PSScriptRoot\organize_music.py"
        
        Write-Host "✅ ALL DONE! Your library is updated and organized." -ForegroundColor Green
    }
}

while ($true) {
    Write-Host ""
    Write-Host "Update your Notion checklist anytime, then run this again!" -ForegroundColor Gray
    $exit = Read-Host "Type 'exit' to quit"
    if ($exit -eq 'exit') { break }
}
