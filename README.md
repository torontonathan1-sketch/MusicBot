# 🎵 Ultimate Notion & iTunes Music Bot 2.2 🚀

An autonomous, premium music downloader designed to perfectly organize, download, and tag music discographies for your local library or offline MP3 players. It leverages the **iTunes Search API** (free & key-less) to query real popular catalogs, captures **the single newest release within the last 1 year**, fetches **Spotify playlists of any size**, and handles **Notion checklists** dynamically in the background!

---

## ✨ Features

*   **⚡ Smart Skip & Auto-Fill:** The bot checks if a song file already exists in `/Artist/Album/Song.mp3` or if an album is already at least 85% downloaded. It will **instantly skip** existing files and **only download the missing songs/albums** you add! Downloads are lightning-fast and never duplicate.
*   **🔥 Real Popularity Rankings:** Uses the Apple iTunes Search API (no credentials needed) to fetch the artist's real, iconic albums (e.g. *Parachutes*, *A Rush of Blood to the Head*, *X&Y* for Coldplay) instead of obscure bootlegs.
*   **💿 Deluxe Album Prioritization:** Automatically identifies, prioritizes, and resolves Deluxe, Expanded, and Bonus editions, cleanly removing standard duplicates from the queue.
*   **📅 Newest 1-Year cutoff:** Isolates the single newest album released within the last 365 days to keep your library completely up to date.
*   **🔄 Notion Checklist Sync:** Add artists from your Notion app on your phone, and the bot automatically pulls, syncs, and appends them to its target list every 5 artists in the background!
*   **🎧 Unlimited Playlists:** Seamlessly fetches and downloads Spotify playlists of any size.
*   **⚠️ Failed Downloads Tracker:** If a download fails due to YouTube restrictions or age-verification (`ERROR: Sign in to confirm your age`), it silently logs it in `failed_downloads.txt` so you can retrieve it later.
*   **📌 Permanent Failure Log Policy:** ailed_downloads.txt is intended to stay in GitHub history and should not be deleted, even if it looks messy.

---

## 🛠️ Step-by-Step Setup (For Complete Beginners)

Follow these simple steps to set up and run the bot on Windows—no programming experience required!

### Step 1: Install Python & Unblock Scripts
1. Open your Windows **Start Menu**, search for **PowerShell**, and open it.
2. Copy and paste this single command, then press **Enter**:
   ```powershell
   winget install Python.Python.3.12 ; Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
   ```
3. **Restart your PowerShell window** so Windows registers the newly installed Python.

### Step 2: Install Bot Dependencies
Navigate to the directory where the bot is located (e.g. `d:\Music` or wherever your folder is) and run:
```powershell
pip install requests tqdm python-dotenv yt-dlp
```

---

## 📝 Background Requirements

To run this bot, make sure you have:
1.  **A Notion Account:** (Free) Used to manage your checklist. You will add artist names to a table inside Notion on your computer or your phone.
2.  **PowerShell Console:** Opened in your bot folder (`d:\Music`) to paste execution commands.
3.  **Active Internet Connection:** Used to query iTunes and fetch the audio streams from YouTube.

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

Open PowerShell in your bot directory (`d:\Music`) and copy-paste the exact commands below to run:

### 1. Run the Main Bot (Notion Sync & Artists)
To sync with Notion and download/auto-fill all missing albums and tracks, paste this command and press **Enter**:
```powershell
.\OrganizeLibrary.ps1
```
*   The bot will ask to sync with Notion, scan your checklist, look up their **Top 9 Albums + 1 Newest Release**, check your local folder for existing files, and download **only the missing tracks** automatically!

### 2. Run the Playlist Downloader
To download an entire Spotify playlist directly, paste this command and press **Enter**:
```powershell
.\DownloadPlaylist.ps1
```
*   Paste your Spotify playlist URL (e.g. `https://open.spotify.com/playlist/...`) and press **Enter**. The bot will download every song inside!

---

## 📁 How Your Files Are Organized
Everything is automatically tagged and sorted into clean, year-less directories:
📁 `d:\Music\Artist Name\Album Title\Song Name.mp3`

Enjoy your premium offline music library! 🎧

## Age-Restricted Tracks

Preferred method: export YouTube cookies to a Netscape-format file and set:

```env
YT_COOKIES_FILE=D:\Music\cookies.txt
```

The bot will use `--cookies` automatically when the file exists. Browser-cookie mode remains optional via `YT_ENABLE_BROWSER_COOKIES=true`.