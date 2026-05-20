import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import dotenv

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


def get_cookies_args() -> list[str]:
    """Prefer cookie file auth; browser cookies are optional."""
    cookies_file = os.getenv("YT_COOKIES_FILE", "").strip()
    if cookies_file and os.path.exists(cookies_file):
        return ["--cookies", cookies_file]

    if os.getenv("YT_ENABLE_BROWSER_COOKIES", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return []

    browser = os.getenv("YT_COOKIES_FROM", "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []


def main() -> None:
    if len(sys.argv) < 2:
        print("Please provide a playlist URL, YouTube URL, search query, or a .txt file path.")
        return

    url = sys.argv[1]
    if "spotify.com" in url:
        print("Spotify input has been removed from this bot. Use a .txt track list or YouTube link.")
        return

    music_root = Path(__file__).parent.absolute()
    playlist_dir = music_root / "Playlists"
    playlist_dir.mkdir(exist_ok=True)

    tracks_to_download: list[str] = []
    input_path = Path(url.strip('"'))

    if input_path.suffix == ".txt" and input_path.exists():
        print(f"\nText file detected: {input_path.name}")
        with open(input_path, "r", encoding="utf-8") as f:
            tracks_to_download = [line.strip() for line in f if line.strip()]
        playlist_name = sanitize_filename(input_path.stem)
    else:
        tracks_to_download = [url]
        playlist_name = "Manual Input"

    print(f"Preparing to process {len(tracks_to_download)} track(s)...")

    for i, track_query in enumerate(tracks_to_download, start=1):
        is_link = track_query.startswith("http")
        if not is_link:
            clean_q = track_query.replace('"', "").replace(":", " ")
            search_query = f"ytsearch1:{clean_q}"
            print(f"[{i}/{len(tracks_to_download)}] Downloading: {track_query}")
        else:
            search_query = track_query
            print(f"[{i}/{len(tracks_to_download)}] Processing URL: {track_query}")

        output_template = str(playlist_dir / playlist_name / "%(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-config-locations",
            search_query,
            "--default-search",
            "ytsearch",
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
        ]

        ffmpeg_loc = get_ffmpeg_location()
        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])

        cmd.extend(get_cookies_args())
        subprocess.run(cmd)

    print(f"\nDone. Check: {playlist_dir.absolute()}")


if __name__ == "__main__":
    main()
