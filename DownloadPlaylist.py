import sys
import subprocess
import re
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Please provide a playlist URL.")
        return

    url = sys.argv[1]
    MUSIC_ROOT = Path(__file__).parent.absolute()
    PLAYLIST_DIR = MUSIC_ROOT / "Playlists"
    PLAYLIST_DIR.mkdir(exist_ok=True)

    # Determine if it's a link or a search term
    if "spotify.com" in url:
        print("\n🎧 Spotify links require a login which we don't have.")
        print("💡 TIP: Instead of the link, just type the NAME of the playlist (e.g. 'Chill Vibes')!")
        return

    is_link = url.startswith("http")
    FFMPEG_PATH = r"C:\Users\Steve\.spotdl"
    
    if is_link:
        print(f"\n🎥 Processing Link: {url}")
        search_query = url
    else:
        print(f"\n🔍 Searching YouTube for: {url}")
        search_query = f"ytsearchmusic1:{url} playlist"

    output_template = str(PLAYLIST_DIR / "%(playlist|Unknown Playlist)s" / "%(playlist_index)02d - %(title)s.%(ext)s")
    
    cmd = [
        "yt-dlp",
        search_query,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "4",
        "--ffmpeg-location", FFMPEG_PATH,
        "--output", output_template,
        "--add-metadata",
        "--postprocessor-args", "ffmpeg:-id3v2_version 3",
        "--yes-playlist",
        "--ignore-errors",
        "--trim-filenames", "100"
    ]
    
    subprocess.run(cmd)

    print(f"\n✅ Playlist processing complete! Check: {PLAYLIST_DIR.absolute()}")

if __name__ == "__main__":
    main()
