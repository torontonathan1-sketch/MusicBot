# Reload PATH so py and yt-dlp are found
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

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
        py "$PSScriptRoot\DownloadPlaylist.py" "$link"
    }
}
