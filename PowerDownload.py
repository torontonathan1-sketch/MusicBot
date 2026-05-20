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
import base64
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import requests
import dotenv
from tqdm import tqdm

# Load environment variables
dotenv.load_dotenv(Path(__file__).parent.absolute() / ".env")


# ── Configuration ─────────────────────────────────────────────────────────────

MUSIC_ROOT = Path(__file__).parent.absolute()
YTDLP_PATH = "yt-dlp"          
def get_ffmpeg_location() -> Optional[str]:
    """Smart helper to find FFmpeg. If installed globally, returns None (allowing yt-dlp to find it automatically)."""
    # 1. Check if globally in system path
    import shutil
    try:
        if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
            return None
    except:
        pass

    # 2. Check common custom folder fallbacks
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
        return re.sub(r'[<>:"/\\|?*]', "", self.title).strip()

# ── MusicBrainz & Spotify helpers ──────────────────────────────────────────────

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


def resolve_spotify_artist_id(artist_name: str) -> Optional[str]:
    """Resolve the Spotify ID of an artist using API credentials or MusicBrainz relations."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if client_id and client_secret:
        try:
            log.info(f"Searching Spotify API for artist: {artist_name!r}")
            auth_response = requests.post("https://accounts.spotify.com/api/token", {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
            }, timeout=10)
            token = auth_response.json().get("access_token")
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                search_response = requests.get(
                    "https://api.spotify.com/v1/search",
                    params={"q": artist_name, "type": "artist", "limit": 1},
                    headers=headers,
                    timeout=10
                )
                items = search_response.json().get("artists", {}).get("items", [])
                if items:
                    artist_id = items[0]["id"]
                    log.info(f"  → Found Spotify Artist ID via API: {artist_id} ({items[0]['name']})")
                    return artist_id
        except Exception as e:
            log.warning(f"Failed to search Spotify via API: {e}")

    # Fallback to MusicBrainz relation search
    try:
        mbid = find_artist_mbid(artist_name)
        if mbid:
            url = f"https://musicbrainz.org/ws/2/artist/{mbid}"
            r = requests.get(url, params={"inc": "url-rels", "fmt": "json"}, headers=MB_HEADERS, timeout=15)
            if r.status_code == 200:
                for rel in r.json().get("relations", []):
                    resource = rel.get("url", {}).get("resource", "")
                    if "spotify.com/artist" in resource:
                        artist_id = resource.split("/")[-1].split("?")[0]
                        log.info(f"  → Found Spotify Artist ID via MusicBrainz: {artist_id}")
                        return artist_id
    except Exception as e:
        log.error(f"Failed to resolve Spotify ID via MusicBrainz fallback: {e}")

    return None


def get_spotify_album_tracklist(album_id: str) -> list[Track]:
    """Fetch and parse tracklist of a Spotify album using the public embed page."""
    embed_url = f"https://open.spotify.com/embed/album/{album_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
    r = requests.get(embed_url, headers=headers, timeout=15)
    
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
    if not match:
        raise RuntimeError(f"Could not find __NEXT_DATA__ in embed page for album {album_id}")
        
    data = json.loads(match.group(1))
    entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
    tracks = entity.get('trackList', [])
    
    track_list = []
    for i, t in enumerate(tracks):
        title = t.get('title') or t.get('name') or "Unknown"
        duration = t.get('duration') or t.get('duration_ms')
        track_list.append(Track(
            number=i + 1,
            title=title,
            duration_ms=duration
        ))
    return track_list


def get_spotify_albums_api(client_id: str, client_secret: str, artist_name: str) -> Optional[list[Album]]:
    """Fetch artist albums/singles, resolve popularity in chunks of 20, and get Top 9 + Latest release via Spotify API."""
    try:
        log.info(f"Authenticating Spotify API Client Credentials…")
        auth_response = requests.post("https://accounts.spotify.com/api/token", {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        }, timeout=10)
        token = auth_response.json().get("access_token")
        if not token:
            log.warning("Could not obtain Spotify API token.")
            return None
            
        headers = {"Authorization": f"Bearer {token}"}
        
        # Search artist
        search_response = requests.get(
            "https://api.spotify.com/v1/search",
            params={"q": artist_name, "type": "artist", "limit": 1},
            headers=headers,
            timeout=10
        )
        items = search_response.json().get("artists", {}).get("items", [])
        if not items:
            log.warning(f"No Spotify artist found for: {artist_name}")
            return None
            
        artist_id = items[0]["id"]
        
        # Get albums and singles
        albums_url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"
        params = {"limit": 50, "include_groups": "album,single"}
        r = requests.get(albums_url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
            
        album_items = r.json().get("items", [])
        if not album_items:
            return []
            
        # Fetch full album details in chunks of 20 to get popularity
        all_albums = []
        ids = [item["id"] for item in album_items]
        
        for i in range(0, len(ids), 20):
            chunk = ids[i:i+20]
            ids_str = ",".join(chunk)
            details_r = requests.get(
                "https://api.spotify.com/v1/albums",
                params={"ids": ids_str},
                headers=headers,
                timeout=10
            )
            if details_r.status_code == 200:
                for full_album in details_r.json().get("albums", []):
                    if not full_album: continue
                    all_albums.append(full_album)
                    
        if not all_albums:
            return []
            
        # Look for the newest release within 1 year (released on or after "2025-05-18")
        recent_releases = [a for a in all_albums if a.get("release_date", "") >= "2025-05-18"]
        latest_album = None
        if recent_releases:
            recent_releases.sort(key=lambda x: x.get("release_date", ""), reverse=True)
            latest_album = recent_releases[0]
            log.info(f"  → Found newest release within 1 year: {latest_album['name']} ({latest_album['release_date']})")
            
        # Candidates for popular albums (excluding latest_album if found)
        candidates = [a for a in all_albums if (not latest_album or a["id"] != latest_album["id"])]
        
        # Deduplicate candidates by base name and prioritize deluxe editions
        def clean_album_name_for_dedup(name: str) -> str:
            n = name.lower()
            for keyword in ["deluxe", "expanded", "bonus", "complete", "special", "super", "tour edition", "repacked", "platinum"]:
                n = n.replace(keyword, "")
            n = re.sub(r'[\(\)\[\]\-\:\,\.]', "", n)
            return " ".join(n.split())

        def is_deluxe(name: str) -> bool:
            n = name.lower()
            return any(k in n for k in ["full moon", "deluxe", "expanded", "bonus", "complete", "special", "platinum", "edition"])

        groups = {}
        for a in candidates:
            base_name = clean_album_name_for_dedup(a["name"])
            if base_name not in groups:
                groups[base_name] = []
            groups[base_name].append(a)
            
        representatives = []
        for base_name, group_list in groups.items():
            deluxe_editions = [a for a in group_list if is_deluxe(a["name"])]
            if deluxe_editions:
                deluxe_editions.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                representatives.append(deluxe_editions[0])
            else:
                group_list.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                representatives.append(group_list[0])
                
        # Sort final representative candidates by popularity descending
        representatives.sort(key=lambda x: x.get("popularity", 0), reverse=True)
        
        # Select target count (9 if latest_album exists, otherwise 10)
        target_count = 9 if latest_album else 10
        selected = []
        if latest_album:
            selected.append(latest_album)
        selected.extend(representatives[:target_count])
        
        final_albums = []
        for a in selected:
            year = None
            date_str = a.get("release_date", "")
            if len(date_str) >= 4 and date_str[:4].isdigit():
                year = int(date_str[:4])
                
            tracks = []
            for item in a.get("tracks", {}).get("items", []):
                tracks.append(Track(
                    number=item.get("track_number", 0),
                    title=item.get("name", "Unknown"),
                    duration_ms=item.get("duration_ms")
                ))
                
            album = Album(
                mbid=a["id"],
                title=a["name"],
                year=year,
                release_type=a.get("album_type", "album"),
                secondary_types=[]
            )
            album.tracks = tracks
            final_albums.append(album)
            
        final_albums.sort(key=lambda a: (a.year or 9999, a.title))
        log.info(f"  ✓ Successfully resolved {len(final_albums)} albums via official Spotify Web API!")
        return final_albums
    except Exception as e:
        log.error(f"Error fetching Spotify albums via Web API: {e}")
        return None


def get_itunes_artist_albums(artist_name: str) -> list[Album]:
    """
    Fetch an artist's top albums via the Apple iTunes Search API.
    Completely free, no API key, no account needed.
    Returns albums ranked by real popularity (sales/chart data).
    Uses iTunes track lookup for accurate tracklists.
    """
    log.info(f"Searching iTunes for artist: {artist_name!r}")
    try:
        # Search for albums by this artist
        r = requests.get(
            "https://itunes.apple.com/search",
            params={
                "term": artist_name,
                "entity": "album",
                "attribute": "artistTerm",
                "limit": 200,
                "country": "us",
            },
            timeout=15
        )
        if r.status_code != 200:
            log.warning(f"iTunes search returned status {r.status_code}")
            return []
        results = r.json().get("results", [])
    except Exception as e:
        log.warning(f"iTunes search failed: {e}")
        return []

    if not results:
        log.warning(f"iTunes found no albums for {artist_name!r}")
        return []

    # Filter to only albums where the searched artist appears in the artistName
    # This naturally handles collabs (e.g. "Drake & 21 Savage" matches "21 Savage")
    artist_lower = artist_name.lower()
    # Build first-word of artist for partial matching (e.g. "21" from "21 Savage")
    artist_words = set(artist_lower.split())
    candidates_raw = []
    for item in results:
        if item.get("wrapperType") != "collection":
            continue
        item_artist = item.get("artistName", "").lower()
        # Accept if any significant word of our artist name appears in the item's artist
        # OR if the item artist appears inside our artist name (handles short names)
        match = (
            artist_lower in item_artist
            or item_artist in artist_lower
            or any(w in item_artist for w in artist_words if len(w) > 2)
        )
        if not match:
            continue
        name = item.get("collectionName", "")
        collection_id = item.get("collectionId")
        track_count = item.get("trackCount", 0)
        date_str = item.get("releaseDate", "")
        year = int(date_str[:4]) if date_str and len(date_str) >= 4 and date_str[:4].isdigit() else None
        if not name or not collection_id:
            continue
        a = Album(
            mbid=str(collection_id),
            title=name,
            year=year,
            release_type="Album",
            secondary_types=[]
        )
        a.popularity = track_count
        candidates_raw.append(a)

    if not candidates_raw:
        log.warning(f"iTunes returned results but none matched artist {artist_name!r}")
        return []

    log.info(f"  → iTunes found {len(candidates_raw)} total releases for {artist_name!r}")

    # Look for newest release within 1 year
    recent = [a for a in candidates_raw if a.year and a.year >= 2025]
    latest_parsed = None
    if recent:
        # Pick most recent by year
        recent.sort(key=lambda x: x.year or 0, reverse=True)
        latest_parsed = recent[0]
        log.info(f"  → Newest release within 1 year (iTunes): {latest_parsed.title} ({latest_parsed.year})")

    # Deduplicate by base name, prefer deluxe editions
    def clean_name(name: str) -> str:
        n = name.lower()
        for kw in ["deluxe edition", "bonus track version", "bonus tracks",
                   "deluxe", "expanded", "bonus", "complete", "special", "super",
                   "tour edition", "repacked", "platinum", "remastered",
                   "anniversary edition", "collector's edition", "edition",
                   "version", "international"]:
            n = n.replace(kw, "")
        n = re.sub(r'[\(\)\[\]\-\:\,\.]', "", n)
        return " ".join(n.split())

    def is_deluxe(name: str) -> bool:
        n = name.lower()
        return any(k in n for k in ["full moon", "deluxe", "expanded", "bonus", "complete", "special", "platinum", "edition"])

    seen_ids = {latest_parsed.mbid} if latest_parsed else set()
    groups = {}
    for a in candidates_raw:
        if a.mbid in seen_ids:
            continue
        base = clean_name(a.title)
        groups.setdefault(base, []).append(a)

    representatives = []
    for base, group in groups.items():
        deluxe = [a for a in group if is_deluxe(a.title)]
        if deluxe:
            # Prefer deluxe; iTunes result order already reflects popularity so use first
            representatives.append(deluxe[0])
        else:
            representatives.append(group[0])  # iTunes ordering = popularity rank

    # Keep iTunes result order (index in original results = popularity rank)
    orig_order = {item.get("collectionId"): i for i, item in enumerate(results)}
    representatives.sort(key=lambda a: orig_order.get(int(a.mbid), 9999))

    # Fetch tracklists from iTunes for each representative until we have 10 valid
    target_count = 9 if latest_parsed else 10
    populated = []

    def fetch_itunes_tracks(collection_id: str) -> list[Track]:
        """Fetch tracklist for an iTunes collection ID."""
        r2 = requests.get(
            "https://itunes.apple.com/lookup",
            params={"id": collection_id, "entity": "song"},
            timeout=15
        )
        if r2.status_code != 200:
            return []
        songs = [s for s in r2.json().get("results", []) if s.get("wrapperType") == "track"]
        return [Track(number=s.get("trackNumber", i+1), title=s.get("trackName", "Unknown"), duration_ms=s.get("trackTimeMillis")) for i, s in enumerate(songs)]

    if latest_parsed:
        try:
            tracks = fetch_itunes_tracks(latest_parsed.mbid)
            latest_parsed.tracks = tracks
            if latest_parsed.track_count >= MIN_TRACKS:
                log.info(f"  ✓ {latest_parsed.year or '????'} — {latest_parsed.title!r} ({latest_parsed.track_count} tracks)")
                populated.append(latest_parsed)
            else:
                log.info(f"  ✗ {latest_parsed.title!r} ({latest_parsed.track_count} tracks) — below MIN_TRACKS, trying next")
                target_count = 10
        except Exception as e:
            log.error(f"  Could not fetch iTunes tracklist for latest: {e}")
            target_count = 10

    log.info(f"Fetching tracklists for {len(representatives)} iTunes candidates until {target_count} valid found…")
    valid = 0
    for album in representatives:
        if valid >= target_count:
            break
        try:
            tracks = fetch_itunes_tracks(album.mbid)
            album.tracks = tracks
            if album.track_count >= MIN_TRACKS:
                log.info(f"  ✓ {album.year or '????'} — {album.title!r} ({album.track_count} tracks)")
                populated.append(album)
                valid += 1
            else:
                log.info(f"  ✗ {album.title!r} ({album.track_count} tracks) — below MIN_TRACKS, trying next…")
        except Exception as e:
            log.error(f"  Could not fetch iTunes tracklist for {album.title!r}: {e}")

    populated.sort(key=lambda a: (a.year or 9999, a.title))
    log.info(f"  Ready to download {len(populated)} iTunes albums.")
    return populated




# ── MusicBrainz Credential-Free Fallback Helpers ───────────────────────────────

def get_artist_albums_mb(mbid: str) -> list[Album]:
    """Fetch all release groups for an artist from MusicBrainz, prioritize studio albums/EPs,
    then fetch track listings for each. Ensures exactly 10 releases if available."""
    log.info(f"Fetching release groups for MBID: {mbid} via MusicBrainz Fallback...")
    all_albums: list[Album] = []
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

            if primary in {"Spokenword", "Audiobook"} or any(t in {"Spokenword", "Audiobook"} for t in secondary):
                continue

            year_str = rg.get("first-release-date", "")
            year = int(year_str[:4]) if len(year_str) >= 4 and year_str[:4].isdigit() else None

            popularity = rg.get("count", 0)
            album = Album(
                mbid=rg["id"],
                title=rg["title"],
                year=year,
                release_type=primary,
                secondary_types=secondary,
                popularity=popularity,
            )
            all_albums.append(album)

        offset += limit
        if offset >= data.get("release-group-count", 0):
            break
    if not all_albums: return []

    primary_releases = []
    secondary_releases = []

    for a in all_albums:
        is_primary = (a.release_type in INCLUDE_TYPES) and not any(t in EXCLUDE_SECONDARY for t in a.secondary_types)
        if is_primary:
            primary_releases.append(a)
        else:
            secondary_releases.append(a)

    primary_releases.sort(key=lambda a: (a.year or 0, a.popularity), reverse=True)
    secondary_releases.sort(key=lambda a: (a.year or 0, a.popularity), reverse=True)

    # Look for the newest release within 1 year (released in 2025 or 2026)
    recent_releases = [a for a in all_albums if a.year and a.year >= 2025]
    latest_parsed = None
    if recent_releases:
        recent_releases.sort(key=lambda x: (x.year, x.popularity), reverse=True)
        latest_parsed = recent_releases[0]
        log.info(f"  → Found newest release within 1 year (MusicBrainz): {latest_parsed.title} ({latest_parsed.year})")

    # Combine primary and secondary into candidate list
    candidates = []
    seen_cand_ids = set()
    if latest_parsed:
        seen_cand_ids.add(latest_parsed.mbid)

    # Put primary releases first in candidates
    for a in primary_releases:
        if a.mbid not in seen_cand_ids:
            candidates.append(a)
            seen_cand_ids.add(a.mbid)
            
    for a in secondary_releases:
        if a.mbid not in seen_cand_ids:
            candidates.append(a)
            seen_cand_ids.add(a.mbid)

    # Deduplicate candidates by base name and prioritize deluxe editions
    def clean_album_name_for_dedup(name: str) -> str:
        n = name.lower()
        for keyword in ["deluxe", "expanded", "bonus", "complete", "special", "super", "tour edition", "repacked", "platinum"]:
            n = n.replace(keyword, "")
        n = re.sub(r'[\(\)\[\]\-\:\,\.]', "", n)
        return " ".join(n.split())

    def is_deluxe(name: str) -> bool:
        n = name.lower()
        return any(k in n for k in ["full moon", "deluxe", "expanded", "bonus", "complete", "special", "platinum", "edition"])

    groups = {}
    for a in candidates:
        base_name = clean_album_name_for_dedup(a.title)
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(a)
        
    representatives = []
    for base_name, group_list in groups.items():
        deluxe_editions = [a for a in group_list if is_deluxe(a.title)]
        if deluxe_editions:
            deluxe_editions.sort(key=lambda x: x.popularity, reverse=True)
            representatives.append(deluxe_editions[0])
        else:
            group_list.sort(key=lambda x: x.popularity, reverse=True)
            representatives.append(group_list[0])
            
    # Sort: studio albums first, then EPs, then by year descending (newest = most relevant)
    def release_type_rank(a):
        if a.release_type == "Album" and not a.secondary_types:
            return 0  # Pure studio album — top priority
        elif a.release_type == "Album":
            return 1
        elif a.release_type == "EP":
            return 2
        else:
            return 3
    representatives.sort(key=lambda x: (release_type_rank(x), -(x.year or 0)))

    # Fetch tracklists for ALL representatives — keep going until we have 10 valid ones
    target_count = 9 if latest_parsed else 10
    populated = []

    # Handle latest release first
    if latest_parsed:
        try:
            tracks = get_tracklist_mb(latest_parsed.mbid)
            latest_parsed.tracks = tracks
            if latest_parsed.track_count >= MIN_TRACKS:
                log.info(f"  ✓ {latest_parsed.year or '????'} — {latest_parsed.title!r} ({latest_parsed.track_count} tracks)")
                populated.append(latest_parsed)
            else:
                log.info(f"  ✗ {latest_parsed.title!r} ({latest_parsed.track_count} tracks) — below MIN_TRACKS, skipping latest")
                target_count = 10  # fill the slot
        except Exception as e:
            log.error(f"  Could not fetch tracklist for latest {latest_parsed.title!r}: {e}")
            target_count = 10

    log.info(f"Checking tracklists for all {len(representatives)} MusicBrainz candidates until {target_count} valid found…")
    valid_non_latest = 0
    for album in representatives:
        if valid_non_latest >= target_count:
            break
        try:
            tracks = get_tracklist_mb(album.mbid)
            album.tracks = tracks
            if album.track_count >= MIN_TRACKS:
                log.info(f"  ✓ {album.year or '????'} — {album.title!r} ({album.track_count} tracks)")
                populated.append(album)
                valid_non_latest += 1
            else:
                log.info(f"  ✗ {album.title!r} ({album.track_count} tracks) — below MIN_TRACKS, trying next…")
        except Exception as e:
            log.error(f"  Could not fetch tracklist for {album.title!r}: {e}")

    populated.sort(key=lambda a: (a.year or 9999, a.title))
    log.info(f"  Ready to download {len(populated)} MusicBrainz albums.")
    return populated


def get_tracklist_mb(release_group_mbid: str) -> list[Track]:
    """Find the best release in a MusicBrainz release group (prioritizing Deluxe editions) and return its tracklist."""
    data = mb_get(
        f"release-group/{release_group_mbid}",
        {"inc": "releases"},
    )
    releases = data.get("releases", [])
    if not releases:
        return []

    best_rel = releases[0]
    for rel in releases:
        title = rel.get("title", "").lower()
        disambig = rel.get("disambiguation", "").lower()
        if "deluxe" in title or "deluxe" in disambig or "expanded" in title or "bonus" in title:
            best_rel = rel
            break

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
    clean_q = query.replace('"', '').replace(':', ' ')
    search_url = f"ytsearchmusic5:{clean_q}"
    cmd = [
        YTDLP_PATH,
        "--no-config-locations",
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
        "--no-config-locations",
        url,
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
        "--postprocessor-args", (
            f"ffmpeg:-metadata artist={artist_name!r} "
            f"-metadata album_artist={artist_name!r} "
            f"-metadata album={album.title!r} "
            f"-metadata date={album.year or ''} "
            f"-id3v2_version 3"
        ),
        "--yes-playlist",
        "--ignore-errors",        "--no-warnings",
        "--trim-filenames", "100",
        "--sleep-interval", "2",
        "--max-sleep-interval", "5",
        "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "--force-ipv4"
    ])

    try:
        subprocess.run(cmd, timeout=3600)
        files = list(output_dir.glob("*.mp3"))
        return len(files)
    except:
        return 0


def record_failed_download(artist: str, album: str, track: str, error: str):
    failed_file = MUSIC_ROOT / "failed_downloads.txt"
    try:
        with open(failed_file, "a", encoding="utf-8") as f:
            f.write(f"Artist: {artist} | Album: {album} | Track: {track} | Error: {error}\n")
        log.warning(f"Recorded failed download in failed_downloads.txt: {track!r} ({error})")
    except Exception as e:
        log.error(f"Failed to write to failed_downloads.txt: {e}")


def download_track_individually(
    artist_name: str,
    album: Album,
    track: Track,
    output_dir: Path,
) -> bool:
    # Build resilient query variants for long classical titles and noisy punctuation
    clean_title = track.title.replace('"', '').replace(':', ' ')
    clean_album = album.title.replace('"', '').replace(':', ' ')
    clean_artist = artist_name.replace('"', '').replace(':', ' ')

    def simplify_title(title: str) -> str:
        # Remove movement detail after colon and collapse punctuation-heavy fragments
        base = title.split(':', 1)[0].strip()
        base = re.sub(r'\b(op\.?|no\.?|nr\.?)\s*', '', base, flags=re.IGNORECASE)
        base = re.sub(r'[^\w\s]', ' ', base)
        return ' '.join(base.split())

    title_simple = simplify_title(track.title)
    queries = [
        f"ytsearch5:{clean_artist} {clean_title} {clean_album}",
        f"ytsearch5:{clean_artist} {title_simple} {clean_album}",
        f"ytsearch5:{clean_artist} {title_simple}",
    ]

    safe_title = sanitize_filename(track.title)
    output_path = output_dir / f"{safe_title}.%(ext)s"

    ffmpeg_loc = get_ffmpeg_location()
    last_error = "Download failed (no output file created)"

    for query in queries:
        cmd = [
            YTDLP_PATH,
            "--no-config-locations",
            query,
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "4",
        ]
        if ffmpeg_loc:
            cmd.extend(["--ffmpeg-location", ffmpeg_loc])
        cmd.extend(get_cookies_args())

        cmd.extend([
            "--output", str(output_path),
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
            "--no-warnings",
            "--trim-filenames", "100",
            "--sleep-interval", "2",
            "--max-sleep-interval", "5",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            exists = False
            if output_dir.exists():
                for f in output_dir.glob("*.mp3"):
                    if safe_title.lower() in f.name.lower():
                        exists = True
                        break

            if exists:
                return True

            combined_output = (res.stderr or "") + "\n" + (res.stdout or "")
            for line in combined_output.splitlines():
                if "ERROR:" in line or "error" in line.lower():
                    last_error = line.strip()
                    break
        except Exception as e:
            last_error = str(e)

    record_failed_download(artist_name, album.title, track.title, last_error)
    return False

def album_already_downloaded(output_dir: Path, expected_count: int) -> bool:
    if not output_dir.exists():
        return False
    existing = list(output_dir.glob("*.mp3"))
    if len(existing) >= expected_count * 0.85:
        return True
    return False



# ── Main orchestration ────────────────────────────────────────────────────────

def process_artist(artist_name: str, total_bar):
    artist_dir = MUSIC_ROOT / sanitize_filename(artist_name)

    # iTunes-first only (Spotify removed), then MusicBrainz fallback
    albums = get_itunes_artist_albums(artist_name)
    if albums and len(albums) < 2:
        log.warning(f"iTunes only found {len(albums)} album(s) for {artist_name!r}; trying MusicBrainz")
        albums = None

    if not albums:
        log.warning("iTunes returned 0/low-confidence albums. Querying MusicBrainz fallback...")
        mbid = find_artist_mbid(artist_name)
        if mbid:
            albums = get_artist_albums_mb(mbid)

    if not albums:
        log.warning(f"Could not resolve any albums for: {artist_name!r}")
        return

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
            for f in album_dir.glob("*.mp3"):
                if safe_title.lower() in f.name.lower():
                    exists = True
                    break

            if not exists:
                missing_tracks.append(track)

        if not missing_tracks:
            album_bar.update(1)
            continue

        # If missing more than 50%, use playlist download (faster)
        playlist_attempted = False
        if len(missing_tracks) > len(album.tracks) * 0.5:
            query = build_ytmusic_query(artist_name, album.title)
            playlist = ytdlp_search_playlist(query, album.track_count, artist_name, album)
            if playlist:
                log.info(f"  → Found album playlist, starting bulk download: {playlist}")
                download_album_playlist(playlist, artist_name, album, album_dir)
                playlist_attempted = True

        # Check for remaining gaps and download them individually
        still_missing = []
        for track in album.tracks:
            safe_title = sanitize_filename(track.title)
            exists = False
            for f in album_dir.glob("*.mp3"):
                if safe_title.lower() in f.name.lower():
                    exists = True
                    break
            if not exists:
                still_missing.append(track)

        if still_missing:
            if playlist_attempted:
                log.info(f"  → Bulk download complete. Filling {len(still_missing)} remaining gaps individually...")
            for track in still_missing:
                download_track_individually(artist_name, album, track, album_dir)

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

    # Deduplicate while preserving original checklist order
    seen_artists = set()
    deduped_artists = []
    for a in artists:
        # Standardize matching name to prevent slight capitalization duplicates
        a_clean = a.strip()
        a_lower = a_clean.lower()
        if a_lower not in seen_artists:
            seen_artists.add(a_lower)
            deduped_artists.append(a_clean)
    artists = deduped_artists

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
                import sys
                subprocess.run([sys.executable, "SyncNotion.py"], cwd=str(MUSIC_ROOT))
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
