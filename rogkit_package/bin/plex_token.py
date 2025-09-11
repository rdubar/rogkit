import os
import sys
import requests

from ..settings import root_dir
from ..bin.tomlr import load_rogkit_toml

def get_token_from_toml():
    toml = load_rogkit_toml()
    return toml.get("plex", {}).get("plex_server_token", None)

def get_token_from_plex():
    try:
        toml = load_rogkit_toml()
        server_url = toml.get("plex", {}).get("plex_server_url", "127.0.0.1")
        port = toml.get("plex", {}).get("plex_server_port", 32400)

        url = f"http://{server_url}:{port}/myplex/account"

        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error: Could not fetch token from Plex (HTTP {response.status_code})")
            return None

        import re
        match = re.search(r'authenticationToken="([^"]+)"', response.text)
        if match:
            return match.group(1)
        else:
            print("Token not found in Plex response")
            return None

    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None

def main():
    config_token = get_token_from_toml()
    plex_token = get_token_from_plex()

    if not config_token:
        print("❌ No token found in rogkit.toml")
    else:
        print(f"🔑 Token from rogkit.toml: {config_token}")

    if not plex_token:
        print("❌ Failed to retrieve live token from Plex")
    else:
        print(f"🔐 Live token from Plex:     {plex_token}")

    if config_token and plex_token:
        if config_token == plex_token:
            print("✅ Tokens match")
        else:
            print("⚠️ Tokens DO NOT match")

if __name__ == "__main__":
    main()