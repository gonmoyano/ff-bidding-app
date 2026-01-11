# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for FF Package Manager
Supports macOS universal binary builds (Intel x86_64 + Apple Silicon arm64)

Build commands:
  # Build for current architecture only:
  pyinstaller ff_bidding_app.spec

  # Build universal binary (requires building on both architectures and merging):
  # See scripts/build_macos_universal.sh
"""

import sys
import os
from pathlib import Path

# Determine target architecture for macOS
# Set via environment variable or default to native
target_arch = os.environ.get('TARGET_ARCH', None)

block_cipher = None

# Project paths
PROJECT_ROOT = Path(SPECPATH)
CLIENT_DIR = PROJECT_ROOT / 'client'
APP_DIR = CLIENT_DIR / 'ff_bidding_app'

# Collect all Python files from the client directory
datas = [
    # Include the entire client package
    (str(CLIENT_DIR / 'ff_bidding_app'), 'ff_bidding_app'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # PySide6 modules
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtNetwork',

    # Application modules
    'ff_bidding_app',
    'ff_bidding_app.app',
    'ff_bidding_app.shotgrid',
    'ff_bidding_app.package_data_treeview',
    'ff_bidding_app.packages_tab',
    'ff_bidding_app.bidding_tab',
    'ff_bidding_app.delivery_tab',
    'ff_bidding_app.bid_selector_widget',
    'ff_bidding_app.settings',
    'ff_bidding_app.settings_dialog',
    'ff_bidding_app.gdrive_service',
    'ff_bidding_app.spreadsheet_cache',
    'ff_bidding_app.logger',
    'ff_bidding_app.assets_tab',
    'ff_bidding_app.costs_tab',
    'ff_bidding_app.rates_tab',
    'ff_bidding_app.vfx_breakdown_tab',
    'ff_bidding_app.vfx_breakdown_widget',
    'ff_bidding_app.vfx_breakdown_model',
    'ff_bidding_app.spreadsheet_widget',
    'ff_bidding_app.formula_evaluator',
    'ff_bidding_app.table_with_totals_bar',
    'ff_bidding_app.thumbnail_cache',
    'ff_bidding_app.image_viewer_widget',
    'ff_bidding_app.document_viewer_widget',
    'ff_bidding_app.document_folder_pane_widget',
    'ff_bidding_app.folder_pane_widget',
    'ff_bidding_app.sliding_overlay_panel',
    'ff_bidding_app.multi_entity_reference_widget',

    # Google API dependencies (optional)
    'google.auth',
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.errors',

    # ShotGrid API
    'shotgun_api3',

    # Standard library modules that might be needed
    'json',
    'logging',
    'datetime',
    'pathlib',
    'ssl',
    'certifi',
]

a = Analysis(
    [str(PROJECT_ROOT / 'run_standalone.py')],
    pathex=[str(CLIENT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'PyQt5',  # We're using PySide6
        'PyQt6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FF Package Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window on macOS
    disable_windowed_traceback=False,
    argv_emulation=True,  # Enable argv emulation for macOS
    target_arch=target_arch,  # None = native, 'x86_64', 'arm64', or 'universal2'
    codesign_identity=os.environ.get('CODESIGN_IDENTITY', None),
    entitlements_file=os.environ.get('ENTITLEMENTS_FILE', None),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FF Package Manager',
)

# macOS-specific: Create .app bundle
app = BUNDLE(
    coll,
    name='FF Package Manager.app',
    icon=str(PROJECT_ROOT / 'macos' / 'app.icns') if (PROJECT_ROOT / 'macos' / 'app.icns').exists() else None,
    bundle_identifier='com.fireframe.ffpackagemanager',
    info_plist={
        'CFBundleName': 'FF Package Manager',
        'CFBundleDisplayName': 'FF Package Manager',
        'CFBundleIdentifier': 'com.fireframe.ffpackagemanager',
        'CFBundleVersion': '0.0.1',
        'CFBundleShortVersionString': '0.0.1',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'FFPM',
        'CFBundleExecutable': 'FF Package Manager',
        'CFBundleIconFile': 'app.icns',
        'CFBundleInfoDictionaryVersion': '6.0',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'NSPrincipalClass': 'NSApplication',
        # Privacy permissions
        'NSAppleEventsUsageDescription': 'FF Package Manager needs to control other apps to integrate with your workflow.',
        'NSDocumentsFolderUsageDescription': 'FF Package Manager needs access to Documents to save packages.',
        'NSDownloadsFolderUsageDescription': 'FF Package Manager needs access to Downloads to save packages.',
    },
)
