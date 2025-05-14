#!/usr/bin/env python3
import requests
import re
import sys

API_ENDPOINT = "https://www.cursor.com/api/download"
PLATFORM = "linux-x64"

def fetch_latest_download_url(platform: str) -> str:
    """
    Call Cursor's download API and return the downloadUrl for a given platform.
    Raises an exception if the request fails or the response is malformed.
    """
    resp = requests.get(
        API_ENDPOINT,
        params={"platform": platform, "releaseTrack": "latest"},
        headers={
            "User-Agent": "Cursor-Version-Checker",
            "Cache-Control": "no-cache",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "downloadUrl" not in data:
        raise KeyError(f"No downloadUrl in response: {data}")
    return data["downloadUrl"]

def extract_version(url: str) -> str:
    """
    Pull the first semver-like pattern (e.g. 1.2.3) out of the URL.
    Returns 'Unknown' if none is found.
    """
    m = re.search(r"\b(\d+\.\d+\.\d+)\b", url)
    return m.group(1) if m else "Unknown"

def main():
    try:
        download_url = fetch_latest_download_url(PLATFORM)
        version = extract_version(download_url)
        print(f"Latest Cursor version for {PLATFORM}: {version}")
        print(f"Download URL: {download_url}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
