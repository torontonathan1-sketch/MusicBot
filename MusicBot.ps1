# Reload PATH so py and git are found
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "         🎵 Music Downloader Bot          " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Supports: Artists, Albums, Playlists, Single Songs" -ForegroundColor White
Write-Host "Output:   Artist\Album\Song.mp3" -ForegroundColor White
Write-Host "Type 'exit' to close." -ForegroundColor DarkGray
Write-Host ""

$outputPath = "f:\Music 2026"

while ($true) {
    Write-Host ""
    $link = Read-Host "🎵 Paste Spotify Link"

    if ($link -eq 'exit' -or $link -eq 'quit') {
        Write-Host "Goodbye!" -ForegroundColor Cyan
        break
    }

    if ($link -match "spotify\.com") {
        Write-Host "⏳ Downloading... This may take a while for large playlists or artist discographies." -ForegroundColor Yellow
        Write-Host "👉 If it asks for Username/Password below, type them in and hit Enter! (It will be saved for next time)." -ForegroundColor Cyan

        py -m zotify `
            --root-path $outputPath `
            --output "{artist}/{album}/{song_name}.{ext}" `
            --download-format mp3 `
            --print-download-progress true `
            --skip-existing true `
            $link

        Write-Host ""
        Write-Host "✅ Done! Files saved to $outputPath" -ForegroundColor Green
    } else {
        Write-Host "❌ That doesn't look like a Spotify link. Please try again." -ForegroundColor Red
    }
}
