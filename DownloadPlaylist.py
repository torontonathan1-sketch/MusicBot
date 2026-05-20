import sys
import subprocess
import re
import os
from pathlib import Path
import dotenv

# Load environment variables
dotenv.load_dotenv(Path(__file__).parent.absolute() / ".env")

def sanitize_filename(name: str) -> str:
    """Remove characters illegal in Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()

def get_ffmpeg_location() -> Optional[str]:
    """Smart helper to find FFmpeg. If installed globally, returns None (allowing yt-dlp to find it automatically)."""
    import shutil
    from typing import Optional
    try:
        if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
            return None
    except:
        pass

    MUSIC_ROOT = Path(__file__).parent.absolute()
    common_paths = [
        r"C:\Users\Steve\.spotdl",
        r"C:\Users\toron\.spotdl",
        str(MUSIC_ROOT / "ffmpeg"),
        str(MUSIC_ROOT / "ffmpeg" / "bin"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p
    return None

def get_cookies_args() -> list:
    """Prefer cookie file auth; optionally allow browser cookies only when explicitly enabled."""
    cookies_file = os.getenv("YT_COOKIES_FILE", "").strip()
    if cookies_file and os.path.exists(cookies_file):
        return ["--cookies", cookies_file]

    if os.getenv("YT_ENABLE_BROWSER_COOKIES", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return []

    browser = os.getenv("YT_COOKIES_FROM", "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []
    browser = os.getenv("YT_COOKIES_FROM", "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []

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
    tracks_to_download = []
    input_path = Path(url.strip('"'))
    if input_path.suffix == ".txt" and input_path.exists():
        print(f"\n📄 Text file detected! Reading tracks from: {input_path.name}")
        with open(input_path, "r", encoding="utf-8") as f:
            tracks_to_download = [line.strip() for line in f if line.strip()]
        playlist_name = input_path.stem
        print(f"✨ Loaded {len(tracks_to_download)} tracks from file.")
    elif "spotify.com" in url:\n        print("Spotify input has been removed from this bot. Use a .txt track list or YouTube link.")\n        return\n    else:\n        # It's a plain search term or YouTube link
        tracks_to_download = [url]

    print(f"🚀 Scalability Mode: Preparing to process {len(tracks_to_download)} tracks...")

    # Process all tracks
    for i, track_query in enumerate(tracks_to_download):
        is_link = track_query.startswith("http")
        
        # Smart skip check: If file already exists in playlist directory
        if not is_link and len(tracks_to_download) > 1:
            clean_pname = sanitize_filename(playlist_name)
            target_dir = PLAYLIST_DIR / clean_pname
            if target_dir.exists():
                # Extract the track name part from "Artist - Track Name"
                parts = track_query.split(" - ", 1)
                track_name = parts[1] if len(parts) > 1 else track_query
                track_clean = sanitize_filename(track_name).lower()
                
                exists = False
                for f in target_dir.glob("*.mp3"):
                    if track_clean in f.name.lower():
                        exists = True
                        break
                if exists:
                    print(f"⏭️ [{i+1}/{len(tracks_to_download)}] Already downloaded, skipping: {track_query}")
                    continue

        if not is_link:
            clean_q = track_query.replace('"', '').replace(':', ' ')
            search_query = f"ytsearch1:{clean_q}"
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
            "--no-config-locations",
            search_query,
            "--default-search", "ytsearch",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "4",
        ]
        ffmpeg_loc = get_ffmpeg_location()
        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])
        cmd.extend(get_cookies_args())

        cmd.extend([
            "--output", output_template,
            "--add-metadata",
            "--postprocessor-args", "ffmpeg:-id3v2_version 3",
            "--no-playlist",
            "--ignore-errors",
            "--trim-filenames", "100"
        ])
        subprocess.run(cmd)

    print(f"\n✅ Playlist processing complete! Check: {PLAYLIST_DIR.absolute()}")

if __name__ == "__main__":
    main()
