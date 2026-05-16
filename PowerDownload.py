"""
PowerDownload.py — Robust discography downloader
Strategy:
  1. MusicBrainz API  → authoritative album + track list (no API key, no rate limits)
  2. yt-dlp           → search YouTube Music for each album playlist
  3. Track verifier   → confirm expected count before committing download
  4. Fallback         → individual track searches when playlist not found
"""

import os
import re
import time
import json
import logging
import argparse
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import requests
from tqdm import tqdm

# ── Configuration ─────────────────────────────────────────────────────────────

MUSIC_ROOT = Path(__file__).parent.absolute()
YTDLP_PATH = "yt-dlp"          
FFMPEG_PATH = r"C:\Users\Steve\.spotdl" # Updated to your specific location
LOG_FILE    = MUSIC_ROOT / "download.log"

# MusicBrainz
MB_BASE     = "https://musicbrainz.org/ws/2"
MB_HEADERS  = {"User-Agent": "MusicDownloader/1.0 (torontonathan1@gmail.com)"}
MB_DELAY    = 1.1              # seconds between requests (API rate limit: 1 req/sec)

# Album filter — only download albums with at least this many tracks
MIN_TRACKS  = 3

# Release types to include (MusicBrainz terminology)
INCLUDE_TYPES = {"Album", "EP"}
# Secondary types to exclude (e.g. compilations, live albums)
EXCLUDE_SECONDARY = {"Compilation", "Live", "Remix", "Spokenword", "Audiobook", "DJ-mix"}

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Track:
    number: int
    title: str
    duration_ms: Optional[int] = None

@dataclass
class Album:
    mbid: str
    title: str
    year: Optional[int]
    release_type: str
    secondary_types: list[str]
    popularity: int = 0
    tracks: list[Track] = field(default_factory=list)

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def folder_name(self) -> str:
        """Safe folder name: strip illegal Windows chars."""
        safe = re.sub(r'[<>:"/\\|?*]', "", self.title).strip()
        if self.year:
            return f"{self.year} - {safe}"
        return safe

# ── MusicBrainz helpers ───────────────────────────────────────────────────────

def mb_get(endpoint: str, params: dict) -> dict:
    """GET from MusicBrainz with rate limiting and error handling."""
    params["fmt"] = "json"
    url = f"{MB_BASE}/{endpoint}"
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=MB_HEADERS, timeout=60)
            if r.status_code == 503:
                wait = 5 * (attempt + 1)
                log.warning(f"MB 503, retrying in {wait}s…")
                time.sleep(wait)
                continue
            r.raise_for_status()
            time.sleep(MB_DELAY)
            return r.json()
        except requests.RequestException as e:
            log.error(f"MB request failed ({attempt+1}/3): {e}")
            time.sleep(3)
    raise RuntimeError(f"MusicBrainz unreachable after 3 attempts: {url}")


def find_artist_mbid(artist_name: str) -> Optional[str]:
    """Search MusicBrainz for an artist and return their MBID."""
    log.info(f"Searching MusicBrainz for artist: {artist_name!r}")
    data = mb_get("artist", {"query": f'artist:"{artist_name}"', "limit": 5})
    artists = data.get("artists", [])
    if not artists:
        log.warning(f"No MusicBrainz results for {artist_name!r}")
        return None

    # Prefer exact name match, else take top result
    for a in artists:
        if a["name"].lower() == artist_name.lower():
            log.info(f"  → Matched artist: {a['name']} (MBID: {a['id']})")
            return a["id"]

    best = artists[0]
    log.info(f"  → Best match: {best['name']} (score {best.get('score')}) MBID: {best['id']}")
    return best["id"]


def get_artist_albums(mbid: str) -> list[Album]:
    """
    Fetch all release groups for an artist, filter to studio albums/EPs,
    then fetch track listings for each.
    """
    log.info(f"Fetching release groups for MBID: {mbid}")
    albums: list[Album] = []
    offset = 0
    limit  = 100

    while True:
        data = mb_get(
            f"release-group",
            {
                "query":   f"arid:{mbid}",
                "limit":   limit,
                "offset":  offset,
            },
        )
        groups = data.get("release-groups", [])
        if not groups:
            break

        for rg in groups:
            primary   = rg.get("primary-type", "")
            secondary = [t for t in rg.get("secondary-types", [])]

            # Type filter in Python instead of API parameter
            if primary not in INCLUDE_TYPES:
                continue
            if any(t in EXCLUDE_SECONDARY for t in secondary):
                log.debug(f"  Skipping {rg['title']!r} (secondary type: {secondary})")
                continue

            year_str = rg.get("first-release-date", "")
            year = int(year_str[:4]) if len(year_str) >= 4 and year_str[:4].isdigit() else None

            # Use the release group MBID to fetch tracks
            popularity = rg.get("count", 0)
            album = Album(
                mbid=rg["id"],
                title=rg["title"],
                year=year,
                release_type=primary,
                secondary_types=secondary,
                popularity=popularity,
            )
            albums.append(album)

        offset += limit
        if offset >= data.get("release-group-count", 0):
            break

    # Fetch track listings
    log.info(f"Found {len(albums)} candidate release groups, fetching track counts…")
    populated = []
    for album in albums:
        try:
            tracks = get_tracklist(album.mbid)
            album.tracks = tracks
            if album.track_count >= MIN_TRACKS:
                log.info(f"  ✓ {album.year or '????'} — {album.title!r} ({album.track_count} tracks)")
                populated.append(album)
            else:
                log.info(f"  ✗ {album.title!r} ({album.track_count} tracks) — below MIN_TRACKS={MIN_TRACKS}")
        except Exception as e:
            log.error(f"  Could not fetch tracklist for {album.title!r}: {e}")

    # Top 10 + Newest Logic
    populated.sort(key=lambda a: (a.year or 0), reverse=True)
    if not populated: return []
    
    newest = populated[0]
    
    # Sort the rest by popularity (release count proxy) to get the most substantial albums (top 10 proxy)
    rest = populated[1:]
    rest.sort(key=lambda a: a.popularity, reverse=True)
    
    final_albums = [newest] + rest[:9] # Newest + Top 9 = Max 10
    final_albums.sort(key=lambda a: (a.year or 9999, a.title))
    
    log.info(f"  Filtered down to {len(final_albums)} top/newest albums.")
    return final_albums


def get_tracklist(release_group_mbid: str) -> list[Track]:
    """
    Find the best release in a release group (prioritizing Deluxe editions) and return its tracklist.
    """
    data = mb_get(
        f"release-group/{release_group_mbid}",
        {"inc": "releases"},
    )
    releases = data.get("releases", [])
    if not releases:
        return []

    # Find the best release (Deluxe)
    best_rel = releases[0]
    for rel in releases:
        title = rel.get("title", "").lower()
        disambig = rel.get("disambiguation", "").lower()
        if "deluxe" in title or "deluxe" in disambig or "expanded" in title or "bonus" in title:
            best_rel = rel
            break

    # Fetch recordings for the best release
    rel_data = mb_get(
        f"release/{best_rel['id']}",
        {"inc": "recordings"},
    )
    
    tracks: list[Track] = []
    for medium in rel_data.get("media", []):
        for t in medium.get("tracks", []):
            tracks.append(Track(
                number=t.get("position", 0),
                title=t.get("title", "Unknown"),
                duration_ms=t.get("length"),
            ))
            
    return tracks

# ── yt-dlp helpers ────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """Remove characters illegal in Windows filenames."""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def build_ytmusic_query(artist: str, album_title: str) -> str:
    return f'{artist} "{album_title}" full album'


def ytdlp_search_playlist(query: str, expected_tracks: int, artist: str, album: Album) -> Optional[str]:
    search_url = f"ytsearchmusic5:{query}"
    cmd = [
        YTDLP_PATH,
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--default-search", "ytsearchmusic",
        search_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        lines = [l for l in result.stdout.strip().splitlines() if l]
        
        best_url = None
        best_score = -1

        for line in lines:
            try:
                info = json.loads(line)
            except json.JSONDecodeError:
                continue

            playlist_count = info.get("playlist_count") or info.get("n_entries", 0)
            title = info.get("title", "")
            url   = info.get("url") or info.get("webpage_url", "")

            if not url or not playlist_count:
                continue

            delta = abs(playlist_count - expected_tracks)
            score = 100 - delta 

            album_words = set(album.title.lower().split())
            title_words = set(title.lower().split())
            overlap = len(album_words & title_words) / max(len(album_words), 1)
            score += int(overlap * 50)

            if score > best_score:
                best_score = score
                best_url   = url

        if best_url and best_score > 60:
            return best_url

    except Exception as e:
        log.error(f"  yt-dlp search error: {e}")

    return None


def download_album_playlist(
    url: str,
    artist_name: str,
    album: Album,
    output_dir: Path,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title)s.%(ext)s") # Simpler naming to match your style

    cmd = [
        YTDLP_PATH,
        url,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "4",
        "--ffmpeg-location", FFMPEG_PATH,
        "--output", output_template,
        "--write-thumbnail",
        "--add-metadata",
        "--postprocessor-args", (
            f"ffmpeg:-metadata artist={artist_name!r} "
            f"-metadata album_artist={artist_name!r} "
            f"-metadata album={album.title!r} "
            f"-metadata date={album.year or ''} "
            f"-id3v2_version 3"
        ),
        "--yes-playlist",
        "--ignore-errors",
        "--quiet",
        "--no-warnings",
        "--trim-filenames", "100",
        "--sleep-interval", "2",
        "--max-sleep-interval", "5",
        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "--force-ipv4"
    ]

    try:
        subprocess.run(cmd, timeout=3600)
        files = list(output_dir.glob("*.mp3"))
        return len(files)
    except:
        return 0


def download_track_individually(
    artist_name: str,
    album: Album,
    track: Track,
    output_dir: Path,
) -> bool:
    query = f"ytsearch1:{artist_name} {track.title} {album.title}"
    safe_title = sanitize_filename(track.title)
    output_path = output_dir / f"{safe_title}.%(ext)s"

    cmd = [
        YTDLP_PATH,
        query,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "4",
        "--ffmpeg-location", FFMPEG_PATH,
        "--output", str(output_path),
        "--write-thumbnail",
        "--add-metadata",
        "--postprocessor-args", (
            f"ffmpeg:-metadata artist={artist_name!r} "
            f"-metadata album_artist={artist_name!r} "
            f"-metadata album={album.title!r} "
            f"-metadata title={track.title!r} "
            f"-metadata date={album.year or ''} "
            f"-id3v2_version 3"
        ),
        "--no-playlist",
        "--ignore-errors",
        "--quiet",
        "--no-warnings",
        "--trim-filenames", "100",
        "--sleep-interval", "2",
        "--max-sleep-interval", "5",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]

    try:
        subprocess.run(cmd, timeout=120)
        return True
    except:
        return False


def album_already_downloaded(output_dir: Path, expected_count: int) -> bool:
    if not output_dir.exists():
        return False
    existing = list(output_dir.glob("*.mp3"))
    if len(existing) >= expected_count * 0.85:
        return True
    return False

def ensure_folder_jpg(album_dir: Path):
    jpg_path = album_dir / "folder.jpg"
    
    images = []
    for ext in ["*.jpg", "*.webp", "*.png"]:
        images.extend(album_dir.glob(ext))
        
    if not jpg_path.exists() and images:
        source_img = images[0]
        cmd = [
            os.path.join(FFMPEG_PATH, "ffmpeg.exe"),
            "-i", str(source_img),
            "-vf", "scale=150:150",
            "-q:v", "5",
            str(jpg_path),
            "-y",
            "-v", "quiet"
        ]
        try:
            subprocess.run(cmd, timeout=30)
        except Exception as e:
            log.error(f"  Failed to create folder.jpg: {e}")
            
    for img in images:
        if img.name != "folder.jpg":
            try:
                img.unlink()
            except:
                pass

# ── Main orchestration ────────────────────────────────────────────────────────

def process_artist(artist_name: str, total_bar):
    artist_dir = MUSIC_ROOT / sanitize_filename(artist_name)

    mbid = find_artist_mbid(artist_name)
    if not mbid: return

    albums = get_artist_albums(mbid)
    if not albums: return

    # Album Progress Bar
    album_bar = tqdm(total=len(albums), desc=f"   ↳ {artist_name} Albums", unit="album", leave=False)

    for album in albums:
        album_dir = artist_dir / sanitize_filename(album.title)
        album_dir.mkdir(parents=True, exist_ok=True)

        # Check which tracks we are actually missing
        missing_tracks = []
        for track in album.tracks:
            safe_title = sanitize_filename(track.title)
            exists = False
            # Check if any file contains the title (case-insensitive)
            for f in album_dir.glob("*.mp3"):
                if safe_title.lower() in f.name.lower():
                    exists = True
                    break
            
            if not exists:
                missing_tracks.append(track)
        
        if not missing_tracks:
            ensure_folder_jpg(album_dir)
            album_bar.update(1)
            continue

        # If missing more than 50%, use playlist download (faster)
        if len(missing_tracks) > len(album.tracks) * 0.5:
            query    = build_ytmusic_query(artist_name, album.title)
            playlist = ytdlp_search_playlist(query, album.track_count, artist_name, album)
            if playlist:
                download_album_playlist(playlist, artist_name, album, album_dir)
                ensure_folder_jpg(album_dir)
                album_bar.update(1)
                continue

        # Otherwise, fill the specific gaps one by one
        for track in missing_tracks:
            download_track_individually(artist_name, album, track, album_dir)
        
        ensure_folder_jpg(album_dir)
        album_bar.update(1)
    
    album_bar.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artists", nargs="*")
    parser.add_argument("--file")
    args = parser.parse_args()

    artists = args.artists or []
    if args.file and os.path.exists(args.file):
        with open(args.file, encoding="utf-8") as f:
            artists.extend([l.strip() for l in f if l.strip()])

    if not artists: return

    total_bar = tqdm(total=len(artists), desc="TOTAL PROGRESS", unit="artist")

    for i, artist in enumerate(artists):
        try:
            process_artist(artist, total_bar)
        except Exception as e:
            log.error(f"Error: {e}")
            
        # Auto-sync Notion every 5 artists
        if (i + 1) % 5 == 0 and args.file:
            log.info("Reached 5 artists. Re-syncing Notion checklist...")
            try:
                subprocess.run(["py", "SyncNotion.py"], cwd=str(MUSIC_ROOT))
                with open(args.file, encoding="utf-8") as f:
                    new_artists = [l.strip() for l in f if l.strip()]
                for na in new_artists:
                    if na not in artists:
                        artists.append(na)
                        total_bar.total += 1
                        total_bar.refresh()
            except Exception as se:
                log.error(f"Failed to auto-sync Notion: {se}")

        total_bar.update(1)

    total_bar.close()

if __name__ == "__main__":
    main()
