import re
import requests
import sys
from pathlib import Path

# Load rogkit settings
from ..settings import root_dir
from ..bin.tomlr import load_rogkit_toml

def extract_token_from_root():
    config = load_rogkit_toml()
    server_url = config.get("plex", {}).get("plex_server_url", "127.0.0.1")
    port = config.get("plex", {}).get("plex_server_port", 32400)
    expected_token = config.get("plex", {}).get("plex_server_token")

    url = f"http://{server_url}:{port}/"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            print(f"❌ HTTP error: {response.status_code}")
            sys.exit(1)

        # Try to extract token from XML body
        match = re.search(r'authenticationToken="([^"]+)"', response.text)
        if match:
            live_token = match.group(1)
            print(f"🔑 Extracted token from Plex: {live_token}")
            if expected_token:
                if live_token == expected_token:
                    print("✅ Token matches rogkit.toml")
                else:
                    print("⚠️  Token differs from rogkit.toml!")
            else:
                print("⚠️  No token in rogkit.toml to compare against")
        else:
            print("❌ Could not find authenticationToken in response")

    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    extract_token_from_root()