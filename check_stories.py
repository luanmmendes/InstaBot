import requests
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# ── credentials from GitHub Secrets ──────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CINEMA_ACCOUNT   = os.environ["CINEMA_ACCOUNT"]
APIFY_TOKEN      = os.environ["APIFY_TOKEN"]

# ── file that remembers which stories were already sent ───────────────────────
SENT_IDS_FILE = "already_sent.json"

def load_sent_ids():
    if Path(SENT_IDS_FILE).exists():
        with open(SENT_IDS_FILE) as f:
            return set(json.load(f))
    return set()

def save_sent_ids(ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(list(ids), f)

# ── fetch stories from Apify ──────────────────────────────────────────────────
def fetch_stories():
    actor_id = "louisdeconinck~instagram-story-details-scraper"
    run_url  = f"https://api.apify.com/v2/actors/{actor_id}/runs?token={APIFY_TOKEN}"

    print(f"Starting Apify actor for @{CINEMA_ACCOUNT}...")
    run = requests.post(run_url, json={"usernames": [CINEMA_ACCOUNT]}).json()

    run_id = run.get("data", {}).get("id")
    if not run_id:
        print(f"Failed to start actor: {run}")
        return []

    # wait for the run to finish (max 5 minutes)
    for i in range(30):
        time.sleep(10)
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
        status = requests.get(status_url).json().get("data", {}).get("status")
        print(f"Run status: {status}")
        if status == "SUCCEEDED":
            break
        if status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            print("Actor run failed.")
            return []

    # get results
    dataset_id = requests.get(
        f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    ).json().get("data", {}).get("defaultDatasetId")

    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
    items = requests.get(items_url).json()
    print(f"Found {len(items)} stories.")
    return items

# ── send a photo to Telegram ──────────────────────────────────────────────────
def send_photo_url(url, caption=""):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    response = requests.post(api_url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": url,
        "caption": caption
    })
    return response.ok

# ── send a video to Telegram ──────────────────────────────────────────────────
def send_video_url(url, caption=""):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    response = requests.post(api_url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "video": url,
        "caption": caption
    })
    return response.ok

# ── main logic ────────────────────────────────────────────────────────────────
def main():
    sent_ids = load_sent_ids()
    new_ids  = set()

    stories = fetch_stories()

    if not stories:
        print("No stories found.")
        save_sent_ids(sent_ids)
        return

    for story in stories:
        story_id  = str(story.get("id") or story.get("pk") or story.get("url"))
        media_url = story.get("videoUrl") or story.get("imageUrl") or story.get("displayUrl")
        is_video  = bool(story.get("videoUrl"))

        if not media_url:
            print(f"No media URL found for story {story_id}, skipping.")
            continue

        if story_id in sent_ids:
            print(f"Already sent: {story_id}, skipping.")
            continue

        caption = f"🎬 Nova story de @{CINEMA_ACCOUNT}"
        timestamp = story.get("timestamp") or story.get("takenAtTimestamp")
        if timestamp:
            dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            caption += f"\n🕐 {dt.strftime('%d/%m/%Y %H:%M')} UTC"

        if is_video:
            success = send_video_url(media_url, caption)
        else:
            success = send_photo_url(media_url, caption)

        if success:
            print(f"Sent story {story_id} ✅")
            new_ids.add(story_id)
        else:
            print(f"Failed to send story {story_id} ❌")

    save_sent_ids(sent_ids | new_ids)
    print(f"Done. {len(new_ids)} new stories sent.")

if __name__ == "__main__":
    main()