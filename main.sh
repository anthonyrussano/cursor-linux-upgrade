#!/usr/bin/env bash
#
# Script to upgrade the "Cursor" app when a new .AppImage is released.
# Usage: ./main.sh /path/to/cursor-latest.AppImage
#
# - Must run as a user with 'sudo' privileges (for writing /opt, etc.).
# - Moves old installation to /opt/cursor_old_TIMESTAMP.
# - Extracts new version so that /opt/cursor/AppRun is the actual launcher.
# - Maintains symlink /usr/local/bin/cursor -> /opt/cursor/AppRun.

set -e  # Exit immediately on error

# 1) Parse argument: path to the new AppImage
APPIMAGE="$1"
if [ -z "$APPIMAGE" ]; then
  echo "Usage: $0 /path/to/cursor-latest.AppImage"
  exit 1
fi

if [ ! -f "$APPIMAGE" ]; then
  echo "Error: File '$APPIMAGE' not found."
  exit 1
fi

echo "==> Using AppImage: $APPIMAGE"

# 2) Make the new AppImage executable
chmod +x "$APPIMAGE"

# 3) Prepare a temporary folder for extraction
TMP_EXTRACT="new_squashfs-root"
rm -rf "$TMP_EXTRACT"
mkdir "$TMP_EXTRACT"
cd "$TMP_EXTRACT"

echo "==> Extracting AppImage..."
"$APPIMAGE" --appimage-extract

cd ..

# At this point, we have new_squashfs-root/squashfs-root/*

# 4) Fix permissions on chrome-sandbox, if it exists
SANDBOX_PATH="$TMP_EXTRACT/squashfs-root/usr/share/cursor/chrome-sandbox"
if [ -f "$SANDBOX_PATH" ]; then
  echo "==> Setting correct ownership & permissions on chrome-sandbox..."
  sudo chown root:root "$SANDBOX_PATH"
  sudo chmod 4755 "$SANDBOX_PATH"
else
  echo "Warning: $SANDBOX_PATH not found. Sandbox might fail without --no-sandbox."
fi

# 5) Back up old version (if /opt/cursor exists)
if [ -d /opt/cursor ]; then
  BACKUP_NAME="/opt/cursor_old_$(date +%Y%m%d%H%M%S)"
  echo "==> Backing up old /opt/cursor to $BACKUP_NAME"
  sudo mv /opt/cursor "$BACKUP_NAME"
fi

# 6) Move the newly extracted 'squashfs-root' folder into /opt/cursor
#    so that /opt/cursor/AppRun is the actual launcher path
echo "==> Moving new Cursor to /opt/cursor"
sudo mv "$TMP_EXTRACT/squashfs-root" /opt/cursor

# 7) Cleanup the leftover empty folder
rm -rf "$TMP_EXTRACT"

# 8) Recreate (or verify) the symlink
echo "==> Updating symlink /usr/local/bin/cursor -> /opt/cursor/AppRun"
sudo ln -sf /opt/cursor/AppRun /usr/local/bin/cursor

echo "==> Upgrade complete!"
echo "You can now run 'cursor' to launch the new version."

# 9) Optionally update desktop database to pick up any changed .desktop files
echo "==> Updating desktop database..."
update-desktop-database ~/.local/share/applications
