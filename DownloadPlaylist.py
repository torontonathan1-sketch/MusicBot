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
            "--add-metadata",
            "--postprocessor-args", "ffmpeg:-id3v2_version 3",
            "--yes-playlist",
            "--ignore-errors",
            "--trim-filenames", "100"
        ]
        subprocess.run(cmd)

    print(f"\n✅ Playlist processing complete! Check: {PLAYLIST_DIR.absolute()}")

if __name__ == "__main__":
    main()
