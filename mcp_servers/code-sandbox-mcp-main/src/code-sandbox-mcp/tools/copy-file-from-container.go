package tools

import (
	"archive/tar"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/docker/docker/client"
	"github.com/mark3labs/mcp-go/mcp"
)

// CopyFileFromContainer copies a single file from a container's filesystem to the local filesystem
func CopyFileFromContainer(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// Extract parameters
	containerID, ok := request.Params.Arguments["container_id"].(string)
	if !ok || containerID == "" {
		return mcp.NewToolResultText("container_id is required"), nil
	}

	containerSrcPath, ok := request.Params.Arguments["container_src_path"].(string)
	if !ok || containerSrcPath == "" {
		return mcp.NewToolResultText("container_src_path is required"), nil
	}

	// If container path doesn't start with /, prepend /app/
	if !strings.HasPrefix(containerSrcPath, "/") {
		containerSrcPath = filepath.Join("/app", containerSrcPath)
	}

	// Get the local destination path (optional parameter)
	localDestPath, ok := request.Params.Arguments["local_dest_path"].(string)
	if !ok || localDestPath == "" {
		// Default: use the name of the source file in current directory
		localDestPath = filepath.Base(containerSrcPath)
	}

	// Clean and create the destination directory if it doesn't exist
	localDestPath = filepath.Clean(localDestPath)
	if err := os.MkdirAll(filepath.Dir(localDestPath), 0755); err != nil {
		return mcp.NewToolResultText(fmt.Sprintf("Error creating destination directory: %v", err)), nil
	}

	// Copy the file from the container
	if err := copyFileFromContainer(ctx, containerID, containerSrcPath, localDestPath); err != nil {
		return mcp.NewToolResultText(fmt.Sprintf("Error copying file from container: %v", err)), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf("Successfully copied %s from container %s to %s", containerSrcPath, containerID, localDestPath)), nil
}

// copyFileFromContainer copies a single file from the container to the local filesystem
func copyFileFromContainer(ctx context.Context, containerID string, srcPath string, destPath string) error {
	cli, err := client.NewClientWithOpts(
		client.FromEnv,
		client.WithAPIVersionNegotiation(),
	)
	if err != nil {
		return fmt.Errorf("failed to create Docker client: %w", err)
	}
	defer cli.Close()

	// Create reader for the file from container
	reader, stat, err := cli.CopyFromContainer(ctx, containerID, srcPath)
	if err != nil {
		return fmt.Errorf("failed to copy from container: %w", err)
	}
	defer reader.Close()

	// Check if the source is a directory
	if stat.Mode.IsDir() {
		return fmt.Errorf("source path is a directory, only files are supported")
	}

	// Create tar reader since Docker sends files in tar format
	tr := tar.NewReader(reader)

	// Read the first (and should be only) file from the archive
	header, err := tr.Next()
	if err != nil {
		return fmt.Errorf("failed to read tar header: %w", err)
	}

	// Verify it's a regular file
	if header.Typeflag != tar.TypeReg {
		return fmt.Errorf("source is not a regular file")
	}

	// Create the destination file
	destFile, err := os.Create(destPath)
	if err != nil {
		return fmt.Errorf("failed to create destination file: %w", err)
	}
	defer destFile.Close()

	// Copy the content
	_, err = io.Copy(destFile, tr)
	if err != nil {
		return fmt.Errorf("failed to write file content: %w", err)
	}

	// Set file permissions from tar header
	if err := os.Chmod(destPath, os.FileMode(header.Mode)); err != nil {
		return fmt.Errorf("failed to set file permissions: %w", err)
	}

	return nil
}
