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

    import requests
    
    # Determine if it's a link or a search term
    search_query = url
    if "spotify.com" in url:
        print("\n🎧 Spotify link detected! Scouring YouTube for a match...")
        try:
            r = requests.get(url, timeout=10)
            # Find the title in the metadata
            match = re.search(r'property="og:title" content="(.*?)"', r.text)
            if match:
                playlist_title = match.group(1)
                print(f"✨ Found Spotify Playlist: '{playlist_title}'")
                search_query = f"ytsearchmusic1:{playlist_title} playlist"
            else:
                print("⚠️ Could not read the Spotify title. Try typing the name manually!")
                return
        except Exception as e:
            print(f"⚠️ Error reading Spotify: {e}")
            return

    is_link = search_query.startswith("http")
    FFMPEG_PATH = r"C:\Users\Steve\.spotdl"
    
    if not is_link:
        # Sanitize search query (remove # which can break URL parsing)
        search_query = search_query.replace("#", "")
        print(f"\n🔍 Searching YouTube for: {search_query}")
    else:
        print(f"\n🎥 Processing Link: {search_query}")

    output_template = str(PLAYLIST_DIR / "%(playlist|Unknown Playlist)s" / "%(playlist_index)02d - %(title)s.%(ext)s")
    
    cmd = [
        "yt-dlp",
        search_query,
        "--default-search", "ytsearch", # Safer than ytsearchmusic:
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
