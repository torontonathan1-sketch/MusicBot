# 🎵 Notion & Spotify Music Bot 2.0

An autonomous, premium music bot designed to perfectly organize, download, and tag music discographies for your local library or offline MP3 players. It leverages Spotify's public and official APIs to identify artists' popular catalogs, guarantees their latest release, fetches unlimited tracks from Spotify playlists, and logs age-verification or connection errors for easy manual retrieval later.

---

## ✨ Premium Features

### 🎧 Spotify Artist Discovery
*   **Top 9 Albums + Latest Release:** Instead of dry database mappings, the bot goes straight to Spotify to fetch the artist's **Top 9 popular releases** and their **Latest Release** (for a perfect 10-album collection!).
*   **Deluxe Album Prioritization:** Fetches complete track listings directly from Spotify's public embed database.

### 🚀 Unlimited Playlist Scalability
*   **Dual-Mode Playlist Downloader:** Downloads playlists of **any size** (thousands of tracks!).
*   **Official Spotify API Mode:** By simply adding API credentials to `.env`, the bot authenticates and paginates endlessly through massive playlists.
*   **Fallback Scraper Mode:** If keys are absent, it safely falls back to downloading the first 100 tracks unauthenticated.

### 📝 Notion Database Synchronization
*   Add and prioritize artists from your phone on the go! The bot syncs your Notion database checklist in the background and keeps your library up to date.

### 🛠️ Failed Downloads Error Tracker
*   If a download fails due to age-verification checks (`ERROR: Sign in to confirm your age`), geographic restrictions, or network blocks, the bot logs it in `failed_downloads.txt`. 
*   Includes the exact **Artist**, **Album**, **Track**, and the **Error Message** so you can grab them separately later.

---

## 🚀 Quick Start & Setup

For a complete step-by-step setup guide including environment variables, Windows execution policy unlocking, Notion page connection, and Spotify developer key setups, see our **[Premium Installation Guide](file:///d:/Music/INSTALLATION_GUIDE.md)**!

### 1. Prerequisites
*   Ensure Python 3.12 is installed.
*   Install required Python modules:
    ```powershell
    pip install requests tqdm python-dotenv yt-dlp
    ```

### 2. Configure Environment
Create a `.env` file in the folder:
```env
# Notion Setup
NOTION_TOKEN=secret_yourNotionToken
NOTION_DB_ID=yourDatabaseID

# Spotify API Setup (Optional - unlocks unlimited playlist track fetching)
SPOTIFY_CLIENT_ID=yourClientID
SPOTIFY_CLIENT_SECRET=yourClientSecret
```

---

## 🏃 Running the Bot

### 🔄 Sync Notion Checklist & Download Albums
Double-click `OrganizeLibrary.ps1` or run it in PowerShell:
```powershell
.\OrganizeLibrary.ps1
```

### 📥 Download Spotify/YouTube Playlists Directly
Double-click `DownloadPlaylist.ps1` or run it in PowerShell:
```powershell
.\DownloadPlaylist.ps1
```
*   Enter your Spotify or YouTube playlist URL when prompted, and watch it download!
