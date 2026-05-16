import sys, os, subprocess, requests, re
from bs4 import BeautifulSoup

def get_tracks(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to load page: {response.status_code}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try to find track names and artists in the metadata or page
    tracks = []
    
    # Method 1: Look for meta tags (works for single tracks/albums sometimes)
    title = soup.find("meta", property="og:title")
    description = soup.find("meta", property="og:description")
    
    if "playlist" in url:
        # For playlists, we might need a more robust way to scrape or use a public API if available
        # But for now, let's see if we can find them in the script tags
        import json
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and "Spotify.Entity" in script.string:
                # This is more complex, let's try a simpler regex on the whole page
                pass
        
        # Fallback: look for track links
        links = soup.find_all("a", href=re.compile(r"/track/"))
        for link in links:
            track_name = link.text.strip()
            if track_name and track_name not in ["Home", "Search", "Your Library"]:
                # Find the artist which is usually the next sibling or near
                # This is fragile, but let's try
                tracks.append(track_name)
    
    return list(set(tracks))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_spotify.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    print(f"Scraping tracks from: {url}")
    tracks = get_tracks(url)
    
    if not tracks:
        print("No tracks found. Is the playlist public?")
        sys.exit(1)
    
    print(f"Found {len(tracks)} tracks. Starting download...")
    
    for track in tracks:
        print(f"\nDownloading: {track}")
        subprocess.run(["spotdl", track])
