import os
import json
import re
from pathlib import Path
import requests
import time

MUSIC_ROOT = Path(__file__).parent.absolute()
MB_BASE = "https://musicbrainz.org/ws/2"
MB_HEADERS = {"User-Agent": "MusicAudit/1.0 (torontonathan1@gmail.com)"}

def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()

def mb_get(endpoint: str, params: dict) -> dict:
    params["fmt"] = "json"
    url = f"{MB_BASE}/{endpoint}"
    time.sleep(1.1) # Respect rate limits
    r = requests.get(url, params=params, headers=MB_HEADERS)
    r.raise_for_status()
    return r.json()

def audit_artist(artist_name: str):
    print(f"🔍 Auditing Artist: {artist_name}")
    artist_dir = MUSIC_ROOT / sanitize_filename(artist_name)
    if not artist_dir.exists():
        print(f"  ⚠️ Artist folder not found locally.")
        return []

    # Search for MBID
    data = mb_get("artist", {"query": f'artist:"{artist_name}"', "limit": 1})
    if not data.get("artists"):
        return []
    mbid = data["artists"][0]["id"]

    # Get release groups (Top 10 logic similar to PowerDownload)
    rg_data = mb_get("release-group", {"query": f"arid:{mbid}", "limit": 100})
    groups = [g for g in rg_data.get("release-groups", []) if g.get("primary-type") in ["Album", "EP"]]
    
    missing_report = []

    for rg in groups[:15]: # Audit a decent sample
        album_title = rg["title"]
        album_dir = artist_dir / sanitize_filename(album_title)
        
        if not album_dir.exists():
            continue

        # Get tracks for this release group
        rel_data = mb_get(f"release-group/{rg['id']}", {"inc": "releases"})
        if not rel_data.get("releases"): continue
        best_rel = rel_data["releases"][0]
        
        track_data = mb_get(f"release/{best_rel['id']}", {"inc": "recordings"})
        expected_tracks = []
        for medium in track_data.get("media", []):
            for t in medium.get("tracks", []):
                expected_tracks.append(t.get("title", "Unknown"))

        # Check local files
        local_files = [f.name.lower() for f in album_dir.glob("*.mp3")]
        
        missing_in_album = []
        for track in expected_tracks:
            safe_track = sanitize_filename(track).lower()
            found = False
            for lf in local_files:
                if safe_track in lf:
                    found = True
                    break
            if not found:
                missing_in_album.append(track)
        
        if missing_in_album:
            missing_report.append({
                "album": album_title,
                "missing": missing_in_album
            })
            
    return missing_report

def main():
    print("==========================================")
    print("       🎵 MUSIC LIBRARY AUDIT TOOL        ")
    print("==========================================")
    
    report_file = MUSIC_ROOT / "missing_songs_report.txt"
    artists = [d.name for d in MUSIC_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("MUSIC LIBRARY AUDIT REPORT\n")
        f.write("==========================\n\n")
        
        for artist in artists:
            try:
                missing = audit_artist(artist)
                if missing:
                    f.write(f"ARTIST: {artist}\n")
                    for m in missing:
                        f.write(f"  ALBUM: {m['album']}\n")
                        for song in m['missing']:
                            f.write(f"    - MISSING: {song}\n")
                    f.write("\n")
            except Exception as e:
                print(f"Error auditing {artist}: {e}")

    print(f"\n✅ Audit complete! Report saved to: {report_file}")

if __name__ == "__main__":
    main()
