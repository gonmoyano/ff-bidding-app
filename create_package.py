#!/usr/bin/env python3
"""Build script for the addon."""

import zipfile
from pathlib import Path


def update_version_file():
    """Update version.py."""
    package_data = {}
    with open("package.py", encoding='utf-8') as f:
        exec(f.read(), package_data)
    
    version = package_data.get("version", "0.0.0")
    name = package_data.get("name", "unknown")
    
    version_file = Path(f"client/{name}/version.py")
    if version_file.parent.exists():
        version_file.write_text(f'__version__ = "{version}"\n', encoding='utf-8')
        print(f"Updated {version_file}")
    
    return name, version


def create_package():
    """Create the addon package."""
    name, version = update_version_file()
    
    package_dir = Path("package")
    package_dir.mkdir(exist_ok=True)
    
    package_filename = f"{name}-{version}.zip"
    package_path = package_dir / package_filename
    
    exclude_patterns = [
        "__pycache__", "*.pyc", ".git", ".gitignore",
        "node_modules", ".vscode", "package"
    ]
    
    def should_exclude(path):
        path_str = str(path)
        for pattern in exclude_patterns:
            if pattern in path_str:
                return True
        return False
    
    print(f"Creating package: {package_path}")
    
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for directory in ["server", "client"]:
            dir_path = Path(directory)
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file() and not should_exclude(file_path):
                        arcname = file_path.relative_to(".")
                        zf.write(file_path, arcname)
                        print(f"  Added: {arcname}")
        
        zf.write("package.py", "package.py")
        print(f"  Added: package.py")
    
    print(f"\nPackage created: {package_path}")
    return package_path


if __name__ == "__main__":
    try:
        package_path = create_package()
        print(f"\nYou can now upload {package_path} to AYON server")
    except Exception as e:
        print(f"\nError: {e}")
        exit(1)
