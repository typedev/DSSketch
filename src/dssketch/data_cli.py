#!/usr/bin/env python3
"""CLI utility for managing DSSketch data files"""

import argparse
import sys
from pathlib import Path


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
    
    # For now, just show basic info until data manager is implemented
    if args.command == 'info':
        from . import __file__ as package_file
        package_dir = Path(package_file).parent
        data_dir = package_dir / 'data'
        
        print(f"\n📦 Package data directory:")
        print(f"   {data_dir}")
        
        if data_dir.exists():
            print(f"\n📁 Available data files:")
            for file in sorted(data_dir.glob('*')):
                if file.is_file():
                    print(f"   • {file.name}")
        else:
            print("   ⚠️  Data directory not found")
    
    elif args.command == 'path':
        from . import __file__ as package_file
        package_dir = Path(package_file).parent
        data_dir = package_dir / 'data'
        print(str(data_dir))
    
    else:
        print(f"Command '{args.command}' not yet implemented")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())