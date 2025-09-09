# Function to check if running in a terminal that supports colors
function Test-ColorSupport {
    # Check if we're in a terminal that supports VirtualTerminalLevel
    $supportsVT = $false
    try {
        $supportsVT = [Console]::IsOutputRedirected -eq $false -and 
                      [Console]::IsErrorRedirected -eq $false -and
                      [Environment]::GetEnvironmentVariable("TERM") -ne $null
    } catch {
        $supportsVT = $false
    }
    return $supportsVT
}

# Function to write colored output
function Write-ColoredMessage {
    param(
        [string]$Message,
        [System.ConsoleColor]$Color = [System.ConsoleColor]::White
    )
    
    if (Test-ColorSupport) {
        $originalColor = [Console]::ForegroundColor
        [Console]::ForegroundColor = $Color
        Write-Host $Message
        [Console]::ForegroundColor = $originalColor
    } else {
        Write-Host $Message
    }
}

# Function to stop running instances
function Stop-RunningInstances {
    param(
        [string]$ProcessName
    )
    
    try {
        $processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
        if ($processes) {
            $processes | ForEach-Object {
                try {
                    $_.Kill()
                    $_.WaitForExit(1000)
                } catch {
                    # Ignore errors if process already exited
                }
            }
            Start-Sleep -Seconds 1  # Give processes time to fully exit
        }
    } catch {
        # Ignore errors if no processes found
    }
}

# Check if Docker is installed
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-ColoredMessage "Error: Docker is not installed" -Color Red
    Write-ColoredMessage "Please install Docker Desktop for Windows:" -Color Yellow
    Write-Host "  https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

# Check if Docker daemon is running
try {
    docker info | Out-Null
} catch {
    Write-ColoredMessage "Error: Docker daemon is not running" -Color Red
    Write-ColoredMessage "Please start Docker Desktop and try again" -Color Yellow
    exit 1
}

Write-ColoredMessage "Downloading latest release..." -Color Green

# Determine architecture
$arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }

# Get the latest release URL
try {
    $apiResponse = Invoke-RestMethod -Uri "https://api.github.com/repos/Automata-Labs-team/code-sandbox-mcp/releases/latest"
    $asset = $apiResponse.assets | Where-Object { $_.name -like "code-sandbox-mcp-windows-$arch.exe" }
} catch {
    Write-ColoredMessage "Error: Failed to fetch latest release information" -Color Red
    Write-Host $_.Exception.Message
    exit 1
}

if (-not $asset) {
    Write-ColoredMessage "Error: Could not find release for windows-$arch" -Color Red
    exit 1
}

# Create installation directory
$installDir = "$env:LOCALAPPDATA\code-sandbox-mcp"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

# Download to a temporary file first
$tempFile = "$installDir\code-sandbox-mcp.tmp"
Write-ColoredMessage "Installing to $installDir\code-sandbox-mcp.exe..." -Color Green

try {
    # Download the binary to temporary file
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tempFile

    # Stop any running instances
    Stop-RunningInstances -ProcessName "code-sandbox-mcp"

    # Try to move the temporary file to the final location
    try {
        Move-Item -Path $tempFile -Destination "$installDir\code-sandbox-mcp.exe" -Force
    } catch {
        Write-ColoredMessage "Error: Failed to install the binary. Please ensure no instances are running and try again." -Color Red
        Remove-Item -Path $tempFile -ErrorAction SilentlyContinue
        exit 1
    }
} catch {
    Write-ColoredMessage "Error: Failed to download or install the binary" -Color Red
    Write-Host $_.Exception.Message
    Remove-Item -Path $tempFile -ErrorAction SilentlyContinue
    exit 1
}

# Add to Claude Desktop config
Write-ColoredMessage "Adding to Claude Desktop configuration..." -Color Green
try {
    & "$installDir\code-sandbox-mcp.exe" --install
} catch {
    Write-ColoredMessage "Error: Failed to configure Claude Desktop" -Color Red
    Write-Host $_.Exception.Message
    exit 1
}

Write-ColoredMessage "Installation complete!" -Color Green
Write-Host "You can now use code-sandbox-mcp with Claude Desktop or other AI applications." 