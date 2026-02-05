#!/usr/bin/env python3
"""
Arc Bookmarks Tool

Export Arc Browser bookmarks or migrate directly to Zen Browser.
"""

import subprocess
import sys
from pathlib import Path

from core import Colors, export_to_html, ArcDataError


def is_zen_running() -> bool:
    """Check if Zen Browser is running (macOS only)."""
    result = subprocess.run(
        ["pgrep", "-f", "Zen Browser"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def wait_for_zen_closed():
    """Check if Zen is running and wait for user to close it."""
    while is_zen_running():
        print(f"\n{Colors.RED}Zen Browser is currently running!{Colors.RESET}")
        print("Please close Zen Browser and press Enter to continue...")
        input()
    print(f"{Colors.GREEN}Zen Browser is closed.{Colors.RESET}")


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
        elif choice == "0" or choice.lower() == "q":
            print("\nBye!")
            sys.exit(0)
        else:
            print(f"\n{Colors.RED}Invalid option.{Colors.RESET}")


if __name__ == "__main__":
    main()
