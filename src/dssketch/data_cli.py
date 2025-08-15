#!/usr/bin/env python3
"""CLI utility for managing DSSketch data files"""

import argparse
import platform
import subprocess
import sys

from .config import get_data_manager


def main():
    parser = argparse.ArgumentParser(
        prog="dssketch-data", description="Manage DSSketch configuration data files"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: info
    info_parser = subparsers.add_parser("info", help="Show data files locations")

    # Command: reset
    reset_parser = subparsers.add_parser("reset", help="Reset data files to defaults")
    reset_parser.add_argument("--file", help="Specific file to reset (e.g., unified-mappings.yaml)")
    reset_parser.add_argument("--all", action="store_true", help="Reset all files")

    # Command: path
    path_parser = subparsers.add_parser("path", help="Show user data directory path")

    # Command: edit
    edit_parser = subparsers.add_parser("edit", help="Open user data directory in file manager")

    # Command: copy
    copy_parser = subparsers.add_parser(
        "copy", help="Copy package file to user directory for editing"
    )
    copy_parser.add_argument("file", help="File to copy (e.g., unified-mappings.yaml)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Get data manager
    dm = get_data_manager()

    if args.command == "info":
        info = dm.get_data_info()
        print(f"\n📦 Package data directory:\n   {info['package_data_dir']}")
        print(f"\n📁 User data directory:\n   {info['user_data_dir']}")

        if info["user_files"]:
            print("\n📄 User files (override defaults):")
            for file in info["user_files"]:
                print(f"   • {file}")
        else:
            print("\n📄 User files: None")

        if info["package_files"]:
            print("\n📄 Package files (defaults):")
            for file in info["package_files"]:
                override = " (overridden)" if file in info["user_files"] else ""
                print(f"   • {file}{override}")

        print("\n💡 Tip: User files override package defaults when present")
        print("💡 Use 'dssketch-data copy <file>' to copy a default file for editing")

    elif args.command == "reset":
        if args.file:
            dm.reset_to_defaults(args.file)
        elif args.all:
            dm.reset_to_defaults()
        else:
            print("Specify --file <filename> or --all")
            return 1

    elif args.command == "path":
        print(dm.user_data_dir)

    elif args.command == "edit":
        path = dm.user_data_dir

        # Ensure directory exists
        path.mkdir(parents=True, exist_ok=True)

        # Open in file manager
        try:
            if platform.system() == "Windows":
                subprocess.run(["explorer", str(path)])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(path)])
            print(f"📂 Opened: {path}")
        except Exception as e:
            print(f"❌ Could not open directory: {e}")
            print(f"📁 Directory path: {path}")
            return 1

    elif args.command == "copy":
        if not args.file:
            print("Please specify a file to copy")
            return 1

        success = dm.copy_package_to_user(args.file)
        if success:
            print(f"💡 You can now edit: {dm.user_data_dir / args.file}")
        return 0 if success else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
