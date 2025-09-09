#!/bin/sh
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in a terminal that supports colors
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors)" -ge 8 ]; then
    HAS_COLORS=1
else
    HAS_COLORS=0
    # Reset color variables if colors are not supported
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    if [ "$HAS_COLORS" = "1" ]; then
        printf "%b%s%b\n" "$color" "$message" "$NC"
    else
        printf "%s\n" "$message"
    fi
}

# Detect OS and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

# Convert architecture to our naming scheme
case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    arm64)   ARCH="arm64" ;;
    *)
        print_status "$RED" "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Convert OS to our naming scheme
case "$OS" in
    linux)   OS="linux" ;;
    darwin)  OS="darwin" ;;
    *)
        print_status "$RED" "Unsupported operating system: $OS"
        exit 1
        ;;
esac

# Check if Docker is installed
if ! command -v docker >/dev/null 2>&1; then
    print_status "$RED" "Error: Docker is not installed"
    print_status "$YELLOW" "Please install Docker first:"
    echo "  - For Linux: https://docs.docker.com/engine/install/"
    echo "  - For macOS: https://docs.docker.com/desktop/install/mac/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    print_status "$RED" "Error: Docker daemon is not running"
    print_status "$YELLOW" "Please start Docker and try again"
    exit 1
fi

print_status "$GREEN" "Downloading latest release..."

# Get the latest release URL
LATEST_RELEASE_URL=$(curl -s https://api.github.com/repos/Automata-Labs-team/code-sandbox-mcp/releases/latest | grep "browser_download_url.*code-sandbox-mcp-$OS-$ARCH" | cut -d '"' -f 4)

if [ -z "$LATEST_RELEASE_URL" ]; then
    print_status "$RED" "Error: Could not find release for $OS-$ARCH"
    exit 1
fi

# Create installation directory
INSTALL_DIR="$HOME/.local/share/code-sandbox-mcp"
mkdir -p "$INSTALL_DIR"

# Download to a temporary file first
TEMP_FILE="$INSTALL_DIR/code-sandbox-mcp.tmp"
print_status "$GREEN" "Installing to $INSTALL_DIR/code-sandbox-mcp..."

if ! curl -L "$LATEST_RELEASE_URL" -o "$TEMP_FILE"; then
    print_status "$RED" "Error: Failed to download the binary"
    rm -f "$TEMP_FILE"
    exit 1
fi

chmod +x "$TEMP_FILE"

# Try to stop the existing process if it's running
if [ -f "$INSTALL_DIR/code-sandbox-mcp" ]; then
    pkill -f "$INSTALL_DIR/code-sandbox-mcp" >/dev/null 2>&1 || true
    sleep 1  # Give it a moment to shut down
fi

# Move the temporary file to the final location
if ! mv "$TEMP_FILE" "$INSTALL_DIR/code-sandbox-mcp"; then
    print_status "$RED" "Error: Failed to install the binary. Please ensure no instances are running and try again."
    rm -f "$TEMP_FILE"
    exit 1
fi

# Add to Claude Desktop config
print_status "$GREEN" "Adding to Claude Desktop configuration..."
"$INSTALL_DIR/code-sandbox-mcp" --install

print_status "$GREEN" "Installation complete!"
echo "You can now use code-sandbox-mcp with Claude Desktop or other AI applications." 