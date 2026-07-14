import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

MUSIC_ROOT = Path(__file__).parent.absolute()
CHUNK_DIR = MUSIC_ROOT / "PlaylistChunks"


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def fetch_spotify_tracks(url: str) -> tuple[list[str], str]:
    playlist_id = url.split('/')[-1].split('?')[0]
    tracks: list[str] = []
    playlist_name = "Unknown Playlist"

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if client_id and client_secret:
        auth_response = requests.post(
            "https://accounts.spotify.com/api/token",
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        auth_response.raise_for_status()
        access_token = auth_response.json().get("access_token")
        if not access_token:
            raise RuntimeError("Spotify auth succeeded but no access token was returned")

        headers = {"Authorization": f"Bearer {access_token}"}
        meta_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
        r_meta = requests.get(meta_url, headers=headers, timeout=15)
        r_meta.raise_for_status()
        playlist_name = r_meta.json().get("name", "Unknown Playlist")

        tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100"
        while tracks_url:
            r_tracks = requests.get(tracks_url, headers=headers, timeout=15)
            r_tracks.raise_for_status()
            payload = r_tracks.json()
            for item in payload.get("items", []):
                t = item.get("track")
                if not t:
                    continue
                title = t.get("name")
                artist = t.get("artists", [{}])[0].get("name", "Unknown")
                if title:
                    tracks.append(f"{artist} - {title}")
            tracks_url = payload.get("next")

        return tracks, playlist_name

    # Fallback: public embed scraper (typically capped around 100)
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    r = requests.get(embed_url, timeout=15)
    r.raise_for_status()
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
    if not match:
        raise RuntimeError("Could not parse Spotify embed payload")

    data = json.loads(match.group(1))
    entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    playlist_name = entity.get("name", entity.get("title", "Unknown Playlist"))
    items = entity.get("trackList") or entity.get("tracks", {}).get("items", [])

    for item in items:
        t = item.get("track", item)
        title = t.get("title", t.get("name"))
        artist = t.get("subtitle", "Unknown")
        if not artist or artist == "Unknown":
            artist = t.get("artists", [{}])[0].get("name", "Unknown")
        if title:
            tracks.append(f"{artist} - {title}")

    return tracks, playlist_name


def chunk_tracks(tracks: list[str], chunk_size: int) -> list[list[str]]:
    return [tracks[i:i + chunk_size] for i in range(0, len(tracks), chunk_size)]


def write_chunk_files(playlist_name: str, chunks: list[list[str]]) -> list[Path]:
    safe_name = sanitize_filename(playlist_name) or "Playlist"
    chunk_root = CHUNK_DIR / safe_name
    chunk_root.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for idx, chunk in enumerate(chunks, start=1):
        path = chunk_root / f"{idx:03d}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk) + "\n")
        paths.append(path)
    return paths


def run_downloader_for_chunks(chunk_files: list[Path]) -> None:
    downloader = MUSIC_ROOT / "DownloadPlaylist.py"
    python_exe = sys.executable

    for i, path in enumerate(chunk_files, start=1):
        print(f"\n=== Chunk {i}/{len(chunk_files)}: {path.name} ===")
        rc = subprocess.call([python_exe, str(downloader), str(path)])
        if rc != 0:
            print(f"Chunk failed with exit code {rc}: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split a large Spotify playlist into chunks and feed DownloadPlaylist.py")
    parser.add_argument("playlist_url", help="Spotify playlist URL")
    parser.add_argument("--chunk-size", type=int, default=100, help="Tracks per chunk (default: 100)")
    parser.add_argument("--no-download", action="store_true", help="Only create chunk files, do not start downloads")
    args = parser.parse_args()

    if "spotify.com/playlist" not in args.playlist_url:
        raise SystemExit("Please provide a Spotify playlist URL.")

    tracks, playlist_name = fetch_spotify_tracks(args.playlist_url)
    if not tracks:
        raise SystemExit("No tracks found in playlist.")

    chunks = chunk_tracks(tracks, max(1, args.chunk_size))
    chunk_files = write_chunk_files(playlist_name, chunks)

    print(f"Playlist: {playlist_name}")
    print(f"Tracks: {len(tracks)}")
    print(f"Chunks: {len(chunk_files)}")
    print(f"Chunk files: {chunk_files[0].parent}")

    if not args.no_download:
        run_downloader_for_chunks(chunk_files)


if __name__ == "__main__":
    main()
