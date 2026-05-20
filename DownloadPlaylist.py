import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import dotenv
import requests
import json

# Load environment variables
dotenv.load_dotenv(Path(__file__).parent.absolute() / ".env")


def sanitize_filename(name: str) -> str:
    """Remove characters illegal in Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def get_ffmpeg_location() -> Optional[str]:
    """Find FFmpeg path, or return None if globally available."""
    import shutil

    try:
        if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
            return None
    except Exception:
        pass

    music_root = Path(__file__).parent.absolute()
    common_paths = [
        r"C:\Users\Steve\.spotdl",
        r"C:\Users\toron\.spotdl",
        str(music_root / "ffmpeg"),
        str(music_root / "ffmpeg" / "bin"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None


def main() -> None:
    if len(sys.argv) < 2:
        print("Please provide a playlist URL.")
        return

    url = sys.argv[1]
    music_root = Path(__file__).parent.absolute()
    playlist_dir = music_root / "Playlists"
    playlist_dir.mkdir(exist_ok=True)

    tracks_to_download: list[str] = []
    input_path = Path(url.strip('"'))

    # Check if the input is a path to a .txt file
    if input_path.suffix == ".txt" and input_path.exists():
        print(f"\nText file detected! Reading tracks from: {input_path.name}")
        with open(input_path, "r", encoding="utf-8") as f:
            tracks_to_download = [line.strip() for line in f if line.strip()]
        playlist_name = input_path.stem
        print(f"Loaded {len(tracks_to_download)} tracks from file.")
    elif "spotify.com" in url:
        print("\nSpotify link detected! Resolving tracks...")
        playlist_id = url.split('/')[-1].split('?')[0]

        # Check for optional Spotify API credentials
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        api_success = False

        if client_id and client_secret:
            print("Spotify API credentials detected. Fetching entire playlist via Spotify API...")
            try:
                # 1. Authenticate using Client Credentials Flow
                auth_url = "https://accounts.spotify.com/api/token"
                auth_response = requests.post(auth_url, {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }, timeout=10)
                auth_data = auth_response.json()
                access_token = auth_data.get("access_token")

                if access_token:
                    headers = {"Authorization": f"Bearer {access_token}"}

                    # 2. Fetch Playlist Metadata (Name)
                    meta_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
                    r_meta = requests.get(meta_url, headers=headers, timeout=10)
                    if r_meta.status_code == 200:
                        playlist_name = r_meta.json().get("name", "Unknown Playlist")
                        print(f"Found Spotify Playlist via API: '{playlist_name}'")

                        # 3. Paginated track fetching (no 100 limit)
                        tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
                        while tracks_url:
                            r_tracks = requests.get(tracks_url, headers=headers, timeout=10)
                            if r_tracks.status_code != 200:
                                break
                            tracks_data = r_tracks.json()
                            for item in tracks_data.get("items", []):
                                t = item.get("track")
                                if not t:
                                    continue
                                name = t.get("name")
                                artist = t.get("artists", [{}])[0].get("name", "Unknown")
                                if name:
                                    tracks_to_download.append(f"{artist} - {name}")
                            tracks_url = tracks_data.get("next")

                        print(f"Fetched {len(tracks_to_download)} tracks via Spotify API pagination.")
                        api_success = True
            except Exception as e:
                print(f"Spotify API error: {e}. Falling back to public web scraper...")
                tracks_to_download = []

        if not api_success:
            print("Fetching tracks via public web player scraper (limits downloads to 100)...")
            try:
                embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
                r = requests.get(embed_url, timeout=10)

                # Extract the JSON data block
                match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
                if match:
                    data = json.loads(match.group(1))
                    entity = data["props"]["pageProps"]["state"]["data"]["entity"]

                    # Get Playlist Name
                    playlist_name = entity.get("name", entity.get("title", "Unknown Playlist"))
                    print(f"Found Spotify Playlist: '{playlist_name}'")

                    # Get Tracks (Handle multiple JSON structures)
                    items = []
                    if "trackList" in entity:
                        items = entity["trackList"]
                    elif "tracks" in entity and "items" in entity["tracks"]:
                        items = entity["tracks"]["items"]

                    for item in items:
                        t = item.get("track", item)
                        name = t.get("title", t.get("name"))
                        artist = t.get("subtitle", "Unknown")
                        if not artist or artist == "Unknown":
                            artist = t.get("artists", [{}])[0].get("name", "Unknown")

                        if name:
                            tracks_to_download.append(f"{artist} - {name}")

                    if len(tracks_to_download) == 100:
                        print("Note: Spotify public view limits downloads to 100 tracks.")
                        print("TIP: Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to .env to remove this limit.")

                    if not tracks_to_download:
                        print("Scraped page but found 0 tracks. Is the playlist empty?")
                        return
                else:
                    print("Could not scrape individual tracks. Falling back to search...")
                    tracks_to_download = [url]
            except Exception as e:
                print(f"Error reading Spotify: {e}")
                tracks_to_download = [url]
    else:
        # It's a plain search term or YouTube link
        tracks_to_download = [url]
        playlist_name = "Manual Input"

    print(f"Preparing to process {len(tracks_to_download)} tracks...")

    ffmpeg_loc = get_ffmpeg_location()

    # Process all tracks
    for i, track_query in enumerate(tracks_to_download, start=1):
        is_link = track_query.startswith("http")

        if not is_link:
            print(f"\n[{i}/{len(tracks_to_download)}] Downloading: {track_query}")
            clean_q = track_query.replace('"', '').replace(':', ' ')
            search_query = f"ytsearch3:{clean_q}"
        else:
            print(f"\n[{i}/{len(tracks_to_download)}] Processing Link: {track_query}")
            search_query = track_query

        # Folder management
        if len(tracks_to_download) > 1:
            clean_pname = sanitize_filename(playlist_name)
            output_template = str(playlist_dir / clean_pname / f"{i:03d} - %(title)s.%(ext)s")
        else:
            output_template = str(playlist_dir / "%(playlist|Unknown Playlist)s" / "%(playlist_index)02d - %(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-config-locations",
            search_query,
            "--default-search", "ytsearch",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "4",
            "--output", output_template,
            "--add-metadata",
            "--postprocessor-args", "ffmpeg:-id3v2_version 3",
            "--no-playlist",
            "--ignore-errors",
            "--trim-filenames", "100",`r`n            "--no-overwrites",
        ]

        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])

        subprocess.run(cmd)

    print(f"\nPlaylist processing complete! Check: {playlist_dir.absolute()}")


if __name__ == "__main__":
    main()
