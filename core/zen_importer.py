#!/usr/bin/env python3
"""
Import Arc Browser bookmarks directly to Zen Browser.
Reads Arc data directly (no HTML file needed).

Zen Browser must be CLOSED before running this script!
"""

import json
import os
import random
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    import lz4.block
except ImportError:
    print("ERROR: lz4 module required. Install with: pip install lz4")
    sys.exit(1)

from .models import Bookmark, BookmarkFolder, ArcSpace
from .arc_exporter import ArcDataReader, ArcDataParser


# ============== LZ4 File Operations ==============

def read_lz4_json(path: Path) -> dict:
    """Read mozlz4 compressed JSON file."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"mozLz40\0":
        raise ValueError(f"Invalid mozlz4 format: {path}")
    return json.loads(lz4.block.decompress(data[8:]))


def write_lz4_json(path: Path, data: dict):
    """Write mozlz4 compressed JSON file."""
    compressed = lz4.block.compress(json.dumps(data).encode("utf-8"))
    with open(path, "wb") as f:
        f.write(b"mozLz40\0")
        f.write(compressed)


# ============== Zen Profile ==============

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


# ============== ID Generation ==============

def generate_id() -> str:
    """Generate unique ID in Zen format: timestamp-random."""
    ts = int(datetime.now().timestamp() * 1000)
    rand = random.randint(0, 99)
    return f"{ts}-{rand}"


# ============== Tab/Folder Creation ==============

def create_empty_tab(workspace_id: str, group_id: str) -> Tuple[dict, str]:
    """Create an empty placeholder tab for a folder."""
    sync_id = generate_id()
    now = int(datetime.now().timestamp() * 1000)
    
    tab = {
        "entries": [{"url": "about:blank", "title": ""}],
        "lastAccessed": now,
        "pinned": True,
        "hidden": False,
        "groupId": group_id,
        "zenWorkspace": workspace_id,
        "zenSyncId": sync_id,
        "zenEssential": False,
        "zenDefaultUserContextId": None,
        "zenPinnedIcon": None,
        "zenIsEmpty": True,
        "zenHasStaticIcon": False,
        "zenGlanceId": None,
        "zenIsGlance": False,
        "searchMode": None,
        "userContextId": 0,
        "attributes": {},
        "index": 1,
        "userTypedValue": "",
        "userTypedClear": 0,
        "image": None,
    }
    return tab, sync_id


def create_tab(url: str, title: str, workspace_id: str, group_id: Optional[str] = None) -> dict:
    """Create a pinned tab entry (works for both folder tabs and standalone)."""
    now = int(datetime.now().timestamp() * 1000)
    
    entry = {
        "url": url,
        "title": title,
        "cacheKey": 0,
        "ID": abs(hash(url)) % 1000000000,
        "docshellUUID": "{" + str(uuid.uuid4()) + "}",
        "resultPrincipalURI": None,
        "hasUserInteraction": False,
        "triggeringPrincipal_base64": '{"3":{}}',
        "docIdentifier": abs(hash(url)) % 1000,
        "transient": False,
        "navigationKey": "{" + str(uuid.uuid4()) + "}",
        "navigationId": "{" + str(uuid.uuid4()) + "}",
    }
    
    tab = {
        "entries": [entry],
        "lastAccessed": now,
        "pinned": True,
        "hidden": False,
        "zenWorkspace": workspace_id,
        "zenSyncId": generate_id(),
        "zenEssential": False,
        "zenDefaultUserContextId": None,
        "zenPinnedIcon": None,
        "zenIsEmpty": False,
        "zenHasStaticIcon": False,
        "zenGlanceId": None,
        "zenIsGlance": False,
        "_zenPinnedInitialState": {
            "entry": {
                "url": url,
                "title": title,
                "cacheKey": 0,
                "ID": abs(hash(url)) % 1000000000,
                "triggeringPrincipal_base64": '{"3":{}}',
            },
            "image": None,
        },
        "searchMode": None,
        "userContextId": 0,
        "attributes": {},
        "index": 1,
        "userTypedValue": "",
        "userTypedClear": 0,
        "image": None,
    }
    
    if group_id:
        tab["groupId"] = group_id
    
    return tab


def create_folder_and_group(
    name: str,
    workspace_id: str,
    parent_id: Optional[str] = None,
    prev_sibling_id: Optional[str] = None,
) -> Tuple[dict, dict, str]:
    """Create folder and group entries. Returns (folder, group, folder_id)."""
    folder_id = generate_id()

    if prev_sibling_id:
        prev_sibling_info = {"type": "folder", "id": prev_sibling_id}
    else:
        prev_sibling_info = {"type": "start", "id": None}

    folder = {
        "pinned": True,
        "splitViewGroup": False,
        "id": folder_id,
        "name": name or "Unnamed",
        "collapsed": True,
        "saveOnWindowClose": True,
        "parentId": parent_id,
        "prevSiblingInfo": prev_sibling_info,
        "emptyTabIds": [],
        "userIcon": "",
        "workspaceId": workspace_id,
    }

    group = {
        "pinned": True,
        "splitView": False,
        "id": folder_id,
        "name": name or "Unnamed",
        "color": "zen-workspace-color",
        "collapsed": True,
        "saveOnWindowClose": True,
    }

    return folder, group, folder_id


# ============== Folder Processing ==============

def process_folder(
    folder: BookmarkFolder,
    workspace_id: str,
    parent_folder_id: Optional[str],
    all_folders: List[dict],
    all_groups: List[dict],
    all_tabs: List[dict],
    child_to_parent: Dict[str, str],
    prev_sibling_id: Optional[str] = None,
) -> str:
    """Recursively process a folder and its contents. Returns folder_id."""
    folder_data, group_data, folder_id = create_folder_and_group(
        folder.title, workspace_id, parent_folder_id, prev_sibling_id
    )

    # Create empty tab for folder
    empty_tab, empty_tab_id = create_empty_tab(workspace_id, folder_id)
    folder_data["emptyTabIds"] = [empty_tab_id]

    all_folders.append(folder_data)
    all_groups.append(group_data)
    all_tabs.append(empty_tab)

    if parent_folder_id:
        child_to_parent[folder_id] = parent_folder_id

    # Process children in order, tracking previous sibling for nested folders
    child_prev_sibling_id = None
    for item in folder.children:
        if isinstance(item, BookmarkFolder):
            child_prev_sibling_id = process_folder(
                item,
                workspace_id,
                folder_id,
                all_folders,
                all_groups,
                all_tabs,
                child_to_parent,
                child_prev_sibling_id,
            )
        elif isinstance(item, Bookmark):
            tab = create_tab(item.url, item.title, workspace_id, folder_id)
            all_tabs.append(tab)
    
    return folder_id


def propagate_empty_tab_ids(folders: List[dict], child_to_parent: Dict[str, str]):
    """Propagate emptyTabIds from child folders up to all parent folders."""
    folder_by_id = {f["id"]: f for f in folders}

    for folder in folders:
        current_id = folder["id"]
        empty_tab_ids = folder["emptyTabIds"].copy()

        parent_id = child_to_parent.get(current_id)
        while parent_id:
            if parent_id in folder_by_id:
                parent_folder = folder_by_id[parent_id]
                for tid in empty_tab_ids:
                    if tid not in parent_folder["emptyTabIds"]:
                        parent_folder["emptyTabIds"].append(tid)
            parent_id = child_to_parent.get(parent_id)


# ============== Arc Data Conversion ==============

def convert_arc_folders_to_spaces(folders: List[BookmarkFolder]) -> List[ArcSpace]:
    """Convert BookmarkFolder list from ArcDataParser to ArcSpace list."""
    spaces = []
    for folder in folders:
        # Each top-level folder is an Arc Space
        space = ArcSpace(name=folder.title, children=folder.children)
        spaces.append(space)
    return spaces


def get_arc_spaces() -> List[ArcSpace]:
    """Read Arc data and return as list of ArcSpace objects."""
    data = ArcDataReader.read_data()
    parser = ArcDataParser(data, include_unpinned=False)
    folders = parser.parse()
    return convert_arc_folders_to_spaces(folders)


# ============== Zen Workspaces ==============

def get_zen_workspaces(profile_path: Path) -> Dict[str, str]:
    """Get Zen workspaces as {name: uuid} mapping."""
    zen_path = profile_path / "zen-sessions.jsonlz4"
    data = read_lz4_json(zen_path)
    
    workspaces = {}
    for space in data.get("spaces", []):
        name = space.get("name", "").strip()
        ws_uuid = space.get("uuid", "")
        if name and ws_uuid:
            workspaces[name] = ws_uuid
    return workspaces


def match_spaces_to_workspaces(
    arc_spaces: List[ArcSpace],
    zen_workspaces: Dict[str, str],
) -> Dict[str, Optional[str]]:
    """
    Match Arc Spaces to Zen Workspaces.
    Returns {arc_space_name: zen_workspace_uuid or None if not found}.
    """
    mapping = {}
    
    for space in arc_spaces:
        arc_name = space.name.strip()
        
        # Try exact match first
        if arc_name in zen_workspaces:
            mapping[arc_name] = zen_workspaces[arc_name]
            continue
        
        # Try case-insensitive match
        found = False
        for zen_name, ws_uuid in zen_workspaces.items():
            if arc_name.lower() == zen_name.lower():
                mapping[arc_name] = ws_uuid
                found = True
                break
        
        if not found:
            mapping[arc_name] = None
    
    return mapping


def prompt_for_missing_workspaces(
    mapping: Dict[str, Optional[str]],
    zen_workspaces: Dict[str, str],
) -> Dict[str, str]:
    """
    Prompt user to create missing workspaces or map to existing ones.
    Returns updated mapping with all spaces resolved.
    """
    final_mapping = {}
    missing = [name for name, ws_uuid in mapping.items() if ws_uuid is None]
    
    if not missing:
        return {k: v for k, v in mapping.items() if v is not None}
    
    print("\n" + "=" * 60)
    print("MISSING WORKSPACES")
    print("=" * 60)
    print(f"\nThe following Arc Spaces have no matching Zen Workspace:")
    for name in missing:
        print(f"  - {name}")
    
    print(f"\nAvailable Zen Workspaces:")
    for i, (name, ws_uuid) in enumerate(zen_workspaces.items(), 1):
        print(f"  {i}. {name}")
    
    print("\n" + "-" * 60)
    
    for arc_name in missing:
        while True:
            print(f"\nArc Space: '{arc_name}'")
            print("Options:")
            print("  1. Create a new workspace in Zen with this name")
            print("  2. Map to an existing Zen workspace")
            print("  3. Skip this space (don't import)")
            
            choice = input("\nChoose option (1/2/3): ").strip()
            
            if choice == "1":
                print(f"\n>>> Please create workspace '{arc_name}' in Zen Browser now.")
                print("    1. Open Zen Browser")
                print("    2. Create workspace with exact name: " + arc_name)
                print("    3. Close Zen Browser")
                input("\nPress Enter when done...")
                
                # Re-read workspaces
                profile_path = find_zen_profile()
                if profile_path:
                    zen_workspaces = get_zen_workspaces(profile_path)
                    if arc_name in zen_workspaces:
                        final_mapping[arc_name] = zen_workspaces[arc_name]
                        print(f"Found workspace '{arc_name}'!")
                        break
                    else:
                        print(f"Workspace '{arc_name}' not found. Try again.")
                        
            elif choice == "2":
                print("\nAvailable workspaces:")
                ws_list = list(zen_workspaces.items())
                for i, (name, _) in enumerate(ws_list, 1):
                    print(f"  {i}. {name}")
                
                try:
                    idx = int(input("Enter number: ").strip()) - 1
                    if 0 <= idx < len(ws_list):
                        target_name, target_uuid = ws_list[idx]
                        final_mapping[arc_name] = target_uuid
                        print(f"Mapped '{arc_name}' -> '{target_name}'")
                        break
                    else:
                        print("Invalid number.")
                except ValueError:
                    print("Invalid input.")
                    
            elif choice == "3":
                print(f"Skipping '{arc_name}'")
                break
            else:
                print("Invalid choice. Enter 1, 2, or 3.")
    
    # Add already matched spaces
    for arc_name, ws_uuid in mapping.items():
        if ws_uuid is not None:
            final_mapping[arc_name] = ws_uuid
    
    return final_mapping


# ============== Clean & Import ==============

def clean_all_pinned_tabs_and_folders(profile_path: Path):
    """Remove all pinned tabs and folders from Zen session files."""
    recovery_path = profile_path / "sessionstore-backups" / "recovery.jsonlz4"
    recovery_bak_path = profile_path / "sessionstore-backups" / "recovery.baklz4"
    zen_sessions_path = profile_path / "zen-sessions.jsonlz4"
    
    print("Cleaning all pinned tabs and folders...")
    
    # Clean recovery.jsonlz4
    if recovery_path.exists():
        data = read_lz4_json(recovery_path)
        if "windows" in data and data["windows"]:
            win = data["windows"][0]
            win["tabs"] = [t for t in win.get("tabs", []) if not t.get("pinned")]
            win["folders"] = []
            win["groups"] = []
            data["session"] = {"lastUpdate": int(datetime.now().timestamp() * 1000)}
        write_lz4_json(recovery_path, data)
        print(f"  Cleaned: {recovery_path.name}")
    
    # Clean recovery.baklz4
    if recovery_bak_path.exists():
        data = read_lz4_json(recovery_bak_path)
        if "windows" in data and data["windows"]:
            win = data["windows"][0]
            win["tabs"] = [t for t in win.get("tabs", []) if not t.get("pinned")]
            win["folders"] = []
            win["groups"] = []
        write_lz4_json(recovery_bak_path, data)
        print(f"  Cleaned: {recovery_bak_path.name}")
    
    # Clean zen-sessions.jsonlz4
    if zen_sessions_path.exists():
        data = read_lz4_json(zen_sessions_path)
        data["tabs"] = [t for t in data.get("tabs", []) if not t.get("pinned")]
        data["folders"] = []
        data["groups"] = []
        data["lastCollected"] = int(datetime.now().timestamp() * 1000)
        write_lz4_json(zen_sessions_path, data)
        print(f"  Cleaned: {zen_sessions_path.name}")


def import_spaces_to_zen(
    profile_path: Path,
    arc_spaces: List[ArcSpace],
    space_to_workspace: Dict[str, str],
):
    """Import Arc Spaces into corresponding Zen Workspaces."""
    recovery_path = profile_path / "sessionstore-backups" / "recovery.jsonlz4"
    recovery_bak_path = profile_path / "sessionstore-backups" / "recovery.baklz4"
    zen_sessions_path = profile_path / "zen-sessions.jsonlz4"

    # Read current data
    recovery_data = read_lz4_json(recovery_path)
    zen_sessions_data = read_lz4_json(zen_sessions_path)

    win = recovery_data.get("windows", [{}])[0]
    existing_tabs = win.get("tabs", [])

    all_folders: List[dict] = []
    all_groups: List[dict] = []
    all_tabs: List[dict] = list(existing_tabs)
    child_to_parent: Dict[str, str] = {}

    # Process each space
    for space in arc_spaces:
        workspace_id = space_to_workspace.get(space.name)
        if not workspace_id:
            continue
        
        print(f"Importing space '{space.name}' -> workspace {workspace_id[:20]}...")
        
        # Track previous sibling for top-level folders in this workspace
        prev_sibling_id = None
        for item in space.children:
            if isinstance(item, BookmarkFolder):
                prev_sibling_id = process_folder(
                    item,
                    workspace_id,
                    None,
                    all_folders,
                    all_groups,
                    all_tabs,
                    child_to_parent,
                    prev_sibling_id,
                )
            elif isinstance(item, Bookmark):
                tab = create_tab(item.url, item.title, workspace_id, group_id=None)
                all_tabs.append(tab)

    # Propagate emptyTabIds
    propagate_empty_tab_ids(all_folders, child_to_parent)

    # Update files
    win["tabs"] = all_tabs
    win["folders"] = all_folders
    win["groups"] = all_groups
    recovery_data["session"] = {"lastUpdate": int(datetime.now().timestamp() * 1000)}

    zen_sessions_data["tabs"] = all_tabs
    zen_sessions_data["folders"] = all_folders
    zen_sessions_data["groups"] = all_groups
    zen_sessions_data["lastCollected"] = int(datetime.now().timestamp() * 1000)

    # Write
    print("\nWriting session files...")
    write_lz4_json(recovery_path, recovery_data)
    print(f"  Updated: {recovery_path.name}")

    if recovery_bak_path.exists():
        write_lz4_json(recovery_bak_path, recovery_data)
        print(f"  Updated: {recovery_bak_path.name}")

    write_lz4_json(zen_sessions_path, zen_sessions_data)
    print(f"  Updated: {zen_sessions_path.name}")

    bookmark_count = sum(1 for t in all_tabs if t.get("pinned") and not t.get("zenIsEmpty"))
    print(f"\nImported {bookmark_count} bookmarks in {len(all_folders)} folders")


# ============== Stats ==============

def count_items(spaces: List[ArcSpace]) -> Tuple[int, int, int]:
    """Count total bookmarks, folders, and standalone tabs."""
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

    total_bm, total_fl, total_standalone = 0, 0, 0
    for space in spaces:
        for item in space.children:
            if isinstance(item, BookmarkFolder):
                bm, fl = count_folder(item)
                total_bm += bm
                total_fl += fl
            elif isinstance(item, Bookmark):
                total_standalone += 1
    return total_bm, total_fl, total_standalone


# ============== Main Entry Point ==============

def import_to_zen() -> bool:
    """
    Main function to import Arc bookmarks to Zen Browser.
    Reads Arc data directly (no HTML file).
    
    Returns True if import was successful.
    """
    print("=" * 60)
    print("Arc Browser -> Zen Browser Migration")
    print("=" * 60)
    
    # Find Zen profile
    profile_path = find_zen_profile()
    if not profile_path:
        print("ERROR: No Zen Browser profile found.")
        return False
    
    print(f"\nZen profile: {profile_path}")
    
    # Read Arc data directly
    print("\nReading Arc Browser data...")
    try:
        arc_spaces = get_arc_spaces()
    except Exception as e:
        print(f"ERROR: Failed to read Arc data: {e}")
        return False
    
    if not arc_spaces:
        print("No Arc Spaces found.")
        return False
    
    print(f"\nFound {len(arc_spaces)} Arc Spaces:")
    for space in arc_spaces:
        folder_count = sum(1 for item in space.children if isinstance(item, BookmarkFolder))
        standalone_count = sum(1 for item in space.children if isinstance(item, Bookmark))
        print(f"  - {space.name}: {folder_count} folders, {standalone_count} standalone tabs")
    
    total_bm, total_fl, total_standalone = count_items(arc_spaces)
    print(f"\nTotal: {total_bm} bookmarks in {total_fl} folders + {total_standalone} standalone tabs")
    
    # Get Zen workspaces
    print("\nReading Zen workspaces...")
    zen_workspaces = get_zen_workspaces(profile_path)
    
    print(f"Found {len(zen_workspaces)} Zen Workspaces:")
    for name in zen_workspaces:
        print(f"  - {name}")
    
    # Match
    print("\nMatching Arc Spaces to Zen Workspaces...")
    mapping = match_spaces_to_workspaces(arc_spaces, zen_workspaces)
    
    matched = {k: v for k, v in mapping.items() if v is not None}
    unmatched = [k for k, v in mapping.items() if v is None]
    
    print(f"\nMatched: {len(matched)}")
    for arc_name, ws_uuid in matched.items():
        zen_name = next((n for n, u in zen_workspaces.items() if u == ws_uuid), "?")
        print(f"  + {arc_name} -> {zen_name}")
    
    if unmatched:
        print(f"\nUnmatched: {len(unmatched)}")
        for name in unmatched:
            print(f"  - {name}")
    
    # Handle unmatched
    if unmatched:
        final_mapping = prompt_for_missing_workspaces(mapping, zen_workspaces)
    else:
        final_mapping = matched
    
    if not final_mapping:
        print("\nNo spaces to import.")
        return False
    
    # Confirm
    print("\n" + "=" * 60)
    print("READY TO IMPORT")
    print("=" * 60)
    print(f"\nWill import {len(final_mapping)} spaces:")
    for arc_name in final_mapping:
        print(f"  - {arc_name}")
    
    print("\nWARNING: This will DELETE all existing pinned tabs and folders!")
    confirm = input("\nProceed? (yes/no): ").strip().lower()
    
    if confirm != "yes":
        print("Aborted.")
        return False
    
    # Backup
    print("\nCreating backups...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for filename in ["zen-sessions.jsonlz4"]:
        src = profile_path / filename
        if src.exists():
            dst = src.with_suffix(f".jsonlz4.backup_{timestamp}")
            shutil.copy2(src, dst)
            print(f"  Backup: {dst.name}")
    
    recovery_path = profile_path / "sessionstore-backups" / "recovery.jsonlz4"
    if recovery_path.exists():
        dst = recovery_path.with_suffix(f".jsonlz4.backup_{timestamp}")
        shutil.copy2(recovery_path, dst)
        print(f"  Backup: {dst.name}")
    
    # Clean & Import
    clean_all_pinned_tabs_and_folders(profile_path)
    
    print("\nImporting...")
    import_spaces_to_zen(profile_path, arc_spaces, final_mapping)
    
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    print("\nNow open Zen Browser to see your imported tabs and folders.")
    
    return True


if __name__ == "__main__":
    import_to_zen()
