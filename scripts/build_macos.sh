#!/bin/bash
#
# Build FF Package Manager for macOS
# This script builds the app for the current architecture
#
# Usage:
#   ./scripts/build_macos.sh              # Build for current architecture
#   ./scripts/build_macos.sh --clean      # Clean build (removes previous build artifacts)
#
# Requirements:
#   - Python 3.9+
#   - pip install -r requirements-macos.txt
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FF Package Manager - macOS Build${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script must be run on macOS${NC}"
    exit 1
fi

# Parse arguments
CLEAN_BUILD=false
for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
    esac
done

# Clean previous builds if requested
if [ "$CLEAN_BUILD" = true ]; then
    echo -e "${YELLOW}Cleaning previous build artifacts...${NC}"
    rm -rf "$BUILD_DIR" "$DIST_DIR"
    echo -e "${GREEN}Clean complete.${NC}"
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}PyInstaller not found. Installing requirements...${NC}"
    pip3 install -r "$PROJECT_ROOT/requirements-macos.txt"
fi

# Detect current architecture
ARCH=$(uname -m)
echo "Building for architecture: $ARCH"
echo ""

# Build the application
echo -e "${GREEN}Building FF Package Manager...${NC}"
cd "$PROJECT_ROOT"

# Set architecture environment variable
export TARGET_ARCH="$ARCH"

# Run PyInstaller
python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --workpath "$BUILD_DIR" \
    --distpath "$DIST_DIR" \
    "$PROJECT_ROOT/ff_bidding_app.spec"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Application bundle: $DIST_DIR/FF Package Manager.app"
echo "Architecture: $ARCH"
echo ""

# Check if app was created
if [ -d "$DIST_DIR/FF Package Manager.app" ]; then
    echo -e "${GREEN}Build successful!${NC}"
    echo ""
    echo "To test the app:"
    echo "  open \"$DIST_DIR/FF Package Manager.app\""
    echo ""
    echo "To verify architecture:"
    echo "  file \"$DIST_DIR/FF Package Manager.app/Contents/MacOS/FF Package Manager\""
else
    echo -e "${RED}Build failed - app bundle not found${NC}"
    exit 1
fi
