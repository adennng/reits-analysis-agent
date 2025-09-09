package installer

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// Version information (set by build flags)
var (
	Version   = "dev"         // Version number (from git tag or specified)
	BuildMode = "development" // Build mode (development or release)
)

// checkForUpdate checks GitHub releases for a newer version
func CheckForUpdate() (bool, string, error) {
	resp, err := http.Get("https://api.github.com/repos/Automata-Labs-team/code-sandbox-mcp/releases/latest")
	if err != nil {
		return false, "", fmt.Errorf("failed to check for updates: %w", err)
	}
	defer resp.Body.Close()

	var release struct {
		TagName string `json:"tag_name"`
		Assets  []struct {
			Name               string `json:"name"`
			BrowserDownloadURL string `json:"browser_download_url"`
		} `json:"assets"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return false, "", fmt.Errorf("failed to parse release info: %w", err)
	}

	// Skip update check if we're on development version
	if Version == "dev" {
		return false, "", nil
	}

	// Compare versions (assuming semver format v1.2.3)
	if release.TagName > "v"+Version {
		// Find matching asset for current OS/arch
		suffix := fmt.Sprintf("%s-%s", runtime.GOOS, runtime.GOARCH)
		if runtime.GOOS == "windows" {
			suffix += ".exe"
		}
		for _, asset := range release.Assets {
			if strings.HasSuffix(asset.Name, suffix) {
				return true, asset.BrowserDownloadURL, nil
			}
		}
	}

	return false, "", nil
}

// performUpdate downloads and replaces the current binary and restarts the process
func PerformUpdate(downloadURL string) error {
	// Get current executable path
	execPath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("failed to get executable path: %w", err)
	}

	// Download new version to temporary file
	tmpFile, err := os.CreateTemp("", "code-sandbox-mcp-update-*")
	if err != nil {
		return fmt.Errorf("failed to create temp file: %w", err)
	}
	defer os.Remove(tmpFile.Name())

	resp, err := http.Get(downloadURL)
	if err != nil {
		return fmt.Errorf("failed to download update: %w", err)
	}
	defer resp.Body.Close()

	if _, err := io.Copy(tmpFile, resp.Body); err != nil {
		return fmt.Errorf("failed to write update: %w", err)
	}
	tmpFile.Close()

	// Make temporary file executable
	if runtime.GOOS != "windows" {
		if err := os.Chmod(tmpFile.Name(), 0755); err != nil {
			return fmt.Errorf("failed to make update executable: %w", err)
		}
	}

	// Replace the current executable
	// On Windows, we need to move the current executable first
	if runtime.GOOS == "windows" {
		oldPath := execPath + ".old"
		if err := os.Rename(execPath, oldPath); err != nil {
			return fmt.Errorf("failed to rename current executable: %w", err)
		}
		defer os.Remove(oldPath)
	}

	if err := os.Rename(tmpFile.Name(), execPath); err != nil {
		return fmt.Errorf("failed to replace executable: %w", err)
	}

	// Start the new version and exit the current process
	args := os.Args[1:] // Keep all arguments except the program name
	cmd := exec.Command(execPath, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start new version: %w", err)
	}

	// Exit the current process
	os.Exit(0)
	return nil // Never reached, just for compiler
}