import re
from pathlib import Path


MUSIC_ROOT = Path(__file__).parent.absolute()


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def parse_failed_line(line: str) -> dict | None:
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
    if not artist or not album or not track:
        return None
    return {"artist": artist, "album": album, "track": track}


def main() -> None:
    failed_file = MUSIC_ROOT / "failed_downloads.txt"
    if not failed_file.exists():
        print(f"Missing file: {failed_file}")
        return

    lines = [line.strip() for line in failed_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = []
    for line in lines:
        parsed = parse_failed_line(line)
        if parsed:
            entries.append(parsed)

    if not entries:
        print("No parsable entries found.")
        return

    out_file = MUSIC_ROOT / "failed_downloads_clean_list.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        for entry in entries:
            artist = entry["artist"]
            album = entry["album"]
            track = entry["track"]
            dest = MUSIC_ROOT / sanitize_filename(artist) / sanitize_filename(album) / f"{sanitize_filename(track)}.mp3"
            f.write(f"{artist} | {album} | {track} | {dest}\n")

    print(f"Wrote {len(entries)} clean entries to: {out_file}")
    for entry in entries[:20]:
        artist = entry["artist"]
        album = entry["album"]
        track = entry["track"]
        dest = MUSIC_ROOT / sanitize_filename(artist) / sanitize_filename(album) / f"{sanitize_filename(track)}.mp3"
        print(f"{artist} -> {album} -> {track} -> {dest}")


if __name__ == "__main__":
    main()
