import instaloader
import requests
import os
import json
from pathlib import Path
from datetime import datetime, timezone

# ── credentials from GitHub Secrets ──────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CINEMA_ACCOUNT   = os.environ["CINEMA_ACCOUNT"]   # e.g. "cinemaxyz"

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

# ── send a photo to Telegram ──────────────────────────────────────────────────
def send_photo(image_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(image_path, "rb") as photo:
        response = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption
        }, files={"photo": photo})
    return response.ok

# ── send a video to Telegram ──────────────────────────────────────────────────
def send_video(video_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    with open(video_path, "rb") as video:
        response = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": caption
        }, files={"video": video})
    return response.ok

# ── main logic ────────────────────────────────────────────────────────────────
def main():
    sent_ids = load_sent_ids()
    new_ids  = set()

    L = instaloader.Instaloader(
        download_video_thumbnails=False,
        save_metadata=False,
        post_metadata_txt_pattern=""
    )

    try:
        profile = instaloader.Profile.from_username(L.context, CINEMA_ACCOUNT)
    except Exception as e:
        print(f"Could not load profile '{CINEMA_ACCOUNT}': {e}")
        return

    stories = L.get_stories(userids=[profile.userid])

    for story in stories:
        for item in story.get_items():
            story_id = str(item.mediaid)

            if story_id in sent_ids:
                print(f"Already sent: {story_id}, skipping.")
                continue

            # download the story item into a local folder
            folder = Path("stories")
            folder.mkdir(exist_ok=True)
            L.download_storyitem(item, target=folder)

            # find the downloaded file (image or video)
            files = sorted(folder.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            media_file = next((f for f in files if f.suffix in [".jpg", ".mp4", ".webp"]), None)

            if not media_file:
                print(f"No media file found for story {story_id}, skipping.")
                continue

            caption = f"🎬 New story from {CINEMA_ACCOUNT}"
            posted_at = datetime.fromtimestamp(item.date_utc.replace(tzinfo=timezone.utc).timestamp())
            caption += f"\n🕐 Posted at {posted_at.strftime('%Y-%m-%d %H:%M')} UTC"

            if media_file.suffix == ".mp4":
                success = send_video(media_file, caption)
            else:
                success = send_photo(media_file, caption)

            if success:
                print(f"Sent story {story_id} ✅")
                new_ids.add(story_id)
            else:
                print(f"Failed to send story {story_id} ❌")

    # save updated sent IDs
    save_sent_ids(sent_ids | new_ids)
    print(f"Done. {len(new_ids)} new stories sent.")

if __name__ == "__main__":
    main()
