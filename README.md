# Arc2Zen

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A tool for exporting bookmarks from Arc Browser and Zen Browser to HTML format, and migrating bookmarks directly from Arc to Zen Browser.

**[RU](README_RU.md)**

## Features

- **Export Arc bookmarks** to HTML (preserves order, compatible with all browsers)
- **Export Zen bookmarks** to HTML (preserves order, compatible with all browsers)
- **Direct migration** from Arc to Zen (preserves folder structure and tab order)
- **Multi-profile support** for Arc and Zen
- **macOS only**

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/arc2zen.git
cd arc2zen

# Install dependencies (only needed for Zen operations)
pip install lz4

# Run the tool
python main.py
```

## Requirements

- Python 3.7+
- `lz4` package (for Zen Browser operations)

```bash
pip install lz4
```

## Usage

Run the script and select an option from the menu:

```
============================================================
Arc Bookmarks Tool
============================================================

Choose an option:

  1. Export Arc bookmarks to HTML file
  2. Export Zen bookmarks to HTML file
  3. Migrate Arc bookmarks to Zen Browser

  0. Exit
```

### Option 1: Export Arc Bookmarks

Exports all pinned bookmarks from Arc Browser to a standard HTML file.

- Auto-generated filename with date or custom name

### Option 2: Export Zen Bookmarks

Exports all pinned tabs from Zen Browser to HTML format.

- Preserves workspace structure as folders
- Preserves folder hierarchy

### Option 3: Migrate Arc to Zen

Directly imports Arc bookmarks into Zen Browser.

**Important:**
- Zen Browser must be **closed** before migration
- The script automatically checks if Zen is running
- Creates backups before making changes
- Requires matching workspaces in Zen (will prompt to create missing ones)

## File Locations

### Arc Browser Data

`~/Library/Application Support/Arc/StorableSidebar.json`

### Zen Browser Data

`~/Library/Application Support/zen/Profiles/`

## Migrating Passwords (Manual)

This tool does not migrate passwords (different security systems). Follow these steps manually:

### Export from macOS (Arc uses iCloud Keychain)
1. Open **Passwords** app (macOS Sequoia+) or **Keychain Access**
2. **Passwords app:** File → Export All Passwords → Save as CSV
3. **Keychain Access:** File → Export Items

### Import to Zen
1. Open Zen Browser
2. Go to `about:logins`
3. Click **⋯** (menu) → **Import from a File...**
4. Select the CSV file

> **Security:** Delete the CSV file after import — it contains plain text passwords.

## Importing HTML to Browsers

### Chrome / Chromium
1. Go to `chrome://bookmarks/`
2. Click ⋮ → "Import bookmarks"
3. Select the HTML file

### Firefox
1. Press `Ctrl+Shift+B` (Bookmarks Manager)
2. "Import and Backup" → "Import Bookmarks from HTML"

### Safari
1. File → "Import From" → "Bookmarks HTML File"

### Edge
1. Click ⋯ → "Favorites" → "Manage favorites"
2. Click ⋯ → "Import favorites" → "Bookmarks HTML file"

## Project Structure

```
arc2zen/
├── main.py              # Main entry point
├── core/
│   ├── __init__.py
│   ├── models.py        # Data classes
│   ├── arc_exporter.py  # Arc Browser operations
│   ├── zen_exporter.py  # Zen export to HTML
│   └── zen_importer.py  # Arc to Zen migration
├── README.md
├── README_RU.md
└── LICENSE
```

## Troubleshooting

### "File not found" for Arc
- Ensure Arc Browser is installed and has been run at least once

### "Zen Browser profile not found"
- Ensure Zen Browser is installed and has been run at least once

### "lz4 module required"
```bash
pip install lz4
```

### Missing bookmarks after migration
- Only **pinned** tabs are migrated
- Unpinned tabs are not included

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Support

If you find this project helpful, please give it a ⭐ star!

## License

This project is licensed under the [MIT License](LICENSE).
