# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Fireframe Prodigy
Supports macOS universal binary builds (Intel x86_64 + Apple Silicon arm64)

Build commands:
  # Build for current architecture only:
  pyinstaller ff_bidding_app.spec

  # Build universal binary (requires building on both architectures and merging):
  # See scripts/build_macos_universal.sh

Note: The app launches in Terminal.app with log output visible.
      Terminal stays open after app exit for reviewing logs.
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Determine target architecture for macOS
# Set via environment variable or default to native
target_arch = os.environ.get('TARGET_ARCH', None)

# Option to launch with terminal (default: True)
# Set LAUNCH_IN_TERMINAL=0 to disable
launch_in_terminal = os.environ.get('LAUNCH_IN_TERMINAL', '1') == '1'

block_cipher = None

# Project paths
PROJECT_ROOT = Path(SPECPATH)
CLIENT_DIR = PROJECT_ROOT / 'client'
APP_DIR = CLIENT_DIR / 'ff_bidding_app'

# Add the client directory to sys.path so PyInstaller can find ff_bidding_app
sys.path.insert(0, str(CLIENT_DIR))

# Collect all submodules from ff_bidding_app
ff_bidding_app_modules = collect_submodules('ff_bidding_app')

# Data files (non-Python files like icons, configs, etc.)
datas = []

# Hidden imports that PyInstaller might miss
hiddenimports = ff_bidding_app_modules + [
    # PySide6 modules
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtSvg',
    'PySide6.QtNetwork',
    'PySide6.QtPrintSupport',

    # Formula evaluation (used by rates_tab)
    'numpy',
    'formulas',
    'formulas.parser',
    'formulas.tokens',
    'formulas.functions',

    # Google API dependencies (optional)
    'google.auth',
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.errors',
    'googleapiclient.http',

    # ShotGrid API
    'shotgun_api3',

    # Standard library modules that might be needed
    'json',
    'logging',
    'datetime',
    'pathlib',
    'ssl',
    'certifi',
    'http.cookiejar',
    'urllib.request',
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

# The actual executable name (launcher script will call this)
exe_name = 'FireframeProdigy-bin' if launch_in_terminal else 'Fireframe Prodigy'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window on macOS (Terminal handles this)
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
    name='Fireframe Prodigy',
)

# Determine the bundle executable name
bundle_executable = 'Fireframe Prodigy' if launch_in_terminal else exe_name

# macOS-specific: Create .app bundle
app = BUNDLE(
    coll,
    name='Fireframe Prodigy.app',
    icon=str(PROJECT_ROOT / 'macos' / 'app.icns') if (PROJECT_ROOT / 'macos' / 'app.icns').exists() else None,
    bundle_identifier='com.fireframe.fireframeprodigy',
    info_plist={
        'CFBundleName': 'Fireframe Prodigy',
        'CFBundleDisplayName': 'Fireframe Prodigy',
        'CFBundleIdentifier': 'com.fireframe.fireframeprodigy',
        'CFBundleVersion': '0.0.1',
        'CFBundleShortVersionString': '0.0.1',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'FFPD',
        'CFBundleExecutable': bundle_executable,
        'CFBundleIconFile': 'app.icns',
        'CFBundleInfoDictionaryVersion': '6.0',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'NSSupportsAutomaticGraphicsSwitching': True,
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'NSPrincipalClass': 'NSApplication',
        # Required for Terminal.app integration
        'LSUIElement': False,
        # Privacy permissions
        'NSAppleEventsUsageDescription': 'Fireframe Prodigy needs to control Terminal.app to display log output.',
        'NSDocumentsFolderUsageDescription': 'Fireframe Prodigy needs access to Documents to save packages.',
        'NSDownloadsFolderUsageDescription': 'Fireframe Prodigy needs access to Downloads to save packages.',
    },
)
