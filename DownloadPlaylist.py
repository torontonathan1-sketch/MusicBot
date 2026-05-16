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
    import json

    # Determine if it's a link or a search term
    tracks_to_download = []
    playlist_name = "Unknown Playlist"
    FFMPEG_PATH = r"C:\Users\Steve\.spotdl"

    if "spotify.com" in url:
        print("\n🎧 Spotify link detected! Deep scraping tracks...")
        try:
            # Get Playlist ID and fetch Embed Page
            playlist_id = url.split('/')[-1].split('?')[0]
            embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
            r = requests.get(embed_url, timeout=10)
            
            # Extract the JSON data block
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
            if match:
                data = json.loads(match.group(1))
                # Get Playlist Name
                playlist_name = data['props']['pageProps']['state']['data']['entity']['name']
                print(f"✨ Found Spotify Playlist: '{playlist_name}'")
                
                # Get Tracks
                items = data['props']['pageProps']['state']['data']['entity']['tracks']['items']
                for item in items:
                    t = item.get('track', item)
                    name = t.get('name')
                    artist = t.get('artists', [{}])[0].get('name', 'Unknown')
                    tracks_to_download.append(f"{artist} - {name}")
            else:
                print("⚠️ Could not scrape individual tracks. Falling back to search...")
                tracks_to_download = [url] # Fallback to original behavior
        except Exception as e:
            print(f"⚠️ Error reading Spotify: {e}")
            tracks_to_download = [url]
    else:
        # It's a plain search term or YouTube link
        tracks_to_download = [url]

    # Process all tracks
    for i, track_query in enumerate(tracks_to_download):
        is_link = track_query.startswith("http")
        
        if not is_link:
            print(f"\n🔍 [{i+1}/{len(tracks_to_download)}] Downloading: {track_query}")
            search_query = f"ytsearch1:{track_query}"
        else:
            print(f"\n🎥 [{i+1}/{len(tracks_to_download)}] Processing Link: {track_query}")
            search_query = track_query

        # If it's a Spotify-scraped track, force the folder to be the playlist name
        if len(tracks_to_download) > 1:
            output_template = str(PLAYLIST_DIR / sanitize_filename(playlist_name) / f"%(title)s.%(ext)s")
        else:
            output_template = str(PLAYLIST_DIR / "%(playlist|Unknown Playlist)s" / "%(playlist_index)02d - %(title)s.%(ext)s")
        
        cmd = [
            "yt-dlp",
            search_query,
            "--default-search", "ytsearch",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "4",
            "--ffmpeg-location", FFMPEG_PATH,
            "--output", output_template,
            "--add-metadata",
            "--postprocessor-args", "ffmpeg:-id3v2_version 3",
            "--no-playlist", # Individual tracks now
            "--ignore-errors",
            "--trim-filenames", "100"
        ]
        subprocess.run(cmd)

    print(f"\n✅ Playlist processing complete! Check: {PLAYLIST_DIR.absolute()}")

if __name__ == "__main__":
    main()
