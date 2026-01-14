#!/bin/bash
#
# Create a DMG installer for Fireframe Prodigy
#
# Usage:
#   ./scripts/create_dmg.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_PATH="$PROJECT_ROOT/dist/universal/Fireframe Prodigy.app"
DMG_PATH="$PROJECT_ROOT/dist/Fireframe_Prodigy.dmg"
VOLUME_NAME="Fireframe Prodigy"
TEMP_DMG="$PROJECT_ROOT/dist/temp.dmg"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Creating DMG Installer${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check app exists
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Error: App not found at $APP_PATH${NC}"
    echo "Run ./scripts/build_macos_universal.sh first"
    exit 1
fi

# Remove existing DMG
rm -f "$DMG_PATH" "$TEMP_DMG"

# Calculate size needed (app size + 50MB buffer)
APP_SIZE=$(du -sm "$APP_PATH" | cut -f1)
DMG_SIZE=$((APP_SIZE + 50))

echo "Creating DMG (${DMG_SIZE}MB)..."

# Create temporary DMG
hdiutil create -size "${DMG_SIZE}m" -fs HFS+ -volname "$VOLUME_NAME" "$TEMP_DMG"

# Mount it
MOUNT_POINT=$(hdiutil attach "$TEMP_DMG" | grep "/Volumes/" | awk '{print $3}')
echo "Mounted at: $MOUNT_POINT"

# Copy app
echo "Copying application..."
cp -R "$APP_PATH" "$MOUNT_POINT/"

# Create Applications symlink for drag-and-drop install
ln -s /Applications "$MOUNT_POINT/Applications"

# Set custom icon positions (optional - requires AppleScript)
# This creates a basic layout; for fancy backgrounds, use a tool like create-dmg

# Unmount
echo "Unmounting..."
hdiutil detach "$MOUNT_POINT"

# Convert to compressed DMG
echo "Compressing..."
hdiutil convert "$TEMP_DMG" -format UDZO -o "$DMG_PATH"

# Clean up
rm -f "$TEMP_DMG"

# Sign the DMG if DEVELOPER_ID is set
if [ -n "$DEVELOPER_ID" ]; then
    echo "Signing DMG..."
    codesign --force --sign "$DEVELOPER_ID" "$DMG_PATH"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}DMG Created Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "DMG Location: $DMG_PATH"
echo ""

# Show file info
ls -lh "$DMG_PATH"
