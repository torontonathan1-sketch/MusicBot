import requests
import os

from dotenv import load_dotenv
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

def sync_notion():
    url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    print("🔄 Syncing with Notion...")
    
    tracks = []
    has_more = True
    next_cursor = None
    
    while has_more:
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
            
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return

        data = response.json()
        
        for block in data.get("results", []):
            btype = block["type"]
            if btype in ("to_do", "bulleted_list_item"):
                text = block[btype]["rich_text"]
                if text:
                    item = text[0]["plain_text"].strip()
                    if item:
                        tracks.append(item)
                        
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
    
    if not tracks:
        print("⚠️ No checklist items found in Notion.")
        return

    tracks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks.txt")
    with open(tracks_path, "w", encoding="utf-8") as f:
        for t in tracks:
            f.write(t + "\n")
            
    print(f"✅ Success! Updated tracks.txt with {len(tracks)} items from Notion.")

if __name__ == "__main__":
    sync_notion()
