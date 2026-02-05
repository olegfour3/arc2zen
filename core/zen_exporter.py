#!/usr/bin/env python3
"""Export Zen Browser bookmarks to HTML file."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import lz4.block
except ImportError:
    print("ERROR: lz4 module required. Install with: pip install lz4")
    sys.exit(1)

from .models import Bookmark, BookmarkFolder
from .arc_exporter import HTMLExporter


def read_lz4_json(path: Path) -> dict:
    """Read mozlz4 compressed JSON file."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"mozLz40\0":
        raise ValueError(f"Invalid mozlz4 format: {path}")
    return json.loads(lz4.block.decompress(data[8:]))


def find_zen_profile() -> Optional[Path]:
    """Find default Zen Browser profile."""
    if sys.platform == "darwin":
        zen_root = Path.home() / "Library" / "Application Support" / "zen" / "Profiles"
    elif sys.platform == "win32":
        zen_root = Path(os.environ.get("APPDATA", "")) / "zen" / "Profiles"
    else:
        zen_root = Path.home() / ".zen" / "Profiles"

    if not zen_root.exists():
        return None

    for profile_dir in zen_root.iterdir():
        if profile_dir.is_dir() and "default" in profile_dir.name.lower():
            return profile_dir

    for profile_dir in zen_root.iterdir():
        if profile_dir.is_dir():
            return profile_dir
    return None


def get_zen_data(profile_path: Path) -> dict:
    """Read Zen session data."""
    zen_path = profile_path / "zen-sessions.jsonlz4"
    if zen_path.exists():
        return read_lz4_json(zen_path)
    
    # Fallback to recovery file
    recovery_path = profile_path / "sessionstore-backups" / "recovery.jsonlz4"
    if recovery_path.exists():
        data = read_lz4_json(recovery_path)
        if "windows" in data and data["windows"]:
            win = data["windows"][0]
            return {
                "tabs": win.get("tabs", []),
                "folders": win.get("folders", []),
                "groups": win.get("groups", []),
                "spaces": [],
            }
    
    raise FileNotFoundError("Zen Browser session data not found")


def get_zen_workspaces(profile_path: Path) -> Dict[str, str]:
    """Get Zen workspaces as {uuid: name} mapping."""
    zen_path = profile_path / "zen-sessions.jsonlz4"
    data = read_lz4_json(zen_path)
    
    workspaces = {}
    for space in data.get("spaces", []):
        name = space.get("name", "").strip()
        ws_uuid = space.get("uuid", "")
        if name and ws_uuid:
            workspaces[ws_uuid] = name
    return workspaces


def parse_zen_bookmarks(profile_path: Path) -> List[BookmarkFolder]:
    """
    Parse Zen Browser data and return as list of BookmarkFolder.
    Each workspace becomes a top-level folder.
    """
    data = get_zen_data(profile_path)
    workspaces = get_zen_workspaces(profile_path)
    
    tabs = data.get("tabs", [])
    folders = data.get("folders", [])
    
    # Build folder lookup: {folder_id: folder_data}
    folder_lookup = {f["id"]: f for f in folders if isinstance(f, dict) and "id" in f}
    
    # Group tabs and folders by workspace
    workspace_tabs: Dict[str, List[dict]] = {}
    workspace_folders: Dict[str, List[dict]] = {}
    
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        if not tab.get("pinned"):
            continue
        if tab.get("zenIsEmpty"):
            continue
        
        ws_id = tab.get("zenWorkspace", "default")
        if ws_id not in workspace_tabs:
            workspace_tabs[ws_id] = []
        workspace_tabs[ws_id].append(tab)
    
    for folder in folders:
        if not isinstance(folder, dict):
            continue
        ws_id = folder.get("workspaceId", "default")
        if ws_id not in workspace_folders:
            workspace_folders[ws_id] = []
        workspace_folders[ws_id].append(folder)
    
    # Build bookmark tree for each workspace
    result = []
    
    all_workspace_ids = set(workspace_tabs.keys()) | set(workspace_folders.keys())
    
    for ws_id in all_workspace_ids:
        ws_name = workspaces.get(ws_id, f"Workspace {ws_id[:8]}")
        ws_tabs = workspace_tabs.get(ws_id, [])
        ws_folders = workspace_folders.get(ws_id, [])
        
        children = build_folder_tree(ws_tabs, ws_folders, folder_lookup)
        
        if children:
            result.append(BookmarkFolder(title=ws_name, children=children))
    
    return result


def build_folder_tree(
    tabs: List[dict],
    folders: List[dict],
    folder_lookup: Dict[str, dict],
) -> List:
    """Build bookmark folder tree from tabs and folders."""
    # Build folder hierarchy
    folder_children: Dict[str, List] = {}  # folder_id -> children
    root_items = []
    
    # Initialize folder children
    for folder in folders:
        folder_id = folder["id"]
        folder_children[folder_id] = []
    
    # Assign tabs to folders or root
    for tab in tabs:
        entries = tab.get("entries", [])
        if not entries:
            continue
        
        entry = entries[-1] if entries else {}
        url = entry.get("url", "")
        title = entry.get("title", "") or tab.get("_zenPinnedInitialState", {}).get("entry", {}).get("title", "")
        
        if not url or url == "about:blank":
            continue
        
        bookmark = Bookmark(title=title or url, url=url)
        
        group_id = tab.get("groupId")
        if group_id and group_id in folder_children:
            folder_children[group_id].append(bookmark)
        else:
            root_items.append(bookmark)
    
    # Build nested folder structure
    def build_folder(folder_data: dict) -> Optional[BookmarkFolder]:
        folder_id = folder_data["id"]
        name = folder_data.get("name", "Unnamed")
        children = folder_children.get(folder_id, [])
        
        # Find child folders
        for f in folders:
            if f.get("parentId") == folder_id:
                child_folder = build_folder(f)
                if child_folder:
                    children.append(child_folder)
        
        if not children:
            return None
        
        return BookmarkFolder(title=name, children=children)
    
    # Add root-level folders
    for folder in folders:
        if folder.get("parentId") is None:
            built = build_folder(folder)
            if built:
                root_items.append(built)
    
    return root_items


def count_items(folders: List[BookmarkFolder]) -> Tuple[int, int]:
    """Count total bookmarks and folders."""
    def count_folder(folder: BookmarkFolder) -> Tuple[int, int]:
        bm, fl = 0, 1
        for item in folder.children:
            if isinstance(item, Bookmark):
                bm += 1
            elif isinstance(item, BookmarkFolder):
                sub_bm, sub_fl = count_folder(item)
                bm += sub_bm
                fl += sub_fl
        return bm, fl
    
    total_bm, total_fl = 0, 0
    for folder in folders:
        bm, fl = count_folder(folder)
        total_bm += bm
        total_fl += fl
    return total_bm, total_fl


def export_zen_to_html(output_path: Optional[Path] = None) -> Tuple[int, int]:
    """
    Export Zen Browser bookmarks to HTML file.
    
    Returns:
        Tuple of (total_bookmarks, total_folders)
    """
    # Find Zen profile
    profile_path = find_zen_profile()
    if not profile_path:
        raise FileNotFoundError("Zen Browser profile not found")
    
    print(f"Zen profile: {profile_path}")
    
    # Parse Zen data
    print("Reading Zen Browser data...")
    folders = parse_zen_bookmarks(profile_path)
    
    if not folders:
        print("No bookmarks found in Zen Browser")
        return 0, 0
    
    # Export to HTML
    print("Converting to HTML...")
    exporter = HTMLExporter(folders)
    html_content = exporter.export()
    
    # Write output
    if output_path is None:
        current_date = datetime.now().strftime("%Y_%m_%d")
        output_path = Path(f"zen_bookmarks_{current_date}.html")
    
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Saved to: {output_path}")
    
    # Count totals
    total_bookmarks, total_folders = count_items(folders)
    
    return total_bookmarks, total_folders


if __name__ == "__main__":
    try:
        bookmarks, folders = export_zen_to_html()
        print(f"\nExported {bookmarks} bookmarks in {folders} folders")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
