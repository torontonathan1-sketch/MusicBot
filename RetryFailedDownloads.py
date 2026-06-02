"""
RetryFailedDownloads.py — Retry watcher for failed track downloads.

Reads failed_downloads.txt, attempts up to N different search strategies
per track, cycles through them one per attempt, and uses smarter/shorter
queries that don't choke YouTube Search.
"""
import json
import os
import re
import subprocess
import time
import random
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import dotenv

MUSIC_ROOT = Path(__file__).parent.absolute()
dotenv.load_dotenv(MUSIC_ROOT / ".env")
POLL_SECONDS = int(os.getenv("RETRY_WATCH_SECONDS", "10"))


# ── helpers ───────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def get_ffmpeg_location() -> Optional[str]:
    import shutil
    try:
        if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
            return None
    except Exception:
        pass
    for p in [r"C:\Users\Steve\.spotdl", r"C:\Users\toron\.spotdl",
              str(MUSIC_ROOT / "ffmpeg"), str(MUSIC_ROOT / "ffmpeg" / "bin")]:
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


def validate_youtube_cookies() -> None:
    cookies_file = os.getenv("YT_COOKIES_FILE", "").strip()
    if cookies_file and not os.path.exists(cookies_file):
        print(f"[cookies] YT_COOKIES_FILE points to a missing file: {cookies_file}")
    if cookies_file and os.path.exists(cookies_file):
        try:
            text = Path(cookies_file).read_text(encoding="utf-8", errors="ignore")
            if ".youtube.com" not in text and "youtube.com" not in text:
                print(f"[cookies] {cookies_file} exists, but it does not look like YouTube cookies.")
        except Exception:
            pass
    if not get_cookies_args():
        print("[cookies] No YouTube cookies configured. Age/anti-bot failures will be listed, not bypassed.")


def find_yt_dlp() -> str:
    from shutil import which
    for c in ["yt-dlp", "yt-dlp.exe"]:
        if which(c):
            return c
    return "yt-dlp"


def simplify_title(title: str) -> str:
    """Strip feat. clauses, parenthetical subtitles, and punctuation noise."""
    # Remove feat. and with. clauses
    t = re.sub(r"\s*\(?(feat\.?|ft\.?|with\.?)\s+[^)]*\)?", "", title, flags=re.IGNORECASE)
    # Remove parenthetical suffixes like (Live), (Remix), etc.
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def shorten_album(album: str) -> str:
    """Take just the first meaningful word chunk of a long album title."""
    # Strip edition/deluxe/live etc. suffixes
    a = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*$", "", album)
    for kw in ["deluxe", "expanded", "bonus", "remastered", "anniversary", "edition",
                "version", "international", "complete", "original", "soundtrack"]:
        a = re.sub(rf"\b{kw}\b", "", a, flags=re.IGNORECASE)
    a = re.sub(r"[^\w\s]", " ", a)
    a = " ".join(a.split())
    # Cap at 5 words so the query doesn't get too long
    words = a.split()
    return " ".join(words[:5])


def build_queries(artist: str, album: str, track: str) -> list[str]:
    """Build a list of progressively simpler search queries to try in order."""
    clean_artist = artist.replace('"', '').replace(':', ' ').strip()
    clean_track  = track.replace('"', '').replace(':', ' ').strip()
    short_album  = shorten_album(album)
    simple_track = simplify_title(track)

    queries = []
    # Most specific first
    if simple_track != clean_track:
        queries.append(f"ytsearch5:{clean_artist} {simple_track} {short_album}")
    queries.append(f"ytsearch5:{clean_artist} {simple_track}")
    queries.append(f"ytsearch5:{clean_artist} {clean_track}")
    if short_album:
        queries.append(f"ytsearch5:{clean_artist} {simple_track} {short_album}")
    queries.append(f"ytsearch5:{simple_track} {clean_artist}")
    # Last resort — just the simplified title
    queries.append(f"ytsearch3:{simple_track}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        q_norm = " ".join(q.split())
        if q_norm not in seen:
            seen.add(q_norm)
            unique.append(q_norm)
    return unique


def pick_best_candidate(query: str, artist_name: str, track_title: str) -> Optional[str]:
    """
    Run yt-dlp --dump-single-json on the query, score each result,
    and return the best YouTube URL. Returns None on failure.
    """
    yt_dlp = find_yt_dlp()
    search_cmd = [
        yt_dlp, "--no-config-locations",
        "--dump-single-json", "--default-search", "ytsearch",
        "--no-warnings",
        query,
    ]
    search_cmd.extend(get_cookies_args())
    try:
        res = subprocess.run(search_cmd, capture_output=True, text=True, timeout=60)
        if not res.stdout.strip():
            return None
        payload = json.loads(res.stdout)
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        if not entries:
            return None

        expected_norm = track_title.lower()
        artist_norm   = artist_name.lower()
        bad_kw = {"spanish", "español", "espanol", "traducida", "traducido",
                  "cover", "parody", "tribute", "karaoke"}

        best_entry, best_score = None, -9999.0
        for e in entries:
            if not e or not isinstance(e, dict):
                continue
            vid = e.get("id")
            if not vid:
                continue
            title   = (e.get("title") or "").lower()
            channel = (e.get("channel") or "").lower()
            score   = 0.0

            for kw in bad_kw:
                if kw in title and kw not in expected_norm:
                    score -= 50.0

            if artist_norm in title:   score += 15.0
            if artist_norm in channel: score += 10.0
            if "topic" in channel:     score += 5.0

            t_words = set(re.sub(r"[^\w\s]", " ", expected_norm).split())
            v_words = set(re.sub(r"[^\w\s]", " ", title).split())
            if t_words:
                score += len(t_words & v_words) / len(t_words) * 25.0

            if score > best_score:
                best_score, best_entry = score, e

        if best_entry and best_score > -10.0:
            return f"https://www.youtube.com/watch?v={best_entry['id']}"
        first_id = entries[0].get("id") if entries else None
        if first_id:
            return f"https://www.youtube.com/watch?v={first_id}"
    except Exception as ex:
        print(f"    [search error] {ex}")
    return None


# ── core retry ────────────────────────────────────────────────────────────────

@dataclass
class RetryResult:
    ok: bool
    last_error: str = ""


def retry_track(artist: str, album: str, track: str) -> RetryResult:
    yt_dlp     = find_yt_dlp()
    ffmpeg_loc = get_ffmpeg_location()
    output_dir = MUSIC_ROOT / sanitize_filename(artist) / sanitize_filename(album)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_title  = sanitize_filename(track)
    output_path = output_dir / f"{safe_title}.%(ext)s"
    last_error  = "Download failed (no output file created)"

    queries = build_queries(artist, album, track)

    for attempt, query_seed in enumerate(queries, start=1):
        # Resolve to a direct URL
        url = pick_best_candidate(query_seed, artist, track)
        if not url:
            url = query_seed

        cmd = [
            yt_dlp, "--no-config-locations",
            url,
            "--no-playlist",
            "--format",       "bestaudio/best",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality","4",
            "--output",        str(output_path),
            "--add-metadata",
            "--postprocessor-args",
            (f"ffmpeg:-metadata artist={artist!r} "
             f"-metadata album_artist={artist!r} "
             f"-metadata album={album!r} "
             f"-metadata title={track!r} "
             f"-id3v2_version 3"),
            "--ignore-errors",
            "--no-warnings",
            "--trim-filenames","100",
            "--sleep-interval","2",
            "--max-sleep-interval","5",
        ]
        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])
        cmd.extend(get_cookies_args())

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            combined = (res.stderr or "") + "\n" + (res.stdout or "")
            for line in combined.splitlines():
                if "error" in line.lower() or "warning" in line.lower():
                    last_error = line.strip()[:500]
                    break
        except Exception as e:
            last_error = str(e)
            print(f"    error: {last_error}")
            continue

        time.sleep(random.uniform(1.5, 3.5))

        # Check success
        if any(output_dir.glob(f"{safe_title}*.mp3")):
            return RetryResult(ok=True)

        lower_error = last_error.lower()
        if any(marker in lower_error for marker in ("sign in", "not a bot", "confirm your age", "age-restricted")):
            break

    return RetryResult(ok=False, last_error=last_error)


# ── main ─────────────────────────────────────────────────────────────────────

def parse_failed_line(line: str) -> Optional[dict]:
    parts = [p.strip() for p in line.split(" | ")]
    data = {}
    for part in parts:
        if ": " not in part:
            continue
        key, value = part.split(": ", 1)
        data[key.strip().lower()] = value.strip()
    artist = data.get("artist")
    track  = data.get("track")
    if not artist or not track:
        return None
    return {"artist": artist, "album": data.get("album", "Unknown Album"), "track": track}


def load_failed_entries(failed_file: Path) -> list[dict]:
    """Read failed_downloads.txt, deduplicate by full destination, and keep source lines."""
    if not failed_file.exists():
        return []
    seen = set()
    entries = []
    for line in failed_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw_line = line.strip()
        if not raw_line:
            continue
        parsed = parse_failed_line(raw_line)
        if not parsed:
            continue
        key = (
            parsed["artist"].lower(),
            parsed.get("album", "").lower(),
            parsed["track"].lower(),
        )
        if key not in seen:
            seen.add(key)
            parsed["raw_line"] = raw_line
            parsed["key"] = key
            entries.append(parsed)
    return entries


def remove_fixed_entries(failed_file: Path, fixed_lines: set[str]) -> None:
    if not failed_file.exists() or not fixed_lines:
        return
    lines = failed_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    remaining = [line for line in lines if line.strip() not in fixed_lines]
    failed_file.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")


def write_retry_line(path: Path, prefix: str, artist: str, album: str, track: str, error: str = "") -> None:
    clean_error = " ".join((error or "").replace("|", "/").split())[:500]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        if clean_error:
            f.write(f"{prefix} | Time: {stamp} | Artist: {artist} | Album: {album} | Track: {track} | Error: {clean_error}\n")
        else:
            f.write(f"{prefix} | Time: {stamp} | Artist: {artist} | Album: {album} | Track: {track}\n")


def process_entries(entries: list[dict], attempted: set[tuple[str, str, str]], failed_file: Path) -> int:
    retry_log = MUSIC_ROOT / "retry_failed_downloads.log"
    still_failed = MUSIC_ROOT / "failed_downloads_retry.txt"
    fixed_lines: set[str] = set()
    fixed = 0

    pending = [entry for entry in entries if entry["key"] not in attempted]
    for idx, entry in enumerate(pending, start=1):
        artist = entry["artist"]
        album = entry["album"]
        track = entry["track"]
        print(f"[{idx}/{len(pending)}] Retrying: {artist} - {track}")
        attempted.add(entry["key"])

        result = retry_track(artist, album, track)
        if result.ok:
            fixed += 1
            fixed_lines.add(entry["raw_line"])
            write_retry_line(retry_log, "FIXED", artist, album, track)
            print("  fixed")
        else:
            write_retry_line(still_failed, "STILL_FAILED", artist, album, track, result.last_error)
            print(f"  still failed: {result.last_error}")

    remove_fixed_entries(failed_file, fixed_lines)
    return fixed


def main() -> None:
    failed_file = MUSIC_ROOT / "failed_downloads.txt"
    once = "--once" in os.sys.argv
    validate_youtube_cookies()

    attempted: set[tuple[str, str, str]] = set()
    total_fixed = 0

    if once:
        entries = load_failed_entries(failed_file)
        if not entries:
            print("No failed downloads to retry.")
            return
        total_fixed += process_entries(entries, attempted, failed_file)
        print(f"Done. Fixed {total_fixed}/{len(entries)} tracks.")
        return

    print("Watching failed_downloads.txt for new failures. Press Ctrl+C to stop.")
    try:
        while True:
            entries = load_failed_entries(failed_file)
            new_entries = [entry for entry in entries if entry["key"] not in attempted]
            if new_entries:
                total_fixed += process_entries(entries, attempted, failed_file)
                print(f"Retry watcher running. Fixed so far: {total_fixed}")
            time.sleep(max(POLL_SECONDS, 6))
    except KeyboardInterrupt:
        print(f"\nRetry watcher stopped. Fixed this session: {total_fixed}")


if __name__ == "__main__":
    main()
