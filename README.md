# 🎵 Ultimate Notion & iTunes Music Bot 2.0 🚀

An autonomous, premium music downloader designed to perfectly organize, download, and tag music discographies for your local library or offline MP3 players. It leverages the **iTunes Search API** (free & key-less) to query real popular catalogs, captures **the single newest release within the last 1 year**, fetches **Spotify playlists of any size**, and handles **Notion checklists** dynamically in the background!

---

## ✨ Features
*   **🔥 Real Popularity Rankings:** Uses the Apple iTunes Search API (no credentials needed) to fetch the artist's real, iconic albums (e.g. *Parachutes*, *A Rush of Blood to the Head*, *X&Y* for Coldplay) instead of obscure bootlegs.
*   **💿 Deluxe Album Prioritization:** Automatically identifies, prioritizes, and resolves Deluxe, Expanded, and Bonus editions, cleanly removing standard duplicates from the queue.
*   **📅 Newest 1-Year cutoff:** Isolates the single newest album released within the last 365 days to keep your library completely up to date.
*   **🔄 Notion Checklist Sync:** Add artists from your Notion app on your phone, and the bot automatically pulls, syncs, and appends them to its target list every 5 artists in the background!
*   **🎧 Unlimited Playlists:** Seamlessly fetches and downloads Spotify playlists of any size.
*   **⚠️ Failed Downloads Tracker:** If a download fails due to YouTube restrictions or age-verification (`ERROR: Sign in to confirm your age`), it silently logs it in `failed_downloads.txt` so you can retrieve it later.

---

## 🛠️ Step-by-Step Setup (For Complete Beginners)

Follow these simple steps to set up and run the bot on Windows—no programming experience required!

### Step 1: Install Python & Unblock Scripts
1. Open your Windows **Start Menu**, search for **PowerShell**, and open it.
2. Copy and paste this single command, then press **Enter**:
   ```powershell
   winget install Python.Python.3.12 ; Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
   ```
3. Restart your PowerShell window so Windows registers the newly installed Python.

### Step 2: Install Bot Dependencies
Navigate to the directory where the bot is located (e.g. `d:\Music` or wherever your folder is) and run:
```powershell
pip install requests tqdm python-dotenv yt-dlp
```

---

## 📝 Setup Integrations (Creating Your Keys)

### Part A: Notion Checklist Sync (Highly Recommended)
Sync your music download list directly from your Notion workspace!

1. Go to **[notion.so/my-integrations](https://www.notion.so/my-integrations)** and click **+ New integration**.
2. Name it `Music Bot`, select your workspace, and save to get your **Internal Integration Token** (starts with `secret_`).
3. Open your Notion page containing your checklist table.
4. Click the three dots `...` in the top right corner → **Connections** → **Connect to** → search for `Music Bot` and approve.
5. Copy your **Notion Database ID**:
   * If your page URL is `https://www.notion.so/myworkspace/a8d87a4192b04f32a76f62089f81df2f?v=...`
   * Your Database ID is the long code between `myworkspace/` and `?v=`: `a8d87a4192b04f32a76f62089f81df2f`
6. Create a file named `.env` in the bot directory and add these lines:
   ```env
   NOTION_TOKEN=secret_yourNotionTokenHere
   NOTION_DB_ID=a8d87a4192b04f32a76f62089f81df2f
   ```

---

### Part B: Spotify Developer Keys (Optional)
*Adding Spotify keys lifts the 100-track playlist limit and lets you pull playlists of any size.*

1. Go to **[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)** and log in.
2. Click **Create app**:
   * **App name:** `Music Bot`
   * **Redirect URI:** `http://localhost`
   * Check the terms and save.
3. Click **Settings** to copy your **Client ID** and **Client Secret**.
4. Open your `.env` file and append:
   ```env
   SPOTIFY_CLIENT_ID=yourSpotifyClientID
   SPOTIFY_CLIENT_SECRET=yourSpotifyClientSecret
   ```

---

## 🏃 How to Run the Bot

### 1. The Main Bot (Notion Sync & Artists)
Double-click `OrganizeLibrary.ps1` or run it in PowerShell:
```powershell
.\OrganizeLibrary.ps1
```
*   The bot will ask to sync with Notion, check your artist list, query iTunes/Spotify for their **Top 9 Albums + 1 Newest Release**, and download them automatically!

### 2. Spotify Playlist Downloader
Double-click `DownloadPlaylist.ps1` or run it in PowerShell:
```powershell
.\DownloadPlaylist.ps1
```
*   Paste your Spotify playlist URL (e.g. `https://open.spotify.com/playlist/...`) and press **Enter**. The bot will download every song inside!

---

## 📁 How Your Files Are Organized
Everything is automatically tagged and sorted into clean, year-less directories:
📁 `d:\Music\Artist Name\Album Title\Song Name.mp3`

Enjoy your premium offline music library! 🎧
