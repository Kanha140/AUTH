# ⚡ AXENOR AUTH & KEY GENERATION DISCORD BOT ⚡

A high-performance Discord Bot and REST Auth Server featuring **Multi-Owner System**, **Reseller Channels**, **Interactive Control Panels**, **Discord Webhook Logging**, and **Auto-Binding Hardware ID (HWID)** on first login.

---

## 📋 Features Overview

- 👑 **Dual/Multi-Owner System**:
  - **Main Owner ID:** `1378068938847424522`
  - **Guild ID:** `1564210205988753551`
  - `/owner add @user` — Main Owner can add co-owners who get full management privileges.
  - All Owners (Main Owner + Co-Owners) automatically receive channel permissions across all reseller channels.
- 📢 **Public Key Generation**:
  - Key generation in reseller channels is **NOT hidden** (`ephemeral=False`). Everyone inside the reseller channel can see the generated key, credentials, duration, and HWID status!
- 🔔 **Discord Webhook Logging**:
  - Automatic embeds sent to your Discord Webhook channel on every event:
    - 🔑 Key Generated (Username, Password, Days, Expiry, Reseller, Channel)
    - 🗑️ Key Deleted
    - 🔄 HWID Reset
    - 💼 Reseller Added & Channel Created
    - 🚫 Reseller Removed
    - 👑 Owner Added / Removed
    - 💻 Client Logins (Auto-bind, Success, HWID Mismatch attempts with IP)
  - Configure via `.env` (`WEBHOOK_URL=...`) or slash command `/set_logs_webhook`.
- 💼 **Multi-Reseller System**:
  - Add unlimited resellers (`/reseller add`).
  - Automatically creates a private, dedicated channel with permissions for the Reseller, Main Owner, and all Co-Owners.
  - Removes reseller channels when revoked (`/reseller remove`).
  - Overview of all resellers and their assigned channels (`/total_resellers` or `/reseller total`).
- 🔘 **Interactive Reseller Panel (4 Buttons)**:
  - 🟢 **Create User & Pass**: Modal popup to enter `Username`, `Password`, and `Days` (Visible in channel).
  - 🔴 **Delete User & Pass**: Modal popup to revoke and delete a user's license.
  - 🔄 **Reset HWID**: Clears the registered HWID so the user can bind to a new machine.
  - ℹ️ **Key Info**: View credentials, expiration date, time remaining, and bound HWID.
  - *Buttons are persistent (`custom_id`), remaining fully functional across bot restarts!*
- 🔒 **Strict Channel & Creation Enforcement**:
  - Key generation **ONLY** works inside channels created & registered by the bot.
- 💻 **Automatic HWID Binding on First Login**:
  - When a user logs in for the first time through your software/loader, their machine's HWID is **automatically bound** to their account.
  - Subsequent logins from the same device succeed seamlessly.
  - Logins from unauthorized devices are rejected (`HWID MISMATCH`).
  - Resellers or Owners can reset HWID anytime via panel button or `/key reset_hwid`.

---

## 🛠️ Project Structure

```
d:\AXENORBOT\
├── bot.py               # Main Discord bot & slash commands
├── panel.py             # Reseller channel interactive panel, buttons & modals
├── database.py          # SQLite database (Users, Keys, Resellers, Owners, HWID)
├── webhook_logger.py    # Discord Webhook Logging system
├── api.py               # Asynchronous REST Auth API server (aiohttp)
├── client_example.py    # Example Python client loader with Windows HWID generator
├── config.py            # Configuration settings & environment variables
├── .env                 # Bot token, Owner ID, Guild ID, Webhook URL
└── requirements.txt     # Python dependencies
```

---

## 🚀 Quick Start Guide

### 1. Requirements & Dependencies
Ensure Python 3.10+ is installed:
```bash
pip install -r requirements.txt
```

### 2. Configure Your `.env`
Edit the [`.env`](file:///d:/AXENORBOT/.env) file:
```env
DISCORD_TOKEN=YOUR_BOT_TOKEN_HERE
OWNER_ID=1378068938847424522
GUILD_ID=1564210205988753551

# Discord Webhook Logs (Optional: paste here or use /set_logs_webhook)
WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url_here

API_HOST=0.0.0.0
API_PORT=5000
```

### 3. Launch the Bot & API Server
```bash
python bot.py
```

---

## 🎮 Slash Commands Reference

### 👑 Owner Commands
| Command | Arguments | Permissions | Description |
| :--- | :--- | :--- | :--- |
| `/owner add` | `member: @User` | **Main Owner Only** | Add a co-owner with full access across all reseller channels |
| `/owner remove` | `member: @User` | **Main Owner Only** | Remove a co-owner and revoke channel permissions |
| `/owner list` | *None* | **Owners** | View Main Owner and all registered co-owners |
| `/set_logs_webhook` | `webhook_url` | **Owners** | Set/update Discord Webhook URL for logs |

### 💼 Reseller Management
| Command | Arguments | Permissions | Description |
| :--- | :--- | :--- | :--- |
| `/reseller add` | `member`, `category` *(optional)*, `channel_name` *(optional)* | **Owners** | Creates private channel for reseller inside chosen category and deploys the 4-button panel |
| `/reseller remove` | `channel` or `member` | **Owners** | Deletes reseller's channel and removes them from database |
| `/reseller total` / `/total_resellers` | *None* | **Owners** | Lists all registered resellers, user mentions, and channel links |

### 🔑 Key Management
| Command | Arguments | Permissions | Description |
| :--- | :--- | :--- | :--- |
| `/key generate` / `/key_generate` | `username`, `password`, `days` | **Reseller / Owners** | **Only works in reseller channels!** Public message (`ephemeral=False`) |
| `/key delete` / `/key_delete` | `username` | **Reseller / Owners** | Permanently deletes a user/key |
| `/key reset_hwid` | `username` | **Reseller / Owners** | Clears HWID so the next machine auto-binds |
| `/key info` | `username` | **Reseller / Owners** | Inspects credentials, expiration, and HWID binding |
