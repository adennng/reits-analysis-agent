package tools

import (
	"context"
	"fmt"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/mark3labs/mcp-go/mcp"
)

// InitializeEnvironment creates a new container for code execution
func InitializeEnvironment(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// Get the requested Docker image or use default
	image, ok := request.Params.Arguments["image"].(string)
	if !ok || image == "" {
		// Default to a slim debian image with Python pre-installed
		image = "python:3.12-slim-bookworm"
	}

	// Create and start the container
	containerId, err := createContainer(ctx, image)
	if err != nil {
		return mcp.NewToolResultText(fmt.Sprintf("Error: %v", err)), nil
	}

	return mcp.NewToolResultText(fmt.Sprintf("container_id: %s", containerId)), nil
}

// createContainer creates a new Docker container and returns its ID
func createContainer(ctx context.Context, image string) (string, error) {
	cli, err := client.NewClientWithOpts(
		client.FromEnv,
		client.WithAPIVersionNegotiation(),
	)
	if err != nil {
		return "", fmt.Errorf("failed to create Docker client: %w", err)
	}
	defer cli.Close()

	// Ensure the image exists locally. We intentionally avoid any network pull here
	// to guarantee we only use pre-loaded images (offline or air-gapped environments).
	// If the image is missing, return a clear error so the caller can handle it.
	_, _, err = cli.ImageInspectWithRaw(ctx, image)
	if err != nil {
		return "", fmt.Errorf("docker image %s not found locally. Please build or load it before initializing a sandbox", image)
	}

	// Create container config with a working directory
	config := &container.Config{
		Image:      image,
		WorkingDir: "/app",
		Tty:        true,
		OpenStdin:  true,
		StdinOnce:  false,
		Cmd:        []string{"sleep", "infinity"}, // keep container alive for exec commands
	}

	// Create host config
	hostConfig := &container.HostConfig{
		// Add any resource constraints here if needed
	}

	// Create the container
	resp, err := cli.ContainerCreate(
		ctx,
		config,
		hostConfig,
		nil,
		nil,
		"",
	)
	if err != nil {
		return "", fmt.Errorf("failed to create container: %w", err)
	}

	// Start the container
	if err := cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
		return "", fmt.Errorf("failed to start container: %w", err)
	}

	return resp.ID, nil
}
