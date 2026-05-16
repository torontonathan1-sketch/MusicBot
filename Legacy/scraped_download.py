import requests
import json
import subprocess
import sys
import re
from bs4 import BeautifulSoup

def scrape_spotify_playlist(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    print(f"Fetching playlist data from {url}...")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error: Could not fetch page (Status {response.status_code})")
        return []

    content = response.text
    tracks = []

    # Method 1: Look for the embedded JSON in the script tags (The most reliable way)
    # This data is often in a tag with id="initial-state"
    soup = BeautifulSoup(content, 'html.parser')
    initial_state_tag = soup.find('script', id='initial-state')
    if initial_state_tag:
        try:
            # The string is base64 encoded sometimes, or just JSON
            # In the new design, it's often a complex nested JSON
            # We'll just regex search for track/artist patterns inside it
            pass
        except:
            pass

    # Method 2: Robust Regex for Track and Artist names
    # Spotify uses specific patterns for metadata.
    # We look for "name":"..." followed shortly by "artists":[{"name":"..."
    # or "artist_name":"..."
    
    # Pattern for tracks in the "items" array
    items = re.findall(r'{"track":{"album":{.*?,"name":"([^"]+)"},"artists":\[{"external_urls":{.*?,"name":"([^"]+)"}', content)
    
    if not items:
        # Try finding anything that looks like "name":"TRACK" and "name":"ARTIST" in a track object
        # This regex is a bit greedy but works for most public pages
        items = re.findall(r'{"name":"([^"]+)","uri":"spotify:track:[^"]+","artists":\[{"name":"([^"]+)"', content)
        
    if not items:
        # Fallback for older or different layouts
        items = re.findall(r'{"name":"([^"]+)","uri":"spotify:track:[^"]+","artist_name":"([^"]+)"', content)

    for track_name, artist_name in items:
        # Clean up common junk characters
        track_name = track_name.encode('utf-8').decode('unicode-escape')
        artist_name = artist_name.encode('utf-8').decode('unicode-escape')
        
        full_name = f"{artist_name} - {track_name}"
        if full_name not in tracks and track_name not in ["Home", "Search", "Your Library"]:
            tracks.append(full_name)
            
    return tracks

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraped_download.py <spotify_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    tracks = scrape_spotify_playlist(url)
    
    if not tracks:
        print("\n❌ No tracks found automatically.")
        print("1. Make sure the playlist is PUBLIC.")
        print("2. If it still fails, you can manually create a file called 'tracks.txt'")
        print("   with the song names (Artist - Song) and the bot will find them!")
        sys.exit(1)
        
    print(f"✅ Found {len(tracks)} tracks!")
    
    # Save tracks to a file
    with open("temp_tracks.txt", "w", encoding="utf-8") as f:
        for t in tracks:
            f.write(t + "\n")
            
    print("Starting download with spotdl...")
    subprocess.run(["spotdl", "download", "temp_tracks.txt", "--format", "mp3", "--output", "{artist}/{album}/{title}.{output-ext}"])
