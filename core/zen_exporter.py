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
from .arc_exporter import HTMLExporter, sanitize_filename, _get_base_and_ext


def read_lz4_json(path: Path) -> dict:
    """Read mozlz4 compressed JSON file."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"mozLz40\0":
        raise ValueError(f"Invalid mozlz4 format: {path}")
    return json.loads(lz4.block.decompress(data[8:]))


def find_zen_profile() -> Optional[Path]:
    """Find default Zen Browser profile (macOS only)."""
    zen_root = Path.home() / "Library" / "Application Support" / "zen" / "Profiles"

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


def _tab_to_bookmark(tab: dict) -> Optional[Bookmark]:
    """Convert a Zen tab dict to Bookmark. Returns None if invalid."""
    entries = tab.get("entries", [])
    if not entries:
        return None
    entry = entries[-1]
    url = entry.get("url", "")
    title = (
        entry.get("title", "")
        or tab.get("_zenPinnedInitialState", {}).get("entry", {}).get("title", "")
    )
    if not url or url == "about:blank":
        return None
    return Bookmark(title=title or url, url=url)


def _collect_essentials_by_workspace(
    tabs: List[dict],
    spaces: List[dict],
) -> Dict[str, List[Bookmark]]:
    """
    Collect essentials grouped by workspace uuid.
    
    Essentials with zenWorkspace set go to that workspace.
    Essentials with zenWorkspace=None are matched to workspaces
    by userContextId == containerTabId (profile-based binding).
    
    Returns {ws_uuid: [bookmarks]}.
    """
    # Build containerTabId -> [ws_uuid] mapping
    container_to_ws: Dict[int, List[str]] = {}
    for s in spaces:
        ct_id = s.get("containerTabId", 0)
        ws_uuid = s.get("uuid", "")
        if ws_uuid:
            container_to_ws.setdefault(ct_id, []).append(ws_uuid)
    
    ws_ess: Dict[str, List[Bookmark]] = {}
    
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        if not tab.get("pinned") or not tab.get("zenEssential"):
            continue
        if tab.get("zenIsEmpty"):
            continue
        
        bm = _tab_to_bookmark(tab)
        if not bm:
            continue
        
        ws_id = tab.get("zenWorkspace")
        if ws_id:
            ws_ess.setdefault(ws_id, []).append(bm)
        else:
            # Match by userContextId -> containerTabId
            ctx_id = tab.get("userContextId", 0)
            target_ws_ids = container_to_ws.get(ctx_id, [])
            for target_ws in target_ws_ids:
                ws_ess.setdefault(target_ws, []).append(bm)
    
    return ws_ess


def parse_zen_bookmarks(profile_path: Path) -> List[BookmarkFolder]:
    """
    Parse Zen Browser data and return as list of BookmarkFolder.
    Each workspace becomes a top-level folder with its essentials inside.
    """
    data = get_zen_data(profile_path)
    workspaces = get_zen_workspaces(profile_path)
    
    tabs = data.get("tabs", [])
    folders = data.get("folders", [])
    spaces_data = data.get("spaces", [])
    
    folder_lookup = {f["id"]: f for f in folders if isinstance(f, dict) and "id" in f}
    
    # Collect essentials matched to workspaces by profile
    ws_essentials = _collect_essentials_by_workspace(tabs, spaces_data)
    
    # Group non-essential tabs and folders by workspace
    workspace_tabs: Dict[str, List[dict]] = {}
    workspace_folders: Dict[str, List[dict]] = {}
    
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        if not tab.get("pinned"):
            continue
        if tab.get("zenIsEmpty"):
            continue
        if tab.get("zenEssential"):
            continue
        
        ws_id = tab.get("zenWorkspace") or "default"
        workspace_tabs.setdefault(ws_id, []).append(tab)
    
    for folder in folders:
        if not isinstance(folder, dict):
            continue
        ws_id = folder.get("workspaceId") or "default"
        workspace_folders.setdefault(ws_id, []).append(folder)
    
    result = []
    
    all_workspace_ids = set(workspace_tabs.keys()) | set(workspace_folders.keys())
    all_workspace_ids |= set(ws_essentials.keys())
    
    for ws_id in all_workspace_ids:
        ws_name = workspaces.get(ws_id, f"Workspace {(ws_id or 'unknown')[:8]}")
        ws_tabs = workspace_tabs.get(ws_id, [])
        ws_folders = workspace_folders.get(ws_id, [])
        
        children = build_folder_tree(ws_tabs, ws_folders, folder_lookup)
        
        ess_items = ws_essentials.get(ws_id, [])
        if ess_items:
            ess_folder = BookmarkFolder(title="Essentials", children=ess_items)
            children.insert(0, ess_folder)
        
        if children:
            result.append(BookmarkFolder(title=ws_name, children=children))
    
    return result


def sort_folders_by_sibling_order(folders: List[dict], parent_id: Optional[str] = None) -> List[dict]:
    """Sort folders by prevSiblingInfo linked list order."""
    # Filter folders by parent
    siblings = [f for f in folders if f.get("parentId") == parent_id]
    if not siblings:
        return []
    
    # Build map: prev_id -> folder
    by_prev: Dict[Optional[str], dict] = {}
    for f in siblings:
        prev_info = f.get("prevSiblingInfo") or {}
        prev_id = prev_info.get("id") if prev_info.get("type") == "folder" else None
        by_prev[prev_id] = f
    
    # Build ordered list starting from None (first element)
    ordered = []
    current_prev = None
    while current_prev in by_prev:
        folder = by_prev[current_prev]
        ordered.append(folder)
        current_prev = folder["id"]
    
    # Add any remaining folders that weren't in the chain
    ordered_ids = {f["id"] for f in ordered}
    for f in siblings:
        if f["id"] not in ordered_ids:
            ordered.append(f)
    
    return ordered


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
        
        # Find child folders in correct order
        child_folders = sort_folders_by_sibling_order(folders, folder_id)
        for f in child_folders:
            child_folder = build_folder(f)
            if child_folder:
                children.append(child_folder)
        
        if not children:
            return None
        
        return BookmarkFolder(title=name, children=children)
    
    # Add root-level folders in correct order
    root_folders = sort_folders_by_sibling_order(folders, None)
    for folder in root_folders:
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


def export_zen_to_html(
    output_path: Optional[Path] = None,
    split_by_space: bool = False,
) -> Tuple[int, int]:
    """
    Export Zen Browser bookmarks to HTML file(s).
    
    Args:
        split_by_space: If True, export each workspace into a separate file.
    
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
    
    print("Converting to HTML...")
    
    if split_by_space and len(folders) > 1:
        base, ext = _get_base_and_ext(output_path, "zen_bookmarks")
        total_bookmarks = 0
        total_folders = 0
        
        for folder in folders:
            safe_name = sanitize_filename(folder.title)
            file_path = Path(f"{base}_{safe_name}{ext}")
            
            exporter = HTMLExporter([folder])
            html_content = exporter.export()
            
            with file_path.open("w", encoding="utf-8") as f:
                f.write(html_content)
            
            bm, fl = count_items([folder])
            total_bookmarks += bm
            total_folders += fl
            print(f"  {file_path.name}: {bm} bookmarks")
        
        return total_bookmarks, total_folders
    
    # Single file export
    exporter = HTMLExporter(folders)
    html_content = exporter.export()
    
    if output_path is None:
        current_date = datetime.now().strftime("%Y_%m_%d")
        output_path = Path(f"zen_bookmarks_{current_date}.html")
    
    with output_path.open("w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Saved to: {output_path}")
    
    total_bookmarks, total_folders = count_items(folders)
    
    return total_bookmarks, total_folders


if __name__ == "__main__":
    try:
        bookmarks, folders = export_zen_to_html()
        print(f"\nExported {bookmarks} bookmarks in {folders} folders")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
