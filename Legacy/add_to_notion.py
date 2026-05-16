import os
import requests
from dotenv import load_dotenv

load_dotenv("F:/Music/.env")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

artists = [
    "Adele",
    "Aerosmith",
    "Backstreet Boys",
    "Linkin Park",
    "Maroon 5",
    "Rihanna",
    "Shakira",
    "Shawn Mendes",
    "U2"
]

url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

children = []
for a in artists:
    children.append({
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": a}}]
        }
    })

response = requests.patch(url, headers=headers, json={"children": children})
if response.status_code == 200:
    print("Successfully added artists to Notion!")
else:
    print(f"Error: {response.status_code} - {response.text}")
