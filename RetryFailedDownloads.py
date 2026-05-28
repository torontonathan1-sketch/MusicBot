import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import dotenv


MUSIC_ROOT = Path(__file__).parent.absolute()
dotenv.load_dotenv(MUSIC_ROOT / ".env")


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def get_ffmpeg_location() -> Optional[str]:
    import shutil

    try:
        if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
            return None
    except Exception:
        pass

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


def get_cookies_args() -> list[str]:
    cookies_file = os.getenv("YT_COOKIES_FILE", "").strip()
    if cookies_file and os.path.exists(cookies_file):
        return ["--cookies", cookies_file]

    if os.getenv("YT_ENABLE_BROWSER_COOKIES", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return []

    browser = os.getenv("YT_COOKIES_FROM", "").strip()
    if browser:
        return ["--cookies-from-browser", browser]
    return []


def find_yt_dlp() -> str:
    from shutil import which

    for candidate in ["yt-dlp", "yt-dlp.exe"]:
        if which(candidate):
            return candidate
    return "yt-dlp"


def parse_failed_download_line(line: str) -> Optional[dict]:
    parts = [p.strip() for p in line.split(" | ")]
    data = {}
    for part in parts:
        if ": " not in part:
            continue
        key, value = part.split(": ", 1)
        data[key.strip().lower()] = value.strip()

    artist = data.get("artist")
    album = data.get("album")
    track = data.get("track")
    if not artist or not track:
        return None
    return {"artist": artist, "album": album or "Unknown Album", "track": track, "error": data.get("error", "")}


def simplify_title(title: str) -> str:
    base = title.split(":", 1)[0].strip()
    base = re.sub(r"\b(op\.?|no\.?|nr\.?)\s*", "", base, flags=re.IGNORECASE)
    base = re.sub(r"[^\w\s]", " ", base)
    return " ".join(base.split())


def build_queries(artist: str, album: str, track: str) -> list[str]:
    clean_title = track.replace('"', "").replace(":", " ")
    clean_album = album.replace('"', "").replace(":", " ")
    clean_artist = artist.replace('"', "").replace(":", " ")
    title_simple = simplify_title(track)
    return [
        f"ytsearch5:{clean_artist} {clean_title} {clean_album}",
        f"ytsearch5:{clean_artist} {title_simple} {clean_album}",
        f"ytsearch5:{clean_artist} {title_simple}",
    ]


@dataclass
class RetryResult:
    ok: bool
    last_error: str = ""


def retry_track(artist: str, album: str, track: str, attempts: int = 3) -> RetryResult:
    ffmpeg_loc = get_ffmpeg_location()
    yt_dlp = find_yt_dlp()
    output_dir = MUSIC_ROOT / sanitize_filename(artist) / sanitize_filename(album)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title = sanitize_filename(track)
    output_path = output_dir / f"{safe_title}.%(ext)s"
    last_error = "Download failed (no output file created)"

    for attempt in range(1, attempts + 1):
        for query in build_queries(artist, album, track):
            print(f"  attempt {attempt}/{attempts}: {query}")
            cmd = [
                yt_dlp,
                "--no-config-locations",
                query,
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "4",
                "--output", str(output_path),
                "--add-metadata",
                "--postprocessor-args",
                f"ffmpeg:-metadata artist={artist!r} -metadata album_artist={artist!r} -metadata album={album!r} -metadata title={track!r} -id3v2_version 3",
                "--ignore-errors",
                "--no-warnings",
                "--trim-filenames", "100",
                "--sleep-interval", "2",
                "--max-sleep-interval", "5",
                "--user-agent",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
                "--force-ipv4",
            ]
            if ffmpeg_loc:
                cmd.extend(["--ffmpeg-location", ffmpeg_loc])
            cmd.extend(get_cookies_args())

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            except Exception as e:
                last_error = str(e)
                print(f"    error: {last_error}")
                continue

            if res.returncode != 0:
                combined = (res.stdout or "") + "\n" + (res.stderr or "")
                last_error = combined.strip() or f"yt-dlp exited {res.returncode}"
                print(f"    yt-dlp exit {res.returncode}")
                continue

            if any(output_dir.glob(f"{safe_title}*.mp3")):
                print(f"    saved: {output_dir}")
                return RetryResult(ok=True)

            last_error = "Download failed (no output file created)"
            print(f"    no output yet")

    return RetryResult(ok=False, last_error=last_error)


def main() -> None:
    failed_file = MUSIC_ROOT / "failed_downloads.txt"
    if not failed_file.exists():
        print(f"Missing failed downloads file: {failed_file}")
        return

    lines = [line.strip() for line in failed_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = []
    for line in lines:
        parsed = parse_failed_download_line(line)
        if parsed:
            entries.append(parsed)

    if not entries:
        print("No parsable failed download entries found.")
        return

    retry_log = MUSIC_ROOT / "retry_failed_downloads.log"
    retried = 0
    fixed = 0
    still_failed = []

    for entry in entries:
        retried += 1
        artist = entry["artist"]
        album = entry["album"]
        track = entry["track"]
        print(f"[{retried}/{len(entries)}] Retrying: {artist} - {track}")
        result = retry_track(artist, album, track, attempts=3)
        if result.ok:
            fixed += 1
            with open(retry_log, "a", encoding="utf-8") as f:
                f.write(f"FIXED | Artist: {artist} | Album: {album} | Track: {track}\n")
        else:
            still_failed.append(f"Artist: {artist} | Album: {album} | Track: {track} | Error: {result.last_error}")

    if still_failed:
        (MUSIC_ROOT / "failed_downloads_retry.txt").write_text("\n".join(still_failed) + "\n", encoding="utf-8")

    print(f"Retry complete. Fixed {fixed}/{len(entries)} tracks.")
    print(f"Output folder: {MUSIC_ROOT}")


if __name__ == "__main__":
    main()
