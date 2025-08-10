#!/usr/bin/env python3
"""CLI utility for managing DSSketch data files"""

import argparse
import sys
from pathlib import Path


# После рефакторинга будет: from src.dssketch.config import get_data_manager
# Сейчас для примера:
def main():
    parser = argparse.ArgumentParser(
        prog='dssketch-data',
        description='Manage DSSketch configuration data files'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Command: info
    info_parser = subparsers.add_parser('info', help='Show data files locations')
    
    # Command: reset
    reset_parser = subparsers.add_parser('reset', help='Reset data files to defaults')
    reset_parser.add_argument('--file', help='Specific file to reset (e.g., unified-mappings.yaml)')
    reset_parser.add_argument('--all', action='store_true', help='Reset all files')
    
    # Command: path
    path_parser = subparsers.add_parser('path', help='Show user data directory path')
    
    # Command: edit
    edit_parser = subparsers.add_parser('edit', help='Open user data directory in file manager')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Import here to avoid circular imports during refactoring
    try:
        from src.dssketch.config import get_data_manager
    except ImportError:
        print("⚠️  This utility will be available after refactoring to src/ structure")
        return 1
    
    dm = get_data_manager()
    
    if args.command == 'info':
        info = dm.get_data_info()
        print(f"\n📦 Package data directory:\n   {info['package_data_dir']}")
        print(f"\n📁 User data directory:\n   {info['user_data_dir']}")
        print(f"\n📄 User files: {', '.join(info['user_files']) or 'None'}")
        print(f"📄 Package files: {', '.join(info['package_files'])}")
        print("\n💡 Tip: User files override package defaults when present")
        
    elif args.command == 'reset':
        if args.file:
            dm.reset_to_defaults(args.file)
        elif args.all:
            dm.reset_to_defaults()
        else:
            print("Specify --file <filename> or --all")
            return 1
            
    elif args.command == 'path':
        print(dm.user_data_dir)
        
    elif args.command == 'edit':
        import subprocess
        import platform
        
        path = dm.user_data_dir
        if platform.system() == 'Windows':
            subprocess.run(['explorer', str(path)])
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', str(path)])
        else:  # Linux
            subprocess.run(['xdg-open', str(path)])
        print(f"📂 Opened: {path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())