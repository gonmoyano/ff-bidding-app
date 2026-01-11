#!/bin/bash
#
# Build FF Package Manager as a Universal Binary for macOS
# Creates an app that runs natively on both Intel (x86_64) and Apple Silicon (arm64)
#
# IMPORTANT: Creating a true universal binary requires:
#   Option A: Build on Apple Silicon with Rosetta and lipo merge
#   Option B: Build on both architectures and merge with lipo
#   Option C: Use GitHub Actions with matrix builds
#
# This script implements Option A (recommended for local development)
#
# Requirements:
#   - macOS 11.0+ on Apple Silicon (M1/M2/M3)
#   - Python 3.9+ installed for both arm64 and x86_64
#   - pip install -r requirements-macos.txt (in both Python environments)
#
# Usage:
#   ./scripts/build_macos_universal.sh
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

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FF Package Manager - Universal Build${NC}"
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

# Clean previous builds
echo -e "${YELLOW}Cleaning previous build artifacts...${NC}"
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$UNIVERSAL_DIR"

# Function to build for a specific architecture
build_for_arch() {
    local arch=$1
    local arch_build_dir="$BUILD_DIR/$arch"
    local arch_dist_dir="$DIST_DIR/$arch"

    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Building for $arch...${NC}"
    echo -e "${BLUE}========================================${NC}"

    mkdir -p "$arch_build_dir" "$arch_dist_dir"

    cd "$PROJECT_ROOT"

    if [ "$arch" = "x86_64" ] && [ "$NATIVE_ARCH" = "arm64" ]; then
        # Use Rosetta to run x86_64 Python on Apple Silicon
        echo -e "${YELLOW}Using Rosetta for x86_64 build...${NC}"
        arch -x86_64 python3 -m PyInstaller \
            --noconfirm \
            --clean \
            --workpath "$arch_build_dir" \
            --distpath "$arch_dist_dir" \
            "$PROJECT_ROOT/ff_bidding_app.spec"
    elif [ "$arch" = "arm64" ] && [ "$NATIVE_ARCH" = "x86_64" ]; then
        echo -e "${RED}Cannot build arm64 on x86_64 Mac. Use GitHub Actions or an Apple Silicon Mac.${NC}"
        return 1
    else
        # Native build
        python3 -m PyInstaller \
            --noconfirm \
            --clean \
            --workpath "$arch_build_dir" \
            --distpath "$arch_dist_dir" \
            "$PROJECT_ROOT/ff_bidding_app.spec"
    fi

    echo -e "${GREEN}$arch build complete.${NC}"
}

# Function to merge binaries into universal binary
create_universal_binary() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Creating Universal Binary...${NC}"
    echo -e "${BLUE}========================================${NC}"

    local arm64_app="$DIST_DIR/arm64/FF Package Manager.app"
    local x86_64_app="$DIST_DIR/x86_64/FF Package Manager.app"
    local universal_app="$UNIVERSAL_DIR/FF Package Manager.app"

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

    # Find all Mach-O binaries and merge them
    echo "Merging Mach-O binaries with lipo..."

    find "$arm64_app/Contents/MacOS" -type f -perm +111 | while read arm64_binary; do
        relative_path="${arm64_binary#$arm64_app/}"
        x86_64_binary="$x86_64_app/$relative_path"
        universal_binary="$universal_app/$relative_path"

        if [ -f "$x86_64_binary" ]; then
            # Check if it's a Mach-O binary
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

# Build for both architectures
if [ "$NATIVE_ARCH" = "arm64" ]; then
    # On Apple Silicon, we can build both
    build_for_arch "arm64"
    build_for_arch "x86_64"
    create_universal_binary
elif [ "$NATIVE_ARCH" = "x86_64" ]; then
    # On Intel, we can only build x86_64
    echo -e "${YELLOW}Warning: On Intel Mac, can only build x86_64.${NC}"
    echo -e "${YELLOW}For universal binary, use Apple Silicon Mac or GitHub Actions.${NC}"
    echo ""
    build_for_arch "x86_64"

    # Copy x86_64 as the output (not universal)
    cp -R "$DIST_DIR/x86_64/FF Package Manager.app" "$UNIVERSAL_DIR/"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Application: $UNIVERSAL_DIR/FF Package Manager.app"
echo ""
echo "To verify the architectures:"
echo "  file \"$UNIVERSAL_DIR/FF Package Manager.app/Contents/MacOS/FF Package Manager\""
echo ""
echo "Expected output for universal binary:"
echo "  Mach-O universal binary with 2 architectures: [x86_64:Mach-O 64-bit executable x86_64] [arm64:Mach-O 64-bit executable arm64]"
echo ""

# Verify the build
if [ -f "$UNIVERSAL_DIR/FF Package Manager.app/Contents/MacOS/FF Package Manager" ]; then
    echo -e "${GREEN}Build verification:${NC}"
    file "$UNIVERSAL_DIR/FF Package Manager.app/Contents/MacOS/FF Package Manager"
fi
