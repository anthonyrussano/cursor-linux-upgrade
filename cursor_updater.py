#!/usr/bin/env python3
import argparse
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import requests
from packaging import version

# Configuration
API_ENDPOINT = "https://www.cursor.com/api/download"
PLATFORM = "linux-x64"
DESKTOP_IN = Path("/opt/cursor/cursor.desktop")
SYMLINK = Path("/usr/local/bin/cursor")
INSTALL_DIR = Path("/opt/cursor")
BACKUP_DIR = Path("/opt/cursor_backups")
LOG_FILE = Path.home() / ".cursor_updater.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE)
    ]
)
logger = logging.getLogger("cursor_updater")


def get_installed_version(desktop_path: Path) -> Optional[str]:
    """Read the installed version from the cursor.desktop file."""
    if not desktop_path.is_file():
        return None
    try:
        for line in desktop_path.read_text().splitlines():
            if line.startswith("X-AppImage-Version="):
                return line.split("=", 1)[1].strip()
    except (IOError, PermissionError) as e:
        logger.warning(f"Could not read desktop file: {e}")
    return None


def fetch_latest_info(platform: str) -> Tuple[str, str]:
    """
    Call Cursor's download API and return the downloadUrl and version for a given platform.
    """
    try:
        resp = requests.get(
            API_ENDPOINT,
            params={"platform": platform, "releaseTrack": "latest"},
            headers={"User-Agent": "Cursor-Version-Checker", "Cache-Control": "no-cache"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if "downloadUrl" not in data:
            raise KeyError("downloadUrl missing from API response")
        
        download_url = data["downloadUrl"]
        version_str = extract_version(download_url)
        
        return download_url, version_str
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        raise
    except (ValueError, KeyError) as e:
        logger.error(f"API response error: {e}")
        raise


def extract_version(url: str) -> str:
    """Extract a semver-like pattern from the URL."""
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", url)
    return match.group(1) if match else "Unknown"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Helper to run subprocess commands with logging."""
    cmd_str = " ".join(cmd)
    logger.info(f"Running: {cmd_str}")
    
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {cmd_str}")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise


def check_dependencies() -> bool:
    """Check if required system dependencies are installed."""
    dependencies = ["sudo", "update-desktop-database"]
    missing = []
    
    for dep in dependencies:
        try:
            subprocess.run(["which", dep], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            missing.append(dep)
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        return False
    return True


def backup_existing_install(source_dir: Path, backup_dir: Path) -> bool:
    """Create a backup of the existing installation."""
    if not source_dir.exists():
        logger.info("No existing installation to backup")
        return True
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"cursor_{timestamp}"
        
        # Create backup directory with sudo if it doesn't exist
        if not backup_dir.exists():
            logger.info(f"Creating backup directory: {backup_dir}")
            run(["sudo", "mkdir", "-p", str(backup_dir)])
        
        # Create the backup
        logger.info(f"Backing up {source_dir} to {dest}")
        run(["sudo", "cp", "-R", str(source_dir), str(dest)])
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False


def download_appimage(url: str) -> Optional[Path]:
    """Download the AppImage with a progress bar."""
    try:
        logger.info(f"Downloading from {url}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".AppImage") as tmp_file:
            resp = requests.get(url, stream=True)
            resp.raise_for_status()
            
            # Get file size if available
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    tmp_file.write(chunk)
                    downloaded += len(chunk)
                    
                    # Print progress
                    if total_size > 0:
                        percent = downloaded * 100 // total_size
                        sys.stdout.write(f"\rDownload progress: {percent}% [{downloaded} / {total_size} bytes]")
                        sys.stdout.flush()
            
            if total_size > 0:
                sys.stdout.write("\n")
            
            appimage_path = Path(tmp_file.name)
        
        # Make executable
        appimage_path.chmod(appimage_path.stat().st_mode | stat.S_IXUSR)
        return appimage_path
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None


def extract_and_install(appimage_path: Path, install_dir: Path) -> bool:
    """Extract the AppImage and install it."""
    try:
        with tempfile.TemporaryDirectory(prefix="cursor_extract_") as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Extract AppImage
            logger.info("Extracting AppImage...")
            run([str(appimage_path), "--appimage-extract"], cwd=tmpdir_path)
            extracted_dir = tmpdir_path / "squashfs-root"
            
            if not extracted_dir.exists():
                logger.error("Extraction failed - squashfs-root not found")
                return False
            
            # Fix chrome-sandbox permissions, if present
            sandbox = extracted_dir / "usr/share/cursor/chrome-sandbox"
            if sandbox.exists():
                logger.info("Setting chrome-sandbox permissions")
                run(["sudo", "chown", "root:root", str(sandbox)])
                run(["sudo", "chmod", "4755", str(sandbox)])
            else:
                logger.warning("chrome-sandbox not found; may need --no-sandbox")
            
            # Remove old install (if exists)
            if install_dir.exists():
                logger.info(f"Removing old installation at {install_dir}")
                run(["sudo", "rm", "-rf", str(install_dir)])
            
            # Move new version into place
            logger.info(f"Installing to {install_dir}")
            run(["sudo", "mv", str(extracted_dir), str(install_dir)])
            
            return True
    except Exception as e:
        logger.error(f"Installation failed: {e}")
        return False


def update_symlinks_and_db(install_dir: Path, symlink: Path) -> bool:
    """Update symlinks and desktop database."""
    try:
        # Recreate symlink
        logger.info(f"Creating symlink at {symlink}")
        if symlink.exists() or symlink.is_symlink():
            run(["sudo", "rm", "-f", str(symlink)])
        run(["sudo", "ln", "-sf", str(install_dir / "AppRun"), str(symlink)])
        
        # Update desktop database
        desktop_dir = Path.home() / ".local/share/applications"
        if desktop_dir.exists():
            logger.info("Updating desktop database")
            run(["update-desktop-database", str(desktop_dir)])
        
        return True
    except Exception as e:
        logger.error(f"Failed to update symlinks/desktop DB: {e}")
        return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Update Cursor editor on Linux")
    parser.add_argument("--force", action="store_true", help="Force update even if already up to date")
    parser.add_argument("--no-backup", action="store_true", help="Skip backing up existing installation")
    parser.add_argument("--check", action="store_true", help="Only check for updates, don't install")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def main():
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("Cursor Updater starting")
    
    # Check system dependencies
    if not check_dependencies():
        sys.exit("Missing required system dependencies")
    
    # Check if we have sudo access
    try:
        run(["sudo", "-v"])
    except subprocess.CalledProcessError:
        sys.exit("This script requires sudo privileges")
    
    # 1) Check installed version
    installed_version = get_installed_version(DESKTOP_IN)
    logger.info(f"Installed version: {installed_version or 'none'}")
    
    # 2) Fetch latest version info
    try:
        download_url, latest_version = fetch_latest_info(PLATFORM)
        logger.info(f"Latest available version: {latest_version}")
    except Exception as e:
        sys.exit(f"Failed to fetch latest version info: {e}")
    
    # 3) Compare versions
    if installed_version and latest_version != "Unknown":
        try:
            if version.parse(installed_version) >= version.parse(latest_version) and not args.force:
                logger.info("✓ Already up to date.")
                return
        except version.InvalidVersion:
            logger.warning("Could not compare versions semantically, falling back to string comparison")
            if installed_version == latest_version and not args.force:
                logger.info("✓ Already up to date.")
                return
    
    if args.check:
        if not installed_version:
            print(f"Cursor not installed. Latest version available: {latest_version}")
        elif latest_version == "Unknown":
            print(f"Currently installed: {installed_version}. Cannot determine latest version.")
        else:
            print(f"Update available: {installed_version} → {latest_version}")
        return
    
    # 4) Backup existing installation
    if not args.no_backup and INSTALL_DIR.exists():
        if not backup_existing_install(INSTALL_DIR, BACKUP_DIR):
            if input("Backup failed. Continue anyway? (y/N): ").lower() != 'y':
                sys.exit("Update aborted")
    
    # 5) Download new AppImage
    appimage_path = download_appimage(download_url)
    if not appimage_path:
        sys.exit("Download failed")
    
    # 6) Extract & install
    if not extract_and_install(appimage_path, INSTALL_DIR):
        sys.exit("Installation failed")
    
    # 7) Update symlinks and desktop database
    if not update_symlinks_and_db(INSTALL_DIR, SYMLINK):
        logger.warning("Failed to update symlinks or desktop database")
    
    # 8) Cleanup
    try:
        logger.info("Cleaning up temporary files")
        appimage_path.unlink()
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")
    
    logger.info(f"✓ Successfully upgraded to {latest_version}")
    print(f"\n✓ Cursor has been upgraded to version {latest_version}")
    print("  Run `cursor` to launch")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Update cancelled by user")
        print("\nUpdate cancelled")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unhandled exception")
        print(f"\nError: {e}")
        print(f"See log for details: {LOG_FILE}")
        sys.exit(1)