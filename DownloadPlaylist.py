import sys
import subprocess
import re
from pathlib import Path

def sanitize_filename(name: str) -> str:
    """Remove characters illegal in Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()

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

    # Check if the input is a path to a .txt file
    input_path = Path(url.strip('"'))
    if input_path.suffix == ".txt" and input_path.exists():
        print(f"\n📄 Text file detected! Reading tracks from: {input_path.name}")
        with open(input_path, "r", encoding="utf-8") as f:
            tracks_to_download = [line.strip() for line in f if line.strip()]
        playlist_name = input_path.stem
        print(f"✨ Loaded {len(tracks_to_download)} tracks from file.")
    elif "spotify.com" in url:
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
                entity = data['props']['pageProps']['state']['data']['entity']
                
                # Get Playlist Name
                playlist_name = entity.get('name', entity.get('title', 'Unknown Playlist'))
                print(f"✨ Found Spotify Playlist: '{playlist_name}'")
                
                # Get Tracks (Handle multiple JSON structures)
                items = []
                if 'trackList' in entity:
                    items = entity['trackList']
                elif 'tracks' in entity and 'items' in entity['tracks']:
                    items = entity['tracks']['items']
                
                for item in items:
                    t = item.get('track', item)
                    name = t.get('title', t.get('name'))
                    artist = t.get('subtitle', 'Unknown')
                    if not artist or artist == 'Unknown':
                        artist = t.get('artists', [{}])[0].get('name', 'Unknown')
                    
                    if name:
                        tracks_to_download.append(f"{artist} - {name}")
                
                if len(tracks_to_download) == 100:
                    print("⚠️ Note: Spotify's public view limits downloads to 100 tracks.")
                    print("💡 TIP: For larger playlists, you can provide a .txt file list!")
                
                if not tracks_to_download:
                    print("⚠️ Scraped page but found 0 tracks. Is the playlist empty?")
                    return
            else:
                print("⚠️ Could not scrape individual tracks. Falling back to search...")
                tracks_to_download = [url]
        except Exception as e:
            print(f"⚠️ Error reading Spotify: {e}")
            tracks_to_download = [url]
    else:
        # It's a plain search term or YouTube link
        tracks_to_download = [url]

    print(f"🚀 Scalability Mode: Preparing to process {len(tracks_to_download)} tracks...")

    # Process all tracks
    for i, track_query in enumerate(tracks_to_download):
        is_link = track_query.startswith("http")
        
        if not is_link:
            print(f"\n🔍 [{i+1}/{len(tracks_to_download)}] Downloading: {track_query}")
            search_query = f"ytsearch1:{track_query}"
        else:
            print(f"\n🎥 [{i+1}/{len(tracks_to_download)}] Processing Link: {track_query}")
            search_query = track_query

        # Folder management
        if len(tracks_to_download) > 1:
            clean_pname = sanitize_filename(playlist_name)
            output_template = str(PLAYLIST_DIR / clean_pname / f"%(title)s.%(ext)s")
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
            "--no-playlist",
            "--ignore-errors",
            "--trim-filenames", "100"
        ]
        subprocess.run(cmd)

    print(f"\n✅ Playlist processing complete! Check: {PLAYLIST_DIR.absolute()}")

if __name__ == "__main__":
    main()
