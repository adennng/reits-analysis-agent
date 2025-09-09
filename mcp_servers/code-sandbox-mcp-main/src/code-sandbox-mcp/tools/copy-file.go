package tools

import (
	"archive/tar"
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/mark3labs/mcp-go/mcp"
)

// CopyFile copies a single local file to a container's filesystem
func CopyFile(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// Extract parameters
	containerID, ok := request.Params.Arguments["container_id"].(string)
	if !ok || containerID == "" {
		return mcp.NewToolResultText("container_id is required"), nil
	}

	localSrcFile, ok := request.Params.Arguments["local_src_file"].(string)
	if !ok || localSrcFile == "" {
		return mcp.NewToolResultText("local_src_file is required"), nil
	}

	// Clean and validate the source path
	localSrcFile = filepath.Clean(localSrcFile)
	info, err := os.Stat(localSrcFile)
	if err != nil {
		return mcp.NewToolResultText(fmt.Sprintf("Error accessing source file: %v", err)), nil
	}

	if info.IsDir() {
		return mcp.NewToolResultText("local_src_file must be a file, not a directory"), nil
	}

	// Get the destination path (optional parameter)
	destPath, ok := request.Params.Arguments["dest_path"].(string)
	if !ok || destPath == "" {
		// Default: use the name of the source file
		destPath = filepath.Join("/app", filepath.Base(localSrcFile))
	} else {
		// If provided but doesn't start with /, prepend /app/
		if !strings.HasPrefix(destPath, "/") {
			destPath = filepath.Join("/app", destPath)
		}
	}

	// Create destination directory in container if it doesn't exist
	destDir := filepath.Dir(destPath)
	if err := createDirectoryInContainer(ctx, containerID, destDir); err != nil {
		return mcp.NewToolResultText(fmt.Sprintf("Error creating destination directory: %v", err)), nil
	}

	// Copy the file to the container
	if err := copyFileToContainer(ctx, containerID, localSrcFile, destPath); err != nil {
		return mcp.NewToolResultText(fmt.Sprintf("Error copying file to container: %v", err)), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf("Successfully copied %s to %s in container %s", localSrcFile, destPath, containerID)), nil
}

// createDirectoryInContainer creates a directory in the container if it doesn't exist
func createDirectoryInContainer(ctx context.Context, containerID string, dirPath string) error {
	cli, err := client.NewClientWithOpts(
		client.FromEnv,
		client.WithAPIVersionNegotiation(),
	)
	if err != nil {
		return fmt.Errorf("failed to create Docker client: %w", err)
	}
	defer cli.Close()

	createDirCmd := []string{"mkdir", "-p", dirPath}
	exec, err := cli.ContainerExecCreate(ctx, containerID, container.ExecOptions{
		Cmd:          createDirCmd,
		AttachStdout: true,
		AttachStderr: true,
	})
	if err != nil {
		return fmt.Errorf("failed to create exec: %w", err)
	}

	if err := cli.ContainerExecStart(ctx, exec.ID, container.ExecStartOptions{}); err != nil {
		return fmt.Errorf("failed to start exec: %w", err)
	}

	return nil
}

// copyFileToContainer copies a single file to the container
func copyFileToContainer(ctx context.Context, containerID string, srcPath string, destPath string) error {
	cli, err := client.NewClientWithOpts(
		client.FromEnv,
		client.WithAPIVersionNegotiation(),
	)
	if err != nil {
		return fmt.Errorf("failed to create Docker client: %w", err)
	}
	defer cli.Close()

	// Open and stat the source file
	srcFile, err := os.Open(srcPath)
	if err != nil {
		return fmt.Errorf("failed to open source file: %w", err)
	}
	defer srcFile.Close()

	srcInfo, err := srcFile.Stat()
	if err != nil {
		return fmt.Errorf("failed to stat source file: %w", err)
	}

	// Create a buffer to write our archive to
	var buf bytes.Buffer

	// Create a new tar archive
	tw := tar.NewWriter(&buf)

	// Create tar header
	header := &tar.Header{
		Name:    filepath.Base(destPath),
		Size:    srcInfo.Size(),
		Mode:    int64(srcInfo.Mode()),
		ModTime: srcInfo.ModTime(),
	}

	// Write header
	if err := tw.WriteHeader(header); err != nil {
		return fmt.Errorf("failed to write tar header: %w", err)
	}

	// Copy file content to tar archive
	if _, err := io.Copy(tw, srcFile); err != nil {
		return fmt.Errorf("failed to write file content to tar: %w", err)
	}

	// Close tar writer
	if err := tw.Close(); err != nil {
		return fmt.Errorf("failed to close tar writer: %w", err)
	}

	// Copy the tar archive to the container
	err = cli.CopyToContainer(ctx, containerID, filepath.Dir(destPath), &buf, container.CopyToContainerOptions{})
	if err != nil {
		return fmt.Errorf("failed to copy to container: %w", err)
	}

	return nil
}
