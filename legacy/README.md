# 🗄️ Legacy Archive

This folder contains **old, superseded scripts** that are no longer part of the active music bot workflow.

They are kept here for historical reference only — do not use them for downloads.

---

## 📁 Contents

### `MusicBot.ps1`
- **Original version** of the music bot launcher.
- **Technology used:** [Zotify](https://github.com/zotify-dev/zotify) — a Spotify downloader that required a direct Spotify login.
- **Output path:** Hardcoded to `f:\Music 2026`.
- **Why replaced:** Zotify became unreliable and required account login. The current system uses `yt-dlp` + iTunes + MusicBrainz for a completely credential-free, stable, and more powerful download pipeline.
- **Superseded by:** `OrganizeLibrary.ps1` + `PowerDownload.py`
