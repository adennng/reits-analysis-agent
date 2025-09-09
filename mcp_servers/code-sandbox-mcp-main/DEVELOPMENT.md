# Development Guide 🛠️

This guide is for developers who want to build the project locally or contribute to its development.

## Prerequisites

- Go 1.21 or later
- Docker installed and running
- Git (for version information)
- Make (optional, for build automation)

## Building from Source

1. Clone the repository:
```bash
git clone https://github.com/Automata-Labs-team/code-sandbox-mcp.git
cd code-sandbox-mcp
```

2. Build the project:
```bash
# Development build
./build.sh

# Release build
./build.sh --release

# Release with specific version
./build.sh --release --version v1.0.0
```

The binaries will be available in the `bin` directory.

## Build Options

The `build.sh` script supports several options:

| Option | Description |
|--------|-------------|
| `--release` | Build in release mode with version information |
| `--version <ver>` | Specify a version number (e.g., v1.0.0) |

## Project Structure

```
code-sandbox-mcp/
├── src/
│   └── code-sandbox-mcp/
│       └── main.go       # Main application code
├── bin/                  # Compiled binaries
├── build.sh             # Build script
├── install.sh           # Unix-like systems installer
├── install.ps1          # Windows installer
├── README.md            # User documentation
└── DEVELOPMENT.md       # This file
```

## API Documentation

The project implements the MCP (Machine Code Protocol) server interface for executing code in Docker containers.

### Core Functions

- `runInDocker`: Executes single-file code in a Docker container
- `runProjectInDocker`: Runs project directories in containers
- `RegisterTool`: Registers new tool endpoints
- `NewServer`: Creates a new MCP server instance

### Tool Arguments

#### RunCodeArguments
```go
type RunCodeArguments struct {
    Code       string   `json:"code"`       // The code to run
    Language   Language `json:"language"`   // Programming language
}
```

#### RunProjectArguments
```go
type RunProjectArguments struct {
    ProjectDir string   `json:"project_dir"` // Project directory
    Language   Language `json:"language"`    // Programming language
    Entrypoint string   `json:"entrypoint"` // Command to run the project
    Background bool     `json:"background"`  // Run in background
}
```