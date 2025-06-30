# Cursor Updater for Linux

A utility script to update the Cursor IDE on Linux systems.

This script fetches the latest version, handles installation, and provides various options for customization.

## Requirements

- Python 3.12 or higher.
- `requests` package
- `packaging` package
- `sudo` privileges (for installation)

## Usage

Basic usage:
```bash
./update-cursor.py
```

Check for updates without installing:
```bash
./update-cursor.py --check
```

Force update even if the current version is the latest:
```bash
./update-cursor.py --force
```

Skip backing up the existing installation:
```bash
./update-cursor.py --no-backup
```

Enable verbose logging:
```bash
./update-cursor.py --verbose
```

## How It Works

1. The script checks for the currently installed Cursor version
2. It contacts the Cursor API to determine the latest available version
3. If an update is needed, it:
   - Backs up the existing installation (unless `--no-backup` is specified)
   - Downloads the latest AppImage with a progress indicator
   - Extracts the AppImage and fixes permissions
   - Installs to `/opt/cursor/`
   - Creates symlinks and updates the desktop database
   - Cleans up temporary files

## Log File

Logs are stored in `~/.cursor_updater.log` for debugging purposes.

## Troubleshooting

If you encounter issues:
1. Check the log file: `cat ~/.cursor_updater.log`
2. Try running with the `--verbose` flag for more detailed output
3. Make sure you have sudo privileges
4. Verify internet connectivity

## Common Issues

### "chrome-sandbox not found" warning
This is normal for some Cursor versions. You may need to run Cursor with the `--no-sandbox` flag.

### Sudo password prompts
The script requires sudo privileges to install to `/opt/cursor/`. Make sure you have sudo access.

### API connection issues
If you can't connect to the Cursor API, check your internet connection and proxy settings.

## License

This script is provided under the MIT License. Feel free to modify and distribute as needed.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.