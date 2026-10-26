"""
Axenor Auth Client Example
Demonstrates how client applications (Loaders, Tools, Software) authenticate
against the Bot's Auth API with automatic HWID hardware binding on first login.
"""

import sys
import subprocess
import hashlib
import requests
import json

# Replace with your Bot's API server IP/Domain & Port (e.g. http://127.0.0.1:5000)
AUTH_SERVER_URL = "http://127.0.0.1:5000"

def get_hwid() -> str:
    """
    Generates a secure, deterministic Hardware ID (HWID) based on the machine's UUID.
    Works natively on Windows without third-party drivers.
    """
    try:
        # Fetch MachineGuid from Windows Registry
        output = subprocess.check_output(
            'reg query "HKLM\\SOFTWARE\\Microsoft\\Cryptography" /v MachineGuid',
            shell=True
        ).decode().strip()
        guid = output.split()[-1]
        
        # Hash to normalize into a standardized 32-character HWID
        hwid_hash = hashlib.sha256(guid.encode('utf-8')).hexdigest().upper()
        return f"HWID-{hwid_hash[:16]}-{hwid_hash[16:32]}"
    except Exception:
        # Fallback for non-Windows or fallback environments
        import uuid
        raw = f"{uuid.getnode()}"
        return f"HWID-{hashlib.sha256(raw.encode()).hexdigest()[:24].upper()}"

def login(username: str, password: str, hwid: str = None) -> dict:
    if hwid is None:
        hwid = get_hwid()

    endpoint = f"{AUTH_SERVER_URL}/api/login"
    payload = {
        "username": username,
        "password": password,
        "hwid": hwid
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=5)
        return response.json()
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status": "SERVER_OFFLINE",
            "message": f"Could not connect to Auth server at {AUTH_SERVER_URL}. Is the bot running?"
        }
    except Exception as e:
        return {"success": False, "status": "ERROR", "message": str(e)}

if __name__ == "__main__":
    print("=" * 60)
    print("           AXENOR AUTHENTICATION CLIENT LOADER           ")
    print("=" * 60)

    my_hwid = get_hwid()
    print(f"[*] Detected Local Machine HWID: {my_hwid}\n")

    user = input("[?] Enter Username: ").strip()
    pwd = input("[?] Enter Password: ").strip()

    print("\n[*] Sending authentication request...")
    result = login(user, pwd, my_hwid)

    print("\n" + "-" * 40)
    if result.get("success"):
        print("[+] AUTHENTICATION SUCCESSFUL!")
        print(f"[+] Status: {result.get('status')} - {result.get('message')}")
        print(f"[+] User: {result.get('username')}")
        print(f"[+] Expires At: {result.get('expires_at')}")
        print(f"[+] Days Remaining: {result.get('days_left')} days")
        print(f"[+] Bound HWID: {result.get('hwid')}")
        print("-" * 40)
        print("[*] Launching protected application...")
    else:
        print("[-] AUTHENTICATION FAILED!")
        print(f"[-] Status Code: {result.get('status')}")
        print(f"[-] Error: {result.get('message')}")
        print("-" * 40)
