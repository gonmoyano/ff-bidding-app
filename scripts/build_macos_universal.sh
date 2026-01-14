#!/bin/bash
#
# Build Fireframe Prodigy as a Universal Binary for macOS
# Creates an app that runs natively on both Intel (x86_64) and Apple Silicon (arm64)
#
# IMPORTANT: Creating a true universal binary requires building for both architectures.
# On Apple Silicon, you need x86_64 Python installed via Rosetta.
#
# Usage:
#   ./scripts/build_macos_universal.sh
#
# Options:
#   --arm64-only    Build only for Apple Silicon (faster, no Rosetta needed)
#   --skip-x86      Same as --arm64-only
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"
UNIVERSAL_DIR="$DIST_DIR/universal"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
ARM64_ONLY=false
for arg in "$@"; do
    case $arg in
        --arm64-only|--skip-x86)
            ARM64_ONLY=true
            shift
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Fireframe Prodigy - Universal Build${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script must be run on macOS${NC}"
    exit 1
fi

# Detect current architecture
NATIVE_ARCH=$(uname -m)
echo "Native architecture: $NATIVE_ARCH"

# Function to check if Rosetta is installed
check_rosetta() {
    if /usr/bin/pgrep -q oahd; then
        return 0
    fi
    if [ -f "/Library/Apple/System/Library/LaunchDaemons/com.apple.oahd.plist" ]; then
        return 0
    fi
    return 1
}

# Function to find x86_64 Python
find_x86_64_python() {
    # Check for Homebrew x86_64 Python
    if [ -f "/usr/local/bin/python3" ]; then
        local py_arch=$(file /usr/local/bin/python3 | grep -o "x86_64" || true)
        if [ -n "$py_arch" ]; then
            echo "/usr/local/bin/python3"
            return 0
        fi
    fi

    # Check for pyenv x86_64 installation
    if command -v pyenv &> /dev/null; then
        local pyenv_root=$(pyenv root)
        for version_dir in "$pyenv_root/versions/"*; do
            if [ -f "$version_dir/bin/python3" ]; then
                local py_arch=$(file "$version_dir/bin/python3" | grep -o "x86_64" || true)
                if [ -n "$py_arch" ]; then
                    echo "$version_dir/bin/python3"
                    return 0
                fi
            fi
        done
    fi

    return 1
}

# Function to install x86_64 Python via Homebrew
install_x86_64_python_instructions() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}x86_64 Python Not Found${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "To build a universal binary, you need x86_64 Python installed."
    echo ""
    echo -e "${BLUE}Option 1: Install via Homebrew (Recommended)${NC}"
    echo ""
    echo "  # Install Rosetta 2 (if not already installed)"
    echo "  softwareupdate --install-rosetta --agree-to-license"
    echo ""
    echo "  # Install x86_64 Homebrew"
    echo "  arch -x86_64 /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo ""
    echo "  # Install x86_64 Python"
    echo "  arch -x86_64 /usr/local/bin/brew install python@3.11"
    echo ""
    echo "  # Install dependencies"
    echo "  arch -x86_64 /usr/local/bin/python3 -m pip install -r requirements-macos.txt"
    echo ""
    echo -e "${BLUE}Option 2: Use pyenv with arch prefix${NC}"
    echo ""
    echo "  arch -x86_64 pyenv install 3.11.0"
    echo ""
    echo -e "${BLUE}Option 3: Build arm64-only (for testing)${NC}"
    echo ""
    echo "  ./scripts/build_macos_universal.sh --arm64-only"
    echo ""
    echo -e "${BLUE}Option 4: Use GitHub Actions (recommended for releases)${NC}"
    echo ""
    echo "  Push a tag like 'v1.0.0' to trigger automated universal builds"
    echo ""
}

# Clean previous builds
echo -e "${YELLOW}Cleaning previous build artifacts...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$UNIVERSAL_DIR"

# Function to build for a specific architecture
build_for_arch() {
    local arch=$1
    local python_cmd=$2
    local arch_build_dir="$BUILD_DIR/$arch"
    local arch_dist_dir="$DIST_DIR/$arch"

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Building for $arch...${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Using Python: $python_cmd"

    mkdir -p "$arch_build_dir" "$arch_dist_dir"

    cd "$PROJECT_ROOT"

    # Set target architecture for PyInstaller
    export TARGET_ARCH=$arch

    $python_cmd -m PyInstaller \
        --noconfirm \
        --clean \
        --workpath "$arch_build_dir" \
        --distpath "$arch_dist_dir" \
        "$PROJECT_ROOT/ff_bidding_app.spec"

    echo -e "${GREEN}$arch build complete.${NC}"
}

# Function to merge binaries into universal binary
create_universal_binary() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Creating Universal Binary...${NC}"
    echo -e "${BLUE}========================================${NC}"

    local arm64_app="$DIST_DIR/arm64/Fireframe Prodigy.app"
    local x86_64_app="$DIST_DIR/x86_64/Fireframe Prodigy.app"
    local universal_app="$UNIVERSAL_DIR/Fireframe Prodigy.app"

    # Check both builds exist
    if [ ! -d "$arm64_app" ]; then
        echo -e "${RED}Error: arm64 build not found at $arm64_app${NC}"
        return 1
    fi

    if [ ! -d "$x86_64_app" ]; then
        echo -e "${RED}Error: x86_64 build not found at $x86_64_app${NC}"
        return 1
    fi

    # Copy arm64 app as base
    echo "Copying arm64 app as base..."
    cp -R "$arm64_app" "$universal_app"

    # Find all Mach-O binaries and merge them (look for FireframeProdigy-bin)
    echo "Merging Mach-O binaries with lipo..."

    # Find all executable files in MacOS directory
    find "$arm64_app/Contents/MacOS" -type f | while read arm64_binary; do
        relative_path="${arm64_binary#$arm64_app/}"
        x86_64_binary="$x86_64_app/$relative_path"
        universal_binary="$universal_app/$relative_path"

        if [ -f "$x86_64_binary" ]; then
            # Check if it's a Mach-O binary (not a shell script)
            if file "$arm64_binary" | grep -q "Mach-O"; then
                echo "  Merging: $relative_path"
                lipo -create "$arm64_binary" "$x86_64_binary" -output "$universal_binary"
            fi
        fi
    done

    # Also merge binaries in Frameworks
    if [ -d "$arm64_app/Contents/Frameworks" ]; then
        find "$arm64_app/Contents/Frameworks" -type f \( -name "*.dylib" -o -name "*.so" \) | while read arm64_binary; do
            relative_path="${arm64_binary#$arm64_app/}"
            x86_64_binary="$x86_64_app/$relative_path"
            universal_binary="$universal_app/$relative_path"

            if [ -f "$x86_64_binary" ]; then
                if file "$arm64_binary" | grep -q "Mach-O"; then
                    echo "  Merging: $relative_path"
                    lipo -create "$arm64_binary" "$x86_64_binary" -output "$universal_binary" 2>/dev/null || true
                fi
            fi
        done
    fi

    echo -e "${GREEN}Universal binary created.${NC}"
}

# Main build logic
if [ "$NATIVE_ARCH" = "arm64" ]; then
    # Building on Apple Silicon

    # Always build arm64 with native Python
    build_for_arch "arm64" "python3"

    if [ "$ARM64_ONLY" = true ]; then
        echo ""
        echo -e "${YELLOW}Skipping x86_64 build (--arm64-only specified)${NC}"
        cp -R "$DIST_DIR/arm64/Fireframe Prodigy.app" "$UNIVERSAL_DIR/"
    else
        # Try to find x86_64 Python
        X86_64_PYTHON=$(find_x86_64_python || true)

        if [ -n "$X86_64_PYTHON" ]; then
            echo ""
            echo -e "${GREEN}Found x86_64 Python: $X86_64_PYTHON${NC}"

            # Verify it has the required packages
            if $X86_64_PYTHON -c "import PyInstaller" 2>/dev/null; then
                build_for_arch "x86_64" "$X86_64_PYTHON"
                create_universal_binary
            else
                echo -e "${YELLOW}x86_64 Python found but PyInstaller not installed.${NC}"
                echo "Install with: $X86_64_PYTHON -m pip install -r requirements-macos.txt"
                echo ""
                echo "Building arm64-only for now..."
                cp -R "$DIST_DIR/arm64/Fireframe Prodigy.app" "$UNIVERSAL_DIR/"
            fi
        else
            # Check if Rosetta is available
            if check_rosetta; then
                install_x86_64_python_instructions
            else
                echo ""
                echo -e "${YELLOW}Rosetta 2 not installed. Install with:${NC}"
                echo "  softwareupdate --install-rosetta --agree-to-license"
                echo ""
                install_x86_64_python_instructions
            fi

            echo ""
            echo -e "${YELLOW}Continuing with arm64-only build...${NC}"
            cp -R "$DIST_DIR/arm64/Fireframe Prodigy.app" "$UNIVERSAL_DIR/"
        fi
    fi

elif [ "$NATIVE_ARCH" = "x86_64" ]; then
    # Building on Intel Mac - can only build x86_64
    echo -e "${YELLOW}Note: On Intel Mac, can only build x86_64.${NC}"
    echo -e "${YELLOW}For universal binary, use Apple Silicon Mac or GitHub Actions.${NC}"
    echo ""
    build_for_arch "x86_64" "python3"

    # Copy x86_64 as the output
    cp -R "$DIST_DIR/x86_64/Fireframe Prodigy.app" "$UNIVERSAL_DIR/"
fi

# Add Terminal launcher script to the app bundle
add_terminal_launcher() {
    local app_bundle="$1"

    echo ""
    echo -e "${YELLOW}Adding Terminal launcher...${NC}"

    local macos_dir="$app_bundle/Contents/MacOS"
    local launcher="$macos_dir/Fireframe Prodigy"

    # Create the launcher script
    cat > "$launcher" << 'LAUNCHER_EOF'
#!/bin/bash
#
# Fireframe Prodigy Launcher
# Opens Terminal.app with log output visible
# Terminal stays open after app exit
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_EXECUTABLE="$SCRIPT_DIR/FireframeProdigy-bin"
APP_NAME="Fireframe Prodigy"

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
    chmod +x "$launcher"

    echo -e "${GREEN}Terminal launcher added.${NC}"
}

# Add the launcher to the final app bundle
if [ -d "$UNIVERSAL_DIR/Fireframe Prodigy.app" ]; then
    add_terminal_launcher "$UNIVERSAL_DIR/Fireframe Prodigy.app"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Application: $UNIVERSAL_DIR/Fireframe Prodigy.app"
echo "Terminal output: Enabled (logs visible, stays open after exit)"
echo ""

# Verify the build
if [ -f "$UNIVERSAL_DIR/Fireframe Prodigy.app/Contents/MacOS/FireframeProdigy-bin" ]; then
    echo -e "${GREEN}Build verification:${NC}"
    file "$UNIVERSAL_DIR/Fireframe Prodigy.app/Contents/MacOS/FireframeProdigy-bin"
    echo ""

    # Check if it's actually universal
    if file "$UNIVERSAL_DIR/Fireframe Prodigy.app/Contents/MacOS/FireframeProdigy-bin" | grep -q "universal binary"; then
        echo -e "${GREEN}✓ Universal binary created successfully!${NC}"
    else
        echo -e "${YELLOW}Note: This is a single-architecture build.${NC}"
        if [ "$ARM64_ONLY" = true ]; then
            echo "  (--arm64-only was specified)"
        else
            echo "  For a true universal binary, set up x86_64 Python (see instructions above)"
            echo "  or use GitHub Actions for automated builds."
        fi
    fi
fi
echo ""
