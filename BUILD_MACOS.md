# Building Fireframe Prodigy for macOS

This guide explains how to build Fireframe Prodigy as a native macOS application that runs on both Intel (x86_64) and Apple Silicon (arm64) Macs.

## Quick Start

### Prerequisites

- macOS 10.15 (Catalina) or later
- Python 3.9 or later
- Xcode Command Line Tools: `xcode-select --install`

### Install Dependencies

```bash
pip install -r requirements-macos.txt
```

### Build for Current Architecture

```bash
./scripts/build_macos.sh
```

The app will be created at `dist/Fireframe Prodigy.app`.

## Universal Binary (Intel + Apple Silicon)

A universal binary runs natively on both Intel and Apple Silicon Macs without Rosetta translation.

### Option 1: Build on Apple Silicon Mac (Recommended)

If you have an Apple Silicon Mac (M1/M2/M3), you can build both architectures locally:

```bash
./scripts/build_macos_universal.sh
```

This script:
1. Builds the arm64 version natively
2. Builds the x86_64 version using Rosetta
3. Merges both into a universal binary

Output: `dist/universal/Fireframe Prodigy.app`

### Option 2: GitHub Actions (Automated)

Push a version tag to trigger automatic builds:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow builds on both architectures and creates a universal DMG.

### Option 3: Manual Merge

Build on separate machines and merge:

```bash
# On Intel Mac
./scripts/build_macos.sh
# Copy dist/Fireframe Prodigy.app to shared location as "Intel.app"

# On Apple Silicon Mac
./scripts/build_macos.sh
# Copy dist/Fireframe Prodigy.app as "AppleSilicon.app"

# Merge (on any Mac)
lipo -create \
  "Intel.app/Contents/MacOS/Fireframe Prodigy" \
  "AppleSilicon.app/Contents/MacOS/Fireframe Prodigy" \
  -output "Universal.app/Contents/MacOS/Fireframe Prodigy"
```

## Code Signing & Notarization

For distribution outside the App Store, Apple requires code signing and notarization.

### Requirements

- Apple Developer account ($99/year)
- Developer ID Application certificate
- App-specific password for notarization

### Setup

1. Create an app-specific password at https://appleid.apple.com
2. Export your credentials:

```bash
export DEVELOPER_ID="Developer ID Application: Your Company (XXXXXXXXXX)"
export APPLE_ID="your@email.com"
export APPLE_TEAM_ID="XXXXXXXXXX"
export NOTARIZATION_PWD="xxxx-xxxx-xxxx-xxxx"
```

### Sign and Notarize

```bash
./scripts/sign_and_notarize.sh
```

This process takes 5-15 minutes as Apple verifies your app.

## Creating a DMG Installer

```bash
./scripts/create_dmg.sh
```

Creates `dist/FF_Package_Manager.dmg` with drag-and-drop installation.

## File Structure

```
ff-bidding-app/
├── ff_bidding_app.spec      # PyInstaller configuration
├── requirements-macos.txt   # Python dependencies
├── BUILD_MACOS.md          # This file
├── macos/
│   ├── Info.plist          # App metadata
│   ├── entitlements.plist  # App permissions
│   ├── ICON_README.md      # Icon creation guide
│   └── app.icns            # App icon (you create this)
├── scripts/
│   ├── build_macos.sh           # Single-arch build
│   ├── build_macos_universal.sh # Universal build
│   ├── sign_and_notarize.sh     # Code signing
│   └── create_dmg.sh            # DMG creation
└── .github/workflows/
    └── build-macos.yml     # CI/CD workflow
```

## Troubleshooting

### "App is damaged and can't be opened"

The app is not signed. Either:
- Sign it with your Developer ID
- Remove the quarantine attribute: `xattr -cr "Fireframe Prodigy.app"`

### "Cannot be opened because the developer cannot be verified"

The app is signed but not notarized. Either:
- Notarize the app with `./scripts/sign_and_notarize.sh`
- Right-click the app and select "Open" to bypass Gatekeeper

### Build fails with "No module named..."

Ensure all dependencies are installed:
```bash
pip install -r requirements-macos.txt
```

### Universal binary shows only one architecture

Verify with:
```bash
file "dist/universal/Fireframe Prodigy.app/Contents/MacOS/Fireframe Prodigy"
```

Should show: `Mach-O universal binary with 2 architectures`

## App Icon

To add a custom icon:

1. Create a 1024x1024 PNG image
2. Follow instructions in `macos/ICON_README.md`
3. Place `app.icns` in the `macos/` directory
4. Rebuild the app

## Version Updates

Update version in these files:
- `package.py` - `version` variable
- `macos/Info.plist` - `CFBundleVersion` and `CFBundleShortVersionString`
- `ff_bidding_app.spec` - `info_plist` dictionary
