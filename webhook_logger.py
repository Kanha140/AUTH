import aiohttp
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import database
from config import WEBHOOK_URL

logger = logging.getLogger("WebhookLogger")

def get_active_webhook_url() -> str:
    url = database.get_setting("webhook_url", "")
    if not url:
        url = WEBHOOK_URL
    return url.strip()

async def send_webhook(embed_dict: Dict[str, Any]):
    url = get_active_webhook_url()
    if not url:
        return

    payload = {
        "username": "Axenor Auth Logs",
        "avatar_url": "https://cdn.discordapp.com/attachments/1066060000000000000/1066060000000000000/shield.png",
        "embeds": [embed_dict]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=5) as resp:
                if resp.status not in (200, 204):
                    text = await resp.text()
                    logger.warning(f"Webhook post returned status {resp.status}: {text}")
    except Exception as e:
        logger.error(f"Failed to post to webhook: {e}")

async def log_key_generated(username: str, password: str, days: int, expires_at: str, created_by: int, channel_id: int):
    embed = {
        "title": "🔑 License Key Generated",
        "color": 0x2ECC71,  # Green
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "👤 Username", "value": f"`{username}`", "inline": True},
            {"name": "🔒 Password", "value": f"`{password}`", "inline": True},
            {"name": "⏳ Duration", "value": f"`{days} Days`", "inline": True},
            {"name": "📅 Expires At", "value": f"`{expires_at}`", "inline": False},
            {"name": "🛠️ Reseller / Creator", "value": f"<@{created_by}> (`{created_by}`)", "inline": True},
            {"name": "📍 Channel", "value": f"<#{channel_id}>", "inline": True},
            {"name": "💻 HWID Status", "value": "🟢 Unbound (Will auto-bind on 1st login)", "inline": False}
        ],
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_key_deleted(username: str, deleted_by: int, channel_id: Optional[int] = None):
    fields = [
        {"name": "👤 Target Username", "value": f"`{username}`", "inline": True},
        {"name": "👮 Action By", "value": f"<@{deleted_by}> (`{deleted_by}`)", "inline": True}
    ]
    if channel_id:
        fields.append({"name": "📍 Channel", "value": f"<#{channel_id}>", "inline": True})

    embed = {
        "title": "🗑️ License Key Deleted",
        "color": 0xE74C3C,  # Red
        "timestamp": datetime.utcnow().isoformat(),
        "fields": fields,
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_hwid_reset(username: str, reset_by: int, old_hwid: Optional[str] = None):
    embed = {
        "title": "🔄 HWID Reset Executed",
        "color": 0x3498DB,  # Blue
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "👤 Target Username", "value": f"`{username}`", "inline": True},
            {"name": "👮 Reset By", "value": f"<@{reset_by}> (`{reset_by}`)", "inline": True},
            {"name": "💻 Cleared HWID", "value": f"`{old_hwid}`" if old_hwid else "*None*", "inline": False},
            {"name": "📌 Next Step", "value": "Device slot open. Next client login will auto-bind new HWID.", "inline": False}
        ],
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_reseller_added(reseller_id: int, channel_id: int, added_by: int, category_name: Optional[str] = None):
    fields = [
        {"name": "👤 Reseller", "value": f"<@{reseller_id}> (`{reseller_id}`)", "inline": True},
        {"name": "👑 Added By", "value": f"<@{added_by}> (`{added_by}`)", "inline": True},
        {"name": "📍 Reseller Channel", "value": f"<#{channel_id}>", "inline": False}
    ]
    if category_name:
        fields.append({"name": "📁 Category", "value": f"`{category_name}`", "inline": True})

    embed = {
        "title": "💼 New Reseller Added",
        "color": 0x9B59B6,  # Purple
        "timestamp": datetime.utcnow().isoformat(),
        "fields": fields,
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_reseller_removed(channel_name: str, removed_by: int):
    embed = {
        "title": "🚫 Reseller Removed",
        "color": 0xE67E22,  # Orange
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "📍 Channel Removed", "value": f"`{channel_name}`", "inline": True},
            {"name": "👮 Removed By", "value": f"<@{removed_by}> (`{removed_by}`)", "inline": True}
        ],
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_owner_added(new_owner_id: int, added_by: int):
    embed = {
        "title": "👑 Co-Owner Added",
        "color": 0xF1C40F,  # Gold
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "👑 New Owner", "value": f"<@{new_owner_id}> (`{new_owner_id}`)", "inline": True},
            {"name": "🛡️ Authorized By", "value": f"<@{added_by}> (`{added_by}`)", "inline": True}
        ],
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_owner_removed(removed_owner_id: int, removed_by: int):
    embed = {
        "title": "⛔ Co-Owner Removed",
        "color": 0xC0392B,  # Dark Red
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "👤 Removed Owner", "value": f"<@{removed_owner_id}> (`{removed_owner_id}`)", "inline": True},
            {"name": "🛡️ Removed By", "value": f"<@{removed_by}> (`{removed_by}`)", "inline": True}
        ],
        "footer": {"text": "Axenor Auth Logging System"}
    }
    await send_webhook(embed)

async def log_client_login(username: str, status: str, message: str, hwid: str, ip: str = "Unknown"):
    is_success = "SUCCESS" in status
    is_mismatch = "MISMATCH" in status

    color = 0x2ECC71 if is_success else (0xE74C3C if is_mismatch else 0xE67E22)
    icon = "💻" if is_success else ("⚠️" if is_mismatch else "❌")

    embed = {
        "title": f"{icon} Client Auth: {status}",
        "description": message,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {"name": "👤 Username", "value": f"`{username}`", "inline": True},
            {"name": "🌐 IP Address", "value": f"`{ip}`", "inline": True},
            {"name": "💻 HWID", "value": f"`{hwid}`" if hwid else "*None*", "inline": False}
        ],
        "footer": {"text": "Axenor Auth Server"}
    }
    await send_webhook(embed)
