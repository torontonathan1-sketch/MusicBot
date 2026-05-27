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

SPECIAL_VERSION_KEYWORDS = {
    "live", "acoustic", "instrumental", "karaoke", "remix", "remastered",
    "sped up", "slowed", "version", "edit", "radio", "mono", "stereo",
    "demo", "cover", "feat", "ft", "from", "soundtrack", "original motion picture",
}


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def normalize_text(text: str) -> str:
    text = (text or "").lower().replace("\u00A0", " ").replace("\u202F", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_set(text: str) -> set[str]:
    return {w for w in normalize_text(text).split() if len(w) > 1}


def parse_track_query(track_query: str) -> tuple[str, str]:
    parts = track_query.split(" - ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", track_query.strip()


def strip_version_noise(title: str) -> str:
    t = normalize_text(title)
    # Remove common edition/version noise for better resolver matching.
    t = re.sub(r"\b(remaster(ed)?|remastered \d{2,4}|radio edit|mono|stereo|official (video|audio|lyric video)|visualizer|from .+)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_special_version(title: str) -> bool:
    t = normalize_text(title)
    return any(k in t for k in SPECIAL_VERSION_KEYWORDS)


def title_similarity(expected: str, actual: str) -> float:
    a = token_set(expected)
    b = token_set(actual)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a))


def should_replace_download(expected_title: str, actual_title: str) -> bool:
    sim = title_similarity(expected_title, actual_title)
    if is_special_version(expected_title):
        return sim < 0.30
    return sim < 0.45


def find_downloaded_mp3_for_index(output_dir: Path, idx: int) -> Optional[Path]:
    prefix = f"{idx:03d} - "
    matches = sorted([p for p in output_dir.glob("*.mp3") if p.name.startswith(prefix)])
    return matches[-1] if matches else None


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
    cookies_file = os.getenv("YT_COOKIES_FILE", "").strip()
    if cookies_file:
        if os.path.exists(cookies_file):
            return ["--cookies", cookies_file]
        if not _warned_missing_cookies:
            print(f"[WARNING] YT_COOKIES_FILE is configured but file not found: {cookies_file}")
            print("[ACTION REQUIRED] Export YouTube cookies to this file, or enable browser cookies in your .env.")
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
                    # Only treat API path as successful when it actually yields tracks.
                    api_success = len(tracks_to_download) > 0
                    if not api_success:
                        print("Spotify API returned 0 tracks for this playlist. Falling back to public web scraper...")
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


def pick_video_url(track_query: str, blocked_ids: set[str]) -> tuple[Optional[str], Optional[str]]:
    artist, title = parse_track_query(track_query)
    clean_q = normalize_text(track_query).replace('"', "").replace(":", " ")
    clean_q = re.sub(r"\s+", " ", clean_q).strip()

    queries = [
        f"{artist} {title} official audio".strip(),
        f"{artist} {strip_version_noise(title)} audio".strip(),
        clean_q,
    ]

    expected_tokens = token_set(f"{artist} {strip_version_noise(title)}")
    if not expected_tokens:
        expected_tokens = token_set(clean_q)

    best_url = None
    best_vid = None
    best_score = -1.0

    for q in queries:
        if not q:
            continue
        search_query = f"ytsearch8:{q}"
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
        if not res.stdout.strip():
            continue

        try:
            data = json.loads(res.stdout)
        except Exception:
            continue

        entries = data.get("entries", []) if isinstance(data, dict) else []
        for e in entries:
            if not e or not isinstance(e, dict):
                continue
            vid = e.get("id")
            if not vid or vid in blocked_ids:
                continue
            cand_title = e.get("title") or ""
            cand_tokens = token_set(strip_version_noise(cand_title))
            if not cand_tokens:
                continue

            overlap = len(expected_tokens & cand_tokens) / max(1, len(expected_tokens))
            score = overlap
            # Prefer music-oriented uploads over obvious live/covers for normal tracks.
            lowered = normalize_text(cand_title)
            if "official audio" in lowered:
                score += 0.12
            if "topic" in normalize_text(str(e.get("channel") or "")):
                score += 0.08
            if not is_special_version(title):
                if "live" in lowered:
                    score -= 0.2
                if "cover" in lowered:
                    score -= 0.2

            if score > best_score:
                best_score = score
                best_url = f"https://www.youtube.com/watch?v={vid}"
                best_vid = vid

    if best_score >= 0.35:
        return best_url, best_vid
    return None, None


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

    clean_pname = sanitize_filename(playlist_name)
    output_dir = playlist_dir / clean_pname
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, track_query in enumerate(tracks_to_download, start=1):
        is_link = track_query.startswith("http")
        print(f"[{i}/{len(tracks_to_download)}] {track_query}")

        if is_link:
            source_url = track_query
            source_video_id = None
            attempts = 1
            expected_title = ""
        else:
            _, expected_title = parse_track_query(track_query)
            attempts = 4
            source_url = None
            source_video_id = None
            blocked_ids = set(used_video_ids)

        downloaded_ok = False
        for _attempt in range(attempts):
            if not is_link:
                source_url, source_video_id = pick_video_url(track_query, blocked_ids)
                if not source_url:
                    fallback_q = normalize_text(track_query).replace('"', "").replace(":", " ")
                    fallback_q = re.sub(r"\s+", " ", fallback_q).strip()
                    source_url = f"ytsearch1:{fallback_q}"
                    source_video_id = None
                    print(f"Resolver fallback for: {track_query}")

            output_template = str(output_dir / f"{i:03d} - %(title)s.%(ext)s")
            cmd = [
                "yt-dlp",
                "--no-config-locations",
                "--extractor-retries", "3",
                "--retries", "3",
                source_url,
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "4",
                "--output", output_template,
                "--add-metadata",
                "--postprocessor-args", "ffmpeg:-id3v2_version 3",
                "--no-playlist",
                "--ignore-errors",
                "--trim-filenames", "100",
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
                print("[ACTION REQUIRED] CLOSE Chrome, or export YouTube cookies to D:\\Music\\cookies.txt\n")

            if (
                "sign in to confirm your age" in lower_out
                or "inappropriate for some users" in lower_out
                or "age-restricted" in lower_out
                or "age restricted" in lower_out
                or "sign in to confirm you\u2019re not a bot" in lower_out
                or "sign in to confirm you're not a bot" in lower_out
            ):
                extended_error = combined_output.strip()
                if "could not copy chrome cookie database" in lower_out:
                    extended_error += "\n[Action Required] Chrome cookie database was locked (Chrome open). Close Chrome or use Netscape format cookies.txt."
                else:
                    extended_error += "\n[Action Required] YouTube anti-bot/age wall hit. Please configure cookies.txt to bypass."
                append_age_restricted_playlist_track(music_root, playlist_name, track_query, extended_error)

            downloaded_file = find_downloaded_mp3_for_index(output_dir, i)
            if not downloaded_file:
                if source_video_id:
                    blocked_ids.add(source_video_id)
                continue

            if is_link:
                downloaded_ok = True
                break

            actual_title = re.sub(r"^\d{3}\s*-\s*", "", downloaded_file.stem).strip()
            if should_replace_download(expected_title, actual_title):
                print(f"Replacing low-confidence match: expected '{expected_title}' got '{actual_title}'")
                try:
                    downloaded_file.unlink()
                except Exception:
                    pass
                if source_video_id:
                    blocked_ids.add(source_video_id)
                continue

            downloaded_ok = True
            if source_video_id:
                used_video_ids.add(source_video_id)
            break

        if not downloaded_ok:
            print(f"Could not resolve a stable match after retries: {track_query}")

    print(f"Playlist processing complete! Check: {playlist_dir.absolute()}")


if __name__ == "__main__":
    main()
