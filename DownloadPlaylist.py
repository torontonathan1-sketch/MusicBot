import sys
import subprocess
import re
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Please provide a playlist URL.")
        return

    url = sys.argv[1]
    MUSIC_ROOT = Path(__file__).parent.absolute()
    PLAYLIST_DIR = MUSIC_ROOT / "Playlists"
    PLAYLIST_DIR.mkdir(exist_ok=True)

    if "spotify.com" in url:
        print("\n🎧 Detected Spotify link! Using Zotify...")
        # Put it in Playlists/PlaylistName/
        cmd = [
            "py", "-m", "zotify",
            url,
            "--root-path", str(PLAYLIST_DIR),
            "--output", "{playlist}/{playlist_num} - {song_name}.{ext}",
            "--download-format", "mp3",
            "--skip-existing", "true"
        ]
        subprocess.run(cmd)
    else:
        print("\n🎥 Detected YouTube/Other link! Using yt-dlp...")
        FFMPEG_PATH = r"C:\Users\Steve\.spotdl"
        output_template = str(PLAYLIST_DIR / "%(playlist|Unknown Playlist)s" / "%(playlist_index)02d - %(title)s.%(ext)s")
        cmd = [
            "yt-dlp",
            url,
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "4",
            "--ffmpeg-location", FFMPEG_PATH,
            "--output", output_template,
            "--write-thumbnail",
            "--add-metadata",
            "--postprocessor-args", "ffmpeg:-id3v2_version 3",
            "--yes-playlist",
            "--ignore-errors",
            "--trim-filenames", "100"
        ]
        subprocess.run(cmd)
        
        # Make folder.jpg for each playlist directory
        for p_dir in PLAYLIST_DIR.iterdir():
            if not p_dir.is_dir(): continue
            jpg_path = p_dir / "folder.jpg"
            images = []
            for ext in ["*.jpg", "*.webp", "*.png"]:
                images.extend(p_dir.glob(ext))
            
            if not jpg_path.exists() and images:
                source_img = images[0]
                try:
                    subprocess.run([os.path.join(FFMPEG_PATH, "ffmpeg.exe"), "-i", str(source_img), "-vf", "scale=150:150", "-q:v", "5", str(jpg_path), "-y", "-v", "quiet"], timeout=30)
                except: pass
                
            for img in images:
                if img.name != "folder.jpg":
                    try: img.unlink()
                    except: pass
        
    print(f"\n✅ Playlist processing complete! Check: {PLAYLIST_DIR.absolute()}")

if __name__ == "__main__":
    main()
