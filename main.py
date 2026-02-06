#!/usr/bin/env python3
"""
Arc Bookmarks Tool

Export Arc Browser bookmarks or migrate directly to Zen Browser.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from core import Colors, export_to_html, ArcDataError


def is_zen_running() -> bool:
    """Check if Zen Browser is running (macOS only)."""
    # Проверяем несколько возможных имен процесса
    patterns = ["zen", "Zen Browser", "zen-browser"]
    for pattern in patterns:
        result = subprocess.run(
            ["pgrep", "-if", pattern],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True
    return False


def wait_for_zen_closed():
    """Check if Zen is running and wait for user to close it."""
    while is_zen_running():
        print(f"\n{Colors.RED}Zen Browser is currently running!{Colors.RESET}")
        print("Please close Zen Browser and press Enter to continue...")
        input()
    print(f"{Colors.GREEN}Zen Browser is closed.{Colors.RESET}")


def get_zen_profile_path() -> Path | None:
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


def get_backup_files() -> List[Tuple[Path, str]]:
    """
    Get all backup files sorted by timestamp (newest first).
    Returns list of (path, timestamp) tuples.
    """
    profile_path = get_zen_profile_path()
    if not profile_path:
        return []
    
    backups = []
    
    # Ищем бекапы zen-sessions
    for f in profile_path.glob("zen-sessions.jsonlz4.backup_*"):
        # Извлекаем timestamp из имени файла
        timestamp = f.name.replace("zen-sessions.jsonlz4.backup_", "")
        backups.append((f, timestamp))
    
    # Ищем бекапы recovery
    recovery_dir = profile_path / "sessionstore-backups"
    if recovery_dir.exists():
        for f in recovery_dir.glob("recovery.jsonlz4.backup_*"):
            timestamp = f.name.replace("recovery.jsonlz4.backup_", "")
            # Проверяем, что такой timestamp ещё не добавлен (чтобы не дублировать)
            if not any(t == timestamp for _, t in backups):
                backups.append((f, timestamp))
    
    # Сортируем по timestamp (новые первые)
    backups.sort(key=lambda x: x[1], reverse=True)
    
    return backups


def get_unique_backup_timestamps() -> List[str]:
    """Get unique backup timestamps sorted by date (newest first)."""
    backups = get_backup_files()
    timestamps = sorted(set(t for _, t in backups), reverse=True)
    return timestamps


def restore_from_backup(timestamp: str | None = None) -> bool:
    """
    Restore Zen session files from backup.
    If timestamp is None, uses the latest backup.
    Returns True if successful.
    """
    profile_path = get_zen_profile_path()
    if not profile_path:
        print(f"{Colors.RED}Zen profile not found.{Colors.RESET}")
        return False
    
    timestamps = get_unique_backup_timestamps()
    if not timestamps:
        print(f"{Colors.RED}No backups found.{Colors.RESET}")
        return False
    
    # Если timestamp не указан, используем последний
    if timestamp is None:
        timestamp = timestamps[0]
    elif timestamp not in timestamps:
        print(f"{Colors.RED}Backup with timestamp '{timestamp}' not found.{Colors.RESET}")
        return False
    
    # Восстанавливаем zen-sessions
    zen_backup = profile_path / f"zen-sessions.jsonlz4.backup_{timestamp}"
    zen_target = profile_path / "zen-sessions.jsonlz4"
    
    # Восстанавливаем recovery
    recovery_dir = profile_path / "sessionstore-backups"
    recovery_backup = recovery_dir / f"recovery.jsonlz4.backup_{timestamp}"
    recovery_target = recovery_dir / "recovery.jsonlz4"
    recovery_bak_target = recovery_dir / "recovery.baklz4"
    
    restored_count = 0
    
    if zen_backup.exists():
        shutil.copy2(zen_backup, zen_target)
        print(f"  Restored: {zen_target.name}")
        restored_count += 1
    
    if recovery_backup.exists():
        shutil.copy2(recovery_backup, recovery_target)
        print(f"  Restored: {recovery_target.name}")
        # Также копируем в baklz4
        if recovery_bak_target.exists() or recovery_target.exists():
            shutil.copy2(recovery_backup, recovery_bak_target)
            print(f"  Restored: {recovery_bak_target.name}")
        restored_count += 1
    
    return restored_count > 0


def delete_all_backups() -> int:
    """
    Delete all backup files.
    Returns number of deleted files.
    """
    profile_path = get_zen_profile_path()
    if not profile_path:
        return 0
    
    deleted = 0
    
    # Удаляем бекапы zen-sessions
    for f in profile_path.glob("zen-sessions.jsonlz4.backup_*"):
        f.unlink()
        deleted += 1
    
    # Удаляем бекапы recovery
    recovery_dir = profile_path / "sessionstore-backups"
    if recovery_dir.exists():
        for f in recovery_dir.glob("recovery.jsonlz4.backup_*"):
            f.unlink()
            deleted += 1
    
    return deleted


def print_header():
    """Print application header."""
    print()
    print("=" * 60)
    print(f"{Colors.BOLD}Arc Bookmarks Tool{Colors.RESET}")
    print("=" * 60)


def print_menu():
    """Print main menu."""
    print()
    print("Choose an option:")
    print()
    print(f"  {Colors.CYAN}1{Colors.RESET}. Export Arc bookmarks to HTML file")
    print(f"  {Colors.CYAN}2{Colors.RESET}. Export Zen bookmarks to HTML file")
    print(f"  {Colors.CYAN}3{Colors.RESET}. Migrate Arc bookmarks to Zen Browser")
    print()
    print(f"  {Colors.YELLOW}4{Colors.RESET}. Restore Zen from backup")
    print(f"  {Colors.YELLOW}5{Colors.RESET}. Delete all backups")
    print()
    print(f"  {Colors.GREY}0{Colors.RESET}. Exit")
    print()


def export_bookmarks():
    """Export Arc bookmarks to HTML file."""
    print()
    print("-" * 60)
    print("Export to HTML")
    print("-" * 60)
    
    output_input = input("\nOutput filename (Enter for auto): ").strip()
    
    if output_input:
        output_path = Path(output_input)
    else:
        output_path = None
    
    try:
        bookmarks, folders = export_to_html(
            output_path=output_path,
            verbose=False,
            silent=False,
        )
        print()
        print(f"{Colors.GREEN}Export completed!{Colors.RESET}")
        print(f"  Bookmarks: {bookmarks}")
        print(f"  Folders: {folders}")
        sys.exit(0)
        
    except ArcDataError as e:
        print(f"\n{Colors.RED}Error:{Colors.RESET} {e}")
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error:{Colors.RESET} {e}")


def export_zen_bookmarks():
    """Export Zen Browser bookmarks to HTML file."""
    print()
    print("-" * 60)
    print("Export Zen to HTML")
    print("-" * 60)
    
    # Ask for output filename
    output_input = input(f"\nOutput filename (Enter for auto): ").strip()
    
    if output_input:
        output_path = Path(output_input)
    else:
        output_path = None
    
    try:
        from core import export_zen_to_html
        bookmarks, folders = export_zen_to_html(output_path=output_path)
        print()
        print(f"{Colors.GREEN}Export completed!{Colors.RESET}")
        print(f"  Bookmarks: {bookmarks}")
        print(f"  Folders: {folders}")
        sys.exit(0)
        
    except FileNotFoundError as e:
        print(f"\n{Colors.RED}Error:{Colors.RESET} {e}")
    except ImportError as e:
        print(f"\n{Colors.RED}Error:{Colors.RESET} Failed to import zen_exporter: {e}")
        print("Make sure lz4 is installed: pip install lz4")
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error:{Colors.RESET} {e}")


def migrate_to_zen():
    """Migrate Arc bookmarks directly to Zen Browser."""
    print()
    print("-" * 60)
    print("Migrate to Zen Browser")
    print("-" * 60)
    
    # Auto-check if Zen is running
    wait_for_zen_closed()
    
    try:
        from core import import_to_zen
        success = import_to_zen()
        
        if success:
            print(f"\n{Colors.GREEN}Migration completed successfully!{Colors.RESET}")
            print("\nExiting...")
            sys.exit(0)
            
    except ImportError as e:
        print(f"\n{Colors.RED}Error:{Colors.RESET} Failed to import zen_importer: {e}")
        print("Make sure lz4 is installed: pip install lz4")
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error:{Colors.RESET} {e}")


def restore_backup_menu():
    """Restore Zen session files from backup."""
    print()
    print("-" * 60)
    print("Restore from Backup")
    print("-" * 60)
    
    timestamps = get_unique_backup_timestamps()
    
    if not timestamps:
        print(f"\n{Colors.YELLOW}No backups found.{Colors.RESET}")
        return
    
    print(f"\nAvailable backups ({len(timestamps)}):")
    for i, ts in enumerate(timestamps, 1):
        # Форматируем timestamp для читаемости (YYYYMMDD_HHMMSS -> YYYY-MM-DD HH:MM:SS)
        formatted = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}"
        marker = f"{Colors.GREEN}(latest){Colors.RESET}" if i == 1 else ""
        print(f"  {Colors.CYAN}{i}{Colors.RESET}. {formatted} {marker}")
    
    print()
    choice = input("Select backup number (Enter for latest): ").strip()
    
    if choice == "":
        selected_ts = timestamps[0]
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(timestamps):
                selected_ts = timestamps[idx]
            else:
                print(f"{Colors.RED}Invalid number.{Colors.RESET}")
                return
        except ValueError:
            print(f"{Colors.RED}Invalid input.{Colors.RESET}")
            return
    
    # Проверяем, что Zen закрыт
    wait_for_zen_closed()
    
    print(f"\nRestoring from backup {selected_ts}...")
    
    if restore_from_backup(selected_ts):
        print(f"\n{Colors.GREEN}Restore completed!{Colors.RESET}")
        print("You can now open Zen Browser.")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}Restore failed.{Colors.RESET}")


def delete_backups_menu():
    """Delete all backup files."""
    print()
    print("-" * 60)
    print("Delete All Backups")
    print("-" * 60)
    
    timestamps = get_unique_backup_timestamps()
    
    if not timestamps:
        print(f"\n{Colors.YELLOW}No backups found.{Colors.RESET}")
        return
    
    backups = get_backup_files()
    print(f"\nFound {len(backups)} backup files ({len(timestamps)} timestamps):")
    for ts in timestamps:
        formatted = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}"
        print(f"  - {formatted}")
    
    print()
    confirm = input(f"{Colors.YELLOW}Delete all backups? (yes/no):{Colors.RESET} ").strip().lower()
    
    if confirm != "yes":
        print("Cancelled.")
        return
    
    deleted = delete_all_backups()
    print(f"\n{Colors.GREEN}Deleted {deleted} backup files.{Colors.RESET}")


def check_macos():
    """Check if running on macOS, exit if not."""
    if sys.platform != "darwin":
        print(f"\n{Colors.RED}Error: This tool only works on macOS.{Colors.RESET}")
        print(f"Current platform: {sys.platform}")
        sys.exit(1)


def main():
    """Main entry point."""
    check_macos()
    print_header()
    
    while True:
        print_menu()
        
        choice = input("Select option: ").strip()
        
        if choice == "1":
            export_bookmarks()
        elif choice == "2":
            export_zen_bookmarks()
        elif choice == "3":
            migrate_to_zen()
        elif choice == "4":
            restore_backup_menu()
        elif choice == "5":
            delete_backups_menu()
        elif choice == "0" or choice.lower() == "q":
            print("\nBye!")
            sys.exit(0)
        else:
            print(f"\n{Colors.RED}Invalid option.{Colors.RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBye!")
        sys.exit(0)
