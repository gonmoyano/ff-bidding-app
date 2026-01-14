#!/bin/bash
#
# Build Fireframe Prodigy for macOS
# This script builds the app for the current architecture
#
# Usage:
#   ./scripts/build_macos.sh              # Build for current architecture
#   ./scripts/build_macos.sh --clean      # Clean build (removes previous build artifacts)
#   ./scripts/build_macos.sh --no-terminal # Build without Terminal launcher
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
echo -e "${GREEN}Fireframe Prodigy - macOS Build${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script must be run on macOS${NC}"
    exit 1
fi

# Parse arguments
CLEAN_BUILD=false
LAUNCH_IN_TERMINAL=1
for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --no-terminal)
            LAUNCH_IN_TERMINAL=0
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
echo "Launch in Terminal: $([ $LAUNCH_IN_TERMINAL -eq 1 ] && echo 'Yes' || echo 'No')"
echo ""

# Build the application
echo -e "${GREEN}Building Fireframe Prodigy...${NC}"
cd "$PROJECT_ROOT"

# Set architecture environment variable
export TARGET_ARCH="$ARCH"
export LAUNCH_IN_TERMINAL="$LAUNCH_IN_TERMINAL"

# Run PyInstaller
python3 -m PyInstaller \
    --noconfirm \
    --clean \
    --workpath "$BUILD_DIR" \
    --distpath "$DIST_DIR" \
    "$PROJECT_ROOT/ff_bidding_app.spec"

# Add Terminal launcher script if enabled
APP_BUNDLE="$DIST_DIR/Fireframe Prodigy.app"
if [ "$LAUNCH_IN_TERMINAL" -eq 1 ] && [ -d "$APP_BUNDLE" ]; then
    echo ""
    echo -e "${YELLOW}Adding Terminal launcher...${NC}"

    MACOS_DIR="$APP_BUNDLE/Contents/MacOS"
    LAUNCHER="$MACOS_DIR/Fireframe Prodigy"

    # Create the launcher script
    cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/bin/bash
#
# Fireframe Prodigy Launcher
# Opens Terminal.app with log output visible
# Terminal stays open after app exit
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_EXECUTABLE="$SCRIPT_DIR/FireframeProdigy-bin"
APP_NAME="Fireframe Prodigy"

# Get the app bundle path for nice display
BUNDLE_PATH="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Check if we're already in a terminal
if [ -t 0 ] && [ -t 1 ]; then
    # Already in a terminal, just run the app
    echo "=========================================="
    echo "$APP_NAME - Log Output"
    echo "=========================================="
    echo ""
    "$APP_EXECUTABLE" "$@"
    EXIT_CODE=$?
    echo ""
    echo "=========================================="
    echo "Application exited with code: $EXIT_CODE"
    echo "Press Enter to close this window..."
    echo "=========================================="
    read -r
else
    # Not in a terminal, open Terminal.app and run the app there
    osascript <<EOF
tell application "Terminal"
    activate
    set newWindow to do script "clear && echo '==========================================' && echo '$APP_NAME - Log Output' && echo '==========================================' && echo '' && '$APP_EXECUTABLE' && EXIT_CODE=\$? && echo '' && echo '==========================================' && echo \"Application exited with code: \$EXIT_CODE\" && echo 'Press Enter to close this window...' && echo '==========================================' && read"
    set custom title of front window to "$APP_NAME"
end tell
EOF
fi
LAUNCHER_EOF

    # Make launcher executable
    chmod +x "$LAUNCHER"

    echo -e "${GREEN}Terminal launcher added.${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Application bundle: $DIST_DIR/Fireframe Prodigy.app"
echo "Architecture: $ARCH"
if [ "$LAUNCH_IN_TERMINAL" -eq 1 ]; then
    echo "Terminal output: Enabled (logs visible, stays open after exit)"
fi
echo ""

# Check if app was created
if [ -d "$DIST_DIR/Fireframe Prodigy.app" ]; then
    echo -e "${GREEN}Build successful!${NC}"
    echo ""
    echo "To test the app:"
    echo "  open \"$DIST_DIR/Fireframe Prodigy.app\""
    echo ""
    echo "To verify architecture:"
    EXEC_NAME=$([ $LAUNCH_IN_TERMINAL -eq 1 ] && echo "FireframeProdigy-bin" || echo "Fireframe Prodigy")
    echo "  file \"$DIST_DIR/Fireframe Prodigy.app/Contents/MacOS/$EXEC_NAME\""
else
    echo -e "${RED}Build failed - app bundle not found${NC}"
    exit 1
fi
