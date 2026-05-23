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


_warned_missing_cookies = False

def get_cookies_args() -> list:
    global _warned_missing_cookies
    """Prefer cookie file auth; optionally allow browser cookies only when explicitly enabled."""
    cookies_file = os.getenv("YT_COOKIES_FILE", "").strip()
    if cookies_file:
        if os.path.exists(cookies_file):
            return ["--cookies", cookies_file]
        elif not _warned_missing_cookies:
            print(f"[WARNING] YT_COOKIES_FILE is configured but file not found: {cookies_file}")
            print("[ACTION REQUIRED] To resolve: Export YouTube cookies to this file, or enable browser cookies in your .env.")
            _warned_missing_cookies = True

    if os.getenv("YT_ENABLE_BROWSER_COOKIES", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return []

    browser = os.getenv("YT_COOKIES_FROM", "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []


def append_age_restricted_playlist_track(music_root: Path, playlist_name: str, track_query: str, error: str):
    age_file = music_root / "age_restricted_tracks.txt"
    with open(age_file, "a", encoding="utf-8") as f:
        f.write(
            f"Source: PlaylistDownloader | Playlist: {playlist_name} | Track: {track_query} | Error: {error}\n"
        )
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
    # Normalize Unicode spacing and punctuation noise for more reliable searching.
    clean_q = (
        (track_query or "")
        .replace("\u00A0", " ")
        .replace("\u202F", " ")
        .replace('"', "")
        .replace(":", " ")
    )
    clean_q = re.sub(r"\s+", " ", clean_q).strip()
    search_query = f"ytsearch6:{clean_q}"
    cmd = [
        "yt-dlp",
        "--no-config-locations",
        "--dump-single-json",
        "--default-search",
        "ytsearch",
        search_query,
    ]
    cmd.extend(get_cookies_args())
    res = subprocess.run(cmd, capture_output=True, text=True)
    # yt-dlp may return nonzero while still printing usable JSON entries.
    if not res.stdout.strip():
        return None

    try:
        data = json.loads(res.stdout)
    except Exception:
        return None

    entries = data.get("entries", []) if isinstance(data, dict) else []
    for e in entries:
        if not e or not isinstance(e, dict):
            continue
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
                # Last-resort fallback: direct query download path (don't skip the track).
                fallback_q = (
                    (track_query or "")
                    .replace("\u00A0", " ")
                    .replace("\u202F", " ")
                    .replace('"', "")
                    .replace(":", " ")
                )
                fallback_q = re.sub(r"\s+", " ", fallback_q).strip()
                source_url = f"ytsearch1:{fallback_q}"
                print(f"Resolver fallback for: {track_query}")

        clean_pname = sanitize_filename(playlist_name)
        output_template = str(playlist_dir / clean_pname / f"{i:03d} - %(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-config-locations",
            "--extractor-retries",
            "3",
            "--retries",
            "3",
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

        cmd.extend(get_cookies_args())

        res = subprocess.run(cmd, capture_output=True, text=True)
        combined_output = (res.stderr or "") + "\n" + (res.stdout or "")
        lower_out = combined_output.lower()

        if "could not copy chrome cookie database" in lower_out or "lockprofilecookiedatabase" in lower_out:
            print("\n[ERROR] Chrome cookie database is locked because Chrome is currently running!")
            print("[ACTION REQUIRED] To fix this: CLOSE Chrome completely and re-run this script, OR export your YouTube cookies to D:\\Music\\cookies.txt\n")

        if (
            "sign in to confirm your age" in lower_out
            or "inappropriate for some users" in lower_out
            or "age-restricted" in lower_out
            or "age restricted" in lower_out
            or "sign in to confirm you’re not a bot" in lower_out
        ):
            extended_error = combined_output.strip()
            if "could not copy chrome cookie database" in lower_out:
                extended_error += "\n[Action Required] Chrome cookie database was locked (Chrome open). Close Chrome or use Netscape format cookies.txt."
            elif "not a bot" in lower_out or "confirm your age" in lower_out:
                extended_error += "\n[Action Required] YouTube anti-bot/age wall hit. Please configure cookies.txt to bypass."
            append_age_restricted_playlist_track(music_root, playlist_name, track_query, extended_error)

    print(f"Playlist processing complete! Check: {playlist_dir.absolute()}")


if __name__ == "__main__":
    main()
