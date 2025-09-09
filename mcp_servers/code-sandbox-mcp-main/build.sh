#!/bin/bash

# Default values
VERSION="dev"
RELEASE=false

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --release) 
            RELEASE=true
            # If no version specified, use git tag or commit hash
            if [ "$VERSION" = "dev" ]; then
                if [ -d .git ]; then
                    VERSION=$(git describe --tags 2>/dev/null || git rev-parse --short HEAD)
                fi
            fi
            ;;
        --version) 
            VERSION="$2"
            shift 
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Create bin directory if it doesn't exist
mkdir -p bin

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Build mode banner
if [ "$RELEASE" = true ]; then
    echo -e "${BLUE}Building in RELEASE mode (version: ${VERSION})${NC}"
else
    echo -e "${BLUE}Building in DEVELOPMENT mode${NC}"
fi

# Build flags for optimization
BUILDFLAGS="-trimpath"  # Remove file system paths from binary

# Set up ldflags
LDFLAGS="-s -w"  # Strip debug information and symbol tables
if [ "$RELEASE" = true ]; then
    # Add version information for release builds
    LDFLAGS="$LDFLAGS -X 'main.Version=$VERSION' -X 'main.BuildMode=release'"
else
    LDFLAGS="$LDFLAGS -X 'main.BuildMode=development'"
fi

# Function to build for a specific platform
build_for_platform() {
    local GOOS=$1
    local GOARCH=$2
    local EXTENSION=$3
    local OUTPUT="$(pwd)/bin/code-sandbox-mcp-${GOOS}-${GOARCH}${EXTENSION}"
    
    if [ "$RELEASE" = true ]; then
        OUTPUT="$(pwd)/bin/code-sandbox-mcp-${GOOS}-${GOARCH}${EXTENSION}"
    fi

    echo -e "${GREEN}Building for ${GOOS}/${GOARCH}...${NC}"
    pushd src/code-sandbox-mcp
    GOOS=$GOOS GOARCH=$GOARCH go build -ldflags="${LDFLAGS}" ${BUILDFLAGS} -o "$OUTPUT" .
    
    if [ $? -eq 0 ]; then
        popd
        echo -e "${GREEN}✓ Successfully built:${NC} $OUTPUT"
        # Create symlink for native platform
        if [ "$GOOS" = "$(go env GOOS)" ] && [ "$GOARCH" = "$(go env GOARCH)" ]; then
            local SYMLINK="bin/code-sandbox-mcp${EXTENSION}"
            ln -sf "$(basename $OUTPUT)" "$SYMLINK"
            echo -e "${GREEN}✓ Created symlink:${NC} $SYMLINK -> $OUTPUT"
        fi
    else
        popd
        echo -e "${RED}✗ Failed to build for ${GOOS}/${GOARCH}${NC}"
        return 1
    fi
}

# Clean previous builds
echo -e "${GREEN}Cleaning previous builds...${NC}"
rm -f bin/code-sandbox-mcp*

# Build for Linux
build_for_platform linux amd64 ""
build_for_platform linux arm64 ""

# Build for macOS
build_for_platform darwin amd64 ""
build_for_platform darwin arm64 ""

# Build for Windows
build_for_platform windows amd64 ".exe"
build_for_platform windows arm64 ".exe"

echo -e "\n${GREEN}Build process completed!${NC}" 