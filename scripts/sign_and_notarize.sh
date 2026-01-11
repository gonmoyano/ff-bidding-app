#!/bin/bash
#
# Sign and notarize FF Package Manager for macOS distribution
#
# This script:
#   1. Signs the app with your Developer ID certificate
#   2. Submits to Apple for notarization
#   3. Staples the notarization ticket
#
# Requirements:
#   - Apple Developer account
#   - Developer ID Application certificate installed in Keychain
#   - App-specific password for notarization
#
# Environment variables:
#   DEVELOPER_ID        - Your Developer ID (e.g., "Developer ID Application: Your Name (TEAM_ID)")
#   APPLE_ID            - Your Apple ID email
#   APPLE_TEAM_ID       - Your Apple Developer Team ID
#   NOTARIZATION_PWD    - App-specific password for notarization
#
# Usage:
#   export DEVELOPER_ID="Developer ID Application: Your Company (XXXXXXXXXX)"
#   export APPLE_ID="your@email.com"
#   export APPLE_TEAM_ID="XXXXXXXXXX"
#   export NOTARIZATION_PWD="xxxx-xxxx-xxxx-xxxx"
#   ./scripts/sign_and_notarize.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_PATH="$PROJECT_ROOT/dist/universal/FF Package Manager.app"
ENTITLEMENTS="$PROJECT_ROOT/macos/entitlements.plist"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FF Package Manager - Sign & Notarize${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check required environment variables
if [ -z "$DEVELOPER_ID" ]; then
    echo -e "${RED}Error: DEVELOPER_ID environment variable not set${NC}"
    echo "Example: export DEVELOPER_ID=\"Developer ID Application: Your Company (XXXXXXXXXX)\""
    exit 1
fi

if [ -z "$APPLE_ID" ]; then
    echo -e "${RED}Error: APPLE_ID environment variable not set${NC}"
    exit 1
fi

if [ -z "$APPLE_TEAM_ID" ]; then
    echo -e "${RED}Error: APPLE_TEAM_ID environment variable not set${NC}"
    exit 1
fi

if [ -z "$NOTARIZATION_PWD" ]; then
    echo -e "${RED}Error: NOTARIZATION_PWD environment variable not set${NC}"
    echo "Create an app-specific password at https://appleid.apple.com"
    exit 1
fi

# Check app exists
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Error: App not found at $APP_PATH${NC}"
    echo "Run ./scripts/build_macos_universal.sh first"
    exit 1
fi

# Step 1: Sign all binaries and frameworks
echo -e "${GREEN}Step 1: Signing application...${NC}"

# Sign embedded frameworks and libraries first
find "$APP_PATH/Contents/Frameworks" -type f \( -name "*.dylib" -o -name "*.so" -o -name "*.framework" \) 2>/dev/null | while read lib; do
    echo "  Signing: $lib"
    codesign --force --options runtime --timestamp --sign "$DEVELOPER_ID" "$lib" 2>/dev/null || true
done

# Sign the main executable
echo "  Signing main executable..."
codesign --force --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" \
    --sign "$DEVELOPER_ID" \
    "$APP_PATH"

# Verify signature
echo ""
echo -e "${GREEN}Verifying signature...${NC}"
codesign --verify --verbose=2 "$APP_PATH"

echo ""
echo -e "${GREEN}Step 2: Creating ZIP for notarization...${NC}"
ZIP_PATH="$PROJECT_ROOT/dist/FF_Package_Manager.zip"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
echo "Created: $ZIP_PATH"

echo ""
echo -e "${GREEN}Step 3: Submitting for notarization...${NC}"
echo "This may take several minutes..."

xcrun notarytool submit "$ZIP_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$NOTARIZATION_PWD" \
    --wait

echo ""
echo -e "${GREEN}Step 4: Stapling notarization ticket...${NC}"
xcrun stapler staple "$APP_PATH"

echo ""
echo -e "${GREEN}Step 5: Final verification...${NC}"
spctl --assess --type execute --verbose=2 "$APP_PATH"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Signing and Notarization Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Your app is ready for distribution!"
echo "Location: $APP_PATH"
echo ""
echo "To create a DMG installer, run:"
echo "  ./scripts/create_dmg.sh"
