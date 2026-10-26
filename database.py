import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from config import DB_PATH, MAIN_OWNER_ID

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for Bot Owners / Sub-Owners
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS owners (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for Global Settings (e.g. Webhook URL)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Table for Resellers and their assigned channels
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER UNIQUE NOT NULL,
            added_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for Auth Keys / Users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password TEXT NOT NULL,
            days INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            hwid TEXT DEFAULT NULL,
            created_by INTEGER NOT NULL,
            channel_id INTEGER,
            last_login TIMESTAMP DEFAULT NULL
        )
    """)

    conn.commit()
    conn.close()

# ----------------- Owner Functions -----------------

def add_owner(user_id: int, added_by: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO owners (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_owner(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM owners WHERE user_id = ?", (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_all_owners() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM owners ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def is_owner(user_id: int) -> bool:
    """Returns True if user is Main Owner (from config) or added in owners table."""
    if user_id == MAIN_OWNER_ID:
        return True
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM owners WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# ----------------- Settings Functions -----------------

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

# ----------------- Reseller Functions -----------------

def add_reseller(user_id: int, channel_id: int, added_by: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO resellers (user_id, channel_id, added_by) VALUES (?, ?, ?)",
            (user_id, channel_id, added_by)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_reseller_by_channel(channel_id: int) -> Optional[int]:
    """Removes reseller associated with channel_id, returns user_id if deleted."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM resellers WHERE channel_id = ?", (channel_id,))
    row = cursor.fetchone()
    if row:
        user_id = row["user_id"]
        cursor.execute("DELETE FROM resellers WHERE channel_id = ?", (channel_id,))
        conn.commit()
        conn.close()
        return user_id
    conn.close()
    return None

def remove_reseller_by_user(user_id: int) -> List[int]:
    """Removes all channels for a reseller, returns list of channel_ids deleted."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM resellers WHERE user_id = ?", (user_id,))
    channels = [row["channel_id"] for row in cursor.fetchall()]
    if channels:
        cursor.execute("DELETE FROM resellers WHERE user_id = ?", (user_id,))
        conn.commit()
    conn.close()
    return channels

def is_reseller_channel(channel_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM resellers WHERE channel_id = ?", (channel_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_reseller_by_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resellers WHERE channel_id = ?", (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_resellers() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resellers ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ----------------- User / Key Functions -----------------

def create_key(username: str, password: str, days: int, created_by: int, channel_id: int) -> Dict[str, Any]:
    username = username.strip()
    password = password.strip()
    
    if days <= 0:
        return {"success": False, "message": "Days must be greater than 0."}
    
    now = datetime.utcnow()
    expires_at = now + timedelta(days=days)
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password, days, expires_at, created_by, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, password, days, expires_at.strftime("%Y-%m-%d %H:%M:%S"), created_by, channel_id))
        conn.commit()
        return {
            "success": True,
            "username": username,
            "password": password,
            "days": days,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"User/Key '{username}' already exists!"}
    finally:
        conn.close()

def delete_key(username: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username.strip(),))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def reset_hwid(username: str) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hwid FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "message": f"User '{username}' does not exist!"}
    
    old_hwid = row["hwid"]
    cursor.execute("UPDATE users SET hwid = NULL WHERE username = ?", (username.strip(),))
    conn.commit()
    conn.close()
    return {"success": True, "old_hwid": old_hwid}

def get_key_info(username: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    
    data = dict(row)
    now = datetime.utcnow()
    expires_at = datetime.strptime(data["expires_at"], "%Y-%m-%d %H:%M:%S")
    remaining = expires_at - now
    
    data["is_expired"] = remaining.total_seconds() <= 0
    data["remaining_seconds"] = max(0, int(remaining.total_seconds()))
    data["remaining_days"] = max(0, remaining.days)
    data["remaining_hours"] = max(0, int(remaining.seconds // 3600))
    return data

# ----------------- Auth API Verification -----------------

def authenticate_client(username: str, password: str, hwid: str) -> Dict[str, Any]:
    """
    Validates user credentials and auto-binds HWID on first login.
    """
    username = (username or "").strip()
    password = (password or "").strip()
    hwid = (hwid or "").strip()

    if not username or not password:
        return {"success": False, "status": "INVALID_INPUT", "message": "Username and password are required."}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "status": "USER_NOT_FOUND", "message": "Invalid username or password."}

    user = dict(row)

    # Password check
    if user["password"] != password:
        conn.close()
        return {"success": False, "status": "WRONG_PASSWORD", "message": "Invalid username or password."}

    # Expiration check
    now = datetime.utcnow()
    expires_at = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
    if now > expires_at:
        conn.close()
        return {
            "success": False,
            "status": "EXPIRED",
            "message": f"Subscription expired on {user['expires_at']} UTC.",
            "expires_at": user["expires_at"]
        }

    # HWID check and Auto-binding
    bound_hwid = user["hwid"]
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if not bound_hwid:
        # First login! Auto bind HWID
        if not hwid:
            conn.close()
            return {"success": False, "status": "HWID_REQUIRED", "message": "HWID cannot be empty for initial binding."}
        
        cursor.execute("UPDATE users SET hwid = ?, last_login = ? WHERE username = ?", (hwid, now_str, username))
        conn.commit()
        conn.close()
        remaining = expires_at - now
        return {
            "success": True,
            "status": "HWID_BOUND_SUCCESS",
            "message": "Login successful. HWID auto-bound to this device.",
            "username": username,
            "expires_at": user["expires_at"],
            "days_left": remaining.days,
            "hwid": hwid
        }

    # HWID already bound
    if bound_hwid != hwid:
        conn.close()
        return {
            "success": False,
            "status": "HWID_MISMATCH",
            "message": "HWID mismatch! Please contact your reseller to reset your HWID.",
            "bound_hwid": bound_hwid,
            "attempted_hwid": hwid
        }

    # HWID matches, regular login
    cursor.execute("UPDATE users SET last_login = ? WHERE username = ?", (now_str, username))
    conn.commit()
    conn.close()
    remaining = expires_at - now
    return {
        "success": True,
        "status": "SUCCESS",
        "message": "Login successful.",
        "username": username,
        "expires_at": user["expires_at"],
        "days_left": remaining.days,
        "hwid": hwid
    }
