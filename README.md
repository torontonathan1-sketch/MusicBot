# 🎵 Music Bot 2.0

An autonomous, highly optimized music discography downloader that perfectly structures tracks for offline MP3 players. It uses the MusicBrainz database to dynamically identify an artist's discography, picks their Top 10 most popular studio albums (guaranteeing the newest release and Deluxe editions), and downloads them cleanly via `yt-dlp`.

## Features
- **Intelligent Discography Filtering:** Automatically prioritizes true popularity (based on global release counts) and hunts down Deluxe editions to maximize your song count.
- **Hardware-Ready MP3 Optimization:** Perfect for older MP3 players. Shrinks album artwork to a precise 150x150 `folder.jpg`, strictly avoids memory-crashing embedded art, and applies highly compatible ID3v2.3 tags.
- **Infinite Notion Auto-Sync:** Add artists to a Notion checklist on your phone, and the bot will pull them down in the background automatically.
- **Spotify & YouTube Playlists:** Includes a dedicated playlist downloader script.

## Setup Instructions

1. **Download the Bot:** Click the green `Code` button above and select `Download ZIP`, then extract it to a folder (like `Music`).
2. **Install Python:** Ensure Python is installed on your Windows computer.
3. **Install Requirements:** Open a terminal in the folder and run:
   ```bash
   pip install yt-dlp zotify requests tqdm python-dotenv
   ```
4. **Notion Setup (Optional):** Create a `.env` file with your Notion credentials if you want to use the checklist sync:
   ```env
   NOTION_TOKEN=your_integration_token
   PAGE_ID=your_page_id
   ```

## How to Run

- **Full Discographies:** Double click `OrganizeLibrary.ps1` to start the autonomous downloader! It will read your Notion list and build out the artist folders.
- **Playlists:** Double click `DownloadPlaylist.ps1` and paste any YouTube or Spotify playlist URL.
