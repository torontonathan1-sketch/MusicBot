# 🎵 Premium Music Bot Setup Guide

Welcome to the ultimate setup guide for the **Notion & Spotify Music Bot**. Follow these steps to install the required tools, configure integrations, and get your music library downloading in minutes!

---

## 🛠️ Prerequisites & Installation

### 1. Python 3.12 (or newer)
This bot requires Python. If you do not have Python installed:
*   Open **PowerShell** as Administrator and run:
    ```powershell
    winget install Python.Python.3.12
    ```
*   Restart your PowerShell terminal so Python is added to your environment `PATH`.

### 2. Install Required Python Dependencies
Run this command in the bot's workspace (`d:\Music`) to install the core libraries:
```powershell
pip install requests tqdm python-dotenv yt-dlp
```

### 3. Unlock Script Execution (Windows Only)
By default, Windows blocks custom PowerShell scripts (`.ps1`). To enable running this bot's launcher scripts:
*   Open **PowerShell** and run:
    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```

---

## 📝 Integration Setup

### 🚀 Part A: Notion Checklist Sync (Required)
The bot syncs your music download checklist directly from Notion!

1. Go to [Notion Integrations](https://www.notion.so/my-integrations) and click **+ New integration**.
2. Name it `Music Bot`, select your workspace, and save to get your **Internal Integration Token** (begins with `secret_`).
3. Open your Notion page where your music checklist table is.
4. Click the three dots `...` in the top right → **Connections** → **Connect to** → Search for `Music Bot` and approve.
5. Copy your **Notion Database ID**:
   * If your page URL is: `https://www.notion.so/myworkspace/a8d87a4192b04f32a76f62089f81df2f?v=...`
   * Your Database ID is the long code between `myworkspace/` and `?v=`: `a8d87a4192b04f32a76f62089f81df2f`
6. Save these keys in your `d:\Music\.env` file:
   ```env
   NOTION_TOKEN=secret_yourNotionTokenHere
   NOTION_DB_ID=a8d87a4192b04f32a76f62089f81df2f
   ```

---

### 🎨 Part B: Spotify Developer Keys (Optional but Recommended)
Adding Spotify keys lifts the **100-track playlist limit** and allows page-by-page fetching of playlists with **thousands of tracks**!

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app**:
   * **App name:** `Music Library Bot`
   * **Redirect URI:** `http://localhost:3000` (can be anything)
   * Check **Web API** and save.
3. Click **Settings** on your new app to copy your **Client ID** and **Client Secret**.
4. Add them to your `d:\Music\.env` file:
   ```env
   SPOTIFY_CLIENT_ID=yourSpotifyClientID
   SPOTIFY_CLIENT_SECRET=yourSpotifyClientSecret
   ```

> [!NOTE]
> If these credentials are not provided, the bot runs in **Credential-Free Mode**, utilizing public scraping to download the first 100 tracks of Spotify playlists and the top albums.

---

## 🏃 Running the Bot

### 1. Synchronize & Organize Library
Run the main orchestrator script:
```powershell
.\OrganizeLibrary.ps1
```
*   This will check your Notion checklist, fetch any artists you marked, query Spotify for their **Top 9 Albums + Latest Release**, and download them.

### 2. Download Playlists Directly
To download an entire Spotify playlist or search term list:
```powershell
.\DownloadPlaylist.ps1
```
*   Enter your Spotify playlist URL (e.g. `https://open.spotify.com/playlist/...`) and let it download!

---

## ⚠️ Troubleshooting & Error Logs

> [!IMPORTANT]
> **Failed Downloads Logging:**
> If a song fails to download due to YouTube regional blocks, account locks, or **Age-Verification Problems**, the bot will silently record it inside `d:\Music\failed_downloads.txt`.
> 
> You can open this file anytime to see:
> * Exactly which song/album/artist failed.
> * The specific error message returned by YouTube (e.g., `ERROR: Sign in to confirm your age`).
> 
> You can then download these specific items manually later or using a logged-in browser!
