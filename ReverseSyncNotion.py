import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


MUSIC_ROOT = Path(__file__).parent.absolute()
load_dotenv(MUSIC_ROOT / ".env")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
REVERSE_PAGE_ID = os.getenv("REVERSE_PAGE_ID")
REFRESH_SECONDS = int(os.getenv("REVERSE_NOTION_REFRESH_SECONDS", "60"))


def read_clean_failed_list() -> list[str]:
    clean_file = MUSIC_ROOT / "failed_downloads_clean_list.txt"
    if not clean_file.exists():
        return []

    lines = [line.strip() for line in clean_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines


def write_notion(lines: list[str]) -> bool:
    if not NOTION_TOKEN or not REVERSE_PAGE_ID:
        print("Missing NOTION_TOKEN or REVERSE_PAGE_ID in .env")
        return False

    url = f"https://api.notion.com/v1/blocks/{REVERSE_PAGE_ID}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    # Clear existing children first by appending below a divider-style note is not supported directly.
    # We instead overwrite by leaving the page's existing manual content intact and placing a fresh section at the bottom.
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Clean Failed Downloads"}}]
            },
        }
    ]

    for line in lines:
        children.append(
            {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                },
            }
        )

    payload = {"children": children}
    response = requests.patch(url, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 201):
        print(f"Notion error: {response.status_code} - {response.text}")
        return False

    print(f"Updated Notion reverse page with {len(lines)} items.")
    return True


def main() -> None:
    last_snapshot = None
    print("Watching failed_downloads_clean_list.txt and syncing to Notion. Press Ctrl+C to stop.")
    while True:
        lines = read_clean_failed_list()
        snapshot = "\n".join(lines)
        if snapshot != last_snapshot:
            if lines:
                write_notion(lines)
            else:
                print("No clean failed-download lines found yet.")
            last_snapshot = snapshot
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()
