import os
import aiohttp
import asyncio
import base64
import logging
from config import DB_PATH

logger = logging.getLogger("DBSync")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Kanha140/AUTH")
FILE_PATH = "data/auth_bot.db"

async def restore_database():
    """Restores database from GitHub repository on startup to ensure zero data loss."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.info("GitHub credentials not configured, skipping cloud DB restore.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content_b64 = data.get("content", "")
                    if content_b64:
                        raw_bytes = base64.b64decode(content_b64)
                        with open(DB_PATH, "wb") as f:
                            f.write(raw_bytes)
                        logger.info(f"Database successfully restored from GitHub ({len(raw_bytes)} bytes)!")
                        return True
                else:
                    logger.info(f"No existing remote DB backup found on GitHub (status {resp.status}).")
    except Exception as e:
        logger.warning(f"Failed to restore DB from GitHub: {e}")
    return False

async def backup_database():
    """Uploads/syncs the SQLite database to GitHub repository to guarantee persistence."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False

    if not os.path.exists(DB_PATH):
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    try:
        with open(DB_PATH, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Get existing file SHA if already exists
        sha = None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sha = data.get("sha")

            payload = {
                "message": "Automated cloud backup: auth_bot.db",
                "content": content_b64,
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha

            async with session.put(url, headers=headers, json=payload, timeout=15) as put_resp:
                if put_resp.status in (200, 201):
                    logger.info("Database successfully backed up to GitHub cloud storage!")
                    return True
                else:
                    text = await put_resp.text()
                    logger.warning(f"Failed to backup DB to GitHub (status {put_resp.status}): {text}")
    except Exception as e:
        logger.warning(f"DB cloud backup encountered error: {e}")
    return False

def trigger_cloud_backup():
    """Non-blocking call to schedule cloud backup."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(backup_database())
    except RuntimeError:
        pass

async def periodic_db_sync_task():
    """Periodically syncs database to GitHub cloud every 5 minutes."""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        await backup_database()
