import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import dotenv
import requests

# Load environment variables
dotenv.load_dotenv(Path(__file__).parent.absolute() / ".env")


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def get_ffmpeg_location() -> Optional[str]:
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


def fetch_spotify_tracks(url: str) -> tuple[list[str], str]:
    playlist_id = url.split('/')[-1].split('?')[0]
    tracks_to_download: list[str] = []
    playlist_name = "Unknown Playlist"

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    api_success = False

    if client_id and client_secret:
        print("Spotify API credentials detected. Fetching entire playlist via Spotify API...")
        try:
            auth_response = requests.post(
                "https://accounts.spotify.com/api/token",
                {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=10,
            )
            access_token = auth_response.json().get("access_token")
            if access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                meta_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
                r_meta = requests.get(meta_url, headers=headers, timeout=10)
                if r_meta.status_code == 200:
                    playlist_name = r_meta.json().get("name", "Unknown Playlist")
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
                    api_success = True
        except Exception as e:
            print(f"Spotify API error: {e}. Falling back to public web scraper...")

    if not api_success:
        print("Fetching tracks via public web player scraper (limits downloads to 100)...")
        embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
        r = requests.get(embed_url, timeout=10)
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
        if not match:
            return [url], playlist_name
        data = json.loads(match.group(1))
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
        playlist_name = entity.get("name", entity.get("title", "Unknown Playlist"))
        items = entity.get("trackList") or entity.get("tracks", {}).get("items", [])
        for item in items:
            t = item.get("track", item)
            name = t.get("title", t.get("name"))
            artist = t.get("subtitle", "Unknown")
            if not artist or artist == "Unknown":
                artist = t.get("artists", [{}])[0].get("name", "Unknown")
            if name:
                tracks_to_download.append(f"{artist} - {name}")

    return tracks_to_download, playlist_name


def pick_video_url(track_query: str, used_ids: set[str]) -> Optional[str]:
    clean_q = track_query.replace('"', "").replace(":", " ")
    search_query = f"ytsearch6:{clean_q}"
    cmd = [
        "yt-dlp",
        "--no-config-locations",
        "--dump-single-json",
        "--default-search",
        "ytsearch",
        search_query,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        return None

    try:
        data = json.loads(res.stdout)
    except Exception:
        return None

    entries = data.get("entries", []) if isinstance(data, dict) else []
    for e in entries:
        vid = e.get("id")
        if not vid or vid in used_ids:
            continue
        used_ids.add(vid)
        return f"https://www.youtube.com/watch?v={vid}"
    return None


def main() -> None:
    if len(sys.argv) < 2:
        print("Please provide a playlist URL.")
        return

    url = sys.argv[1]
    music_root = Path(__file__).parent.absolute()
    playlist_dir = music_root / "Playlists"
    playlist_dir.mkdir(exist_ok=True)

    input_path = Path(url.strip('"'))
    if input_path.suffix == ".txt" and input_path.exists():
        with open(input_path, "r", encoding="utf-8") as f:
            tracks_to_download = [line.strip() for line in f if line.strip()]
        playlist_name = input_path.stem
    elif "spotify.com" in url:
        print("Spotify link detected! Resolving tracks...")
        tracks_to_download, playlist_name = fetch_spotify_tracks(url)
    else:
        tracks_to_download = [url]
        playlist_name = "Manual Input"

    print(f"Preparing to process {len(tracks_to_download)} tracks...")
    ffmpeg_loc = get_ffmpeg_location()
    used_video_ids: set[str] = set()

    for i, track_query in enumerate(tracks_to_download, start=1):
        is_link = track_query.startswith("http")
        print(f"[{i}/{len(tracks_to_download)}] {track_query}")

        if is_link:
            source_url = track_query
        else:
            source_url = pick_video_url(track_query, used_video_ids)
            if not source_url:
                print(f"Could not resolve video for: {track_query}")
                continue

        clean_pname = sanitize_filename(playlist_name)
        output_template = str(playlist_dir / clean_pname / f"{i:03d} - %(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-config-locations",
            source_url,
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "4",
            "--output",
            output_template,
            "--add-metadata",
            "--postprocessor-args",
            "ffmpeg:-id3v2_version 3",
            "--no-playlist",
            "--ignore-errors",
            "--trim-filenames",
            "100",
            "--no-overwrites",
        ]

        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])

        subprocess.run(cmd)

    print(f"Playlist processing complete! Check: {playlist_dir.absolute()}")


if __name__ == "__main__":
    main()
