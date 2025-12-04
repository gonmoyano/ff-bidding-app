#!/usr/bin/env python3
"""
Standalone launcher for FF Package Manager
Run this to test the app without AYON

Usage:
    python run_standalone.py
"""

import sys
from pathlib import Path

# Add the client directory to path
client_dir = Path(__file__).parent / "client"
sys.path.insert(0, str(client_dir))

print("=" * 80)
print("FF Package Manager - Standalone Mode")
print("=" * 80)
print()

try:
    print("Importing QtWidgets...")
    from PySide6 import QtWidgets

    print("✓ QtWidgets imported")
except ImportError as e:
    print(f"✗ Failed to import QtWidgets: {e}")
    print("  Install: pip install qtpy PyQt5")
    sys.exit(1)

try:
    print("Creating QApplication...")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    print("✓ QApplication created")
except Exception as e:
    print(f"✗ Failed to create QApplication: {e}")
    sys.exit(1)

try:
    print("Importing FFPackageManagerApp...")
    # Import directly from sg_app to avoid loading addon.py
    import importlib.util

    sg_app_path = client_dir / "ff_bidding_app" / "app.py"
    spec = importlib.util.spec_from_file_location("sg_app", sg_app_path)
    sg_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sg_app)
    FFPackageManagerApp = sg_app.PackageManagerApp
    print("✓ FFPackageManagerApp imported")
except ImportError as e:
    print(f"✗ Failed to import FFPackageManagerApp: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

try:
    print("Creating app window...")


    # Apply dark theme BEFORE creating the window
    FFPackageManagerApp.apply_dark_theme(app)
    # Default settings for standalone mode
    window = FFPackageManagerApp(
        sg_url="https://fireframe.shotgrid.autodesk.com/",
        sg_script_name="ff_bidding_app",
        sg_api_key="tiviqwk^jeZqaon8aeemdnnnk",
        output_directory=str(Path.home() / "shotgrid_packages")
    )
    print("✓ Window created")
except Exception as e:
    print(f"✗ Failed to create window: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

try:
    print("Showing window...")
    window.show()
    print("✓ Window shown")
    print()
    print("=" * 80)
    print("SUCCESS! The application should now be visible.")
    print("=" * 80)
    print()
    print("Note: This is running in STANDALONE mode without AYON.")
    print("To connect to real Shotgrid, configure settings in the GUI.")
    print()
except Exception as e:
    print(f"✗ Failed to show window: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Run event loop
print("Starting event loop...")
sys.exit(app.exec())