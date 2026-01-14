"""
Standalone test script for Fireframe Prodigy
Run this to test if the app works outside of AYON

Usage:
    python test_app.py
"""

import sys
from pathlib import Path

# Add the client directory to path
client_dir = Path(__file__).parent / "client"
sys.path.insert(0, str(client_dir))

print("=" * 60)
print("Testing Fireframe Prodigy Standalone")
print("=" * 60)
print()

try:
    print("1. Importing QtWidgets...")
    from qtpy import QtWidgets
    print("   ✓ QtWidgets imported")
except ImportError as e:
    print(f"   ✗ Failed to import QtWidgets: {e}")
    print("   Install: pip install qtpy PyQt5")
    sys.exit(1)

try:
    print("2. Creating QApplication...")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    print("   ✓ QApplication created")
except Exception as e:
    print(f"   ✗ Failed to create QApplication: {e}")
    sys.exit(1)

try:
    print("3. Importing FireframeProdigyApp...")
    from ff_package_manager.sg_app import FireframeProdigyApp
    print("   ✓ FireframeProdigyApp imported")
except ImportError as e:
    print(f"   ✗ Failed to import FireframeProdigyApp: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("4. Creating app window...")
    window = FireframeProdigyApp(
        sg_url="",
        sg_script_name="",
        sg_api_key="",
        output_directory=""
    )
    print("   ✓ Window created")
except Exception as e:
    print(f"   ✗ Failed to create window: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("5. Showing window...")
    window.show()
    print("   ✓ Window shown")
    print()
    print("=" * 60)
    print("SUCCESS! If you can see the window, the app works!")
    print("If the window doesn't appear, check for errors above.")
    print("=" * 60)
    print()
except Exception as e:
    print(f"   ✗ Failed to show window: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Run event loop
sys.exit(app.exec_())