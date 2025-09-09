package tools

import (
	"context"
	"fmt"
	"strings"

	"github.com/docker/docker/api/types/container"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
)

// Exec executes commands in a container
func Exec(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	// Extract parameters
	containerID, ok := request.Params.Arguments["container_id"].(string)
	if !ok || containerID == "" {
		return mcp.NewToolResultText("container_id is required"), nil
	}

	// Commands can be a single string or an array of strings
	var commands []string
	if cmdsArr, ok := request.Params.Arguments["commands"].([]interface{}); ok {
		// It's an array of commands
		for _, cmd := range cmdsArr {
			if cmdStr, ok := cmd.(string); ok {
				commands = append(commands, cmdStr)
			} else {
				return mcp.NewToolResultText("Each command must be a string"), nil
			}
		}
	} else if cmdStr, ok := request.Params.Arguments["commands"].(string); ok {
		// It's a single command string
		commands = []string{cmdStr}
	} else {
		return mcp.NewToolResultText("commands must be a string or an array of strings"), nil
	}

	if len(commands) == 0 {
		return mcp.NewToolResultText("at least one command is required"), nil
	}

	// Execute each command and collect output
	var outputBuilder strings.Builder
	for i, cmd := range commands {
		// Format the command nicely in the output
		if i > 0 {
			outputBuilder.WriteString("\n\n")
		}
		outputBuilder.WriteString(fmt.Sprintf("$ %s\n", cmd))

		// Execute the command
		stdout, stderr, exitCode, err := executeCommandWithOutput(ctx, containerID, cmd)
		if err != nil {
			return mcp.NewToolResultText(fmt.Sprintf("Error executing command: %v", err)), nil
		}

		// Add the command output to the collector
		if stdout != "" {
			outputBuilder.WriteString(stdout)
			if !strings.HasSuffix(stdout, "\n") {
				outputBuilder.WriteString("\n")
			}
		}
		if stderr != "" {
			outputBuilder.WriteString("Error: ")
			outputBuilder.WriteString(stderr)
			if !strings.HasSuffix(stderr, "\n") {
				outputBuilder.WriteString("\n")
			}
		}

		// If the command failed, add the exit code and stop processing subsequent commands
		if exitCode != 0 {
			outputBuilder.WriteString(fmt.Sprintf("Command exited with code %d\n", exitCode))
			break
		}
	}

	return mcp.NewToolResultText(outputBuilder.String()), nil
}

// executeCommandWithOutput runs a command in a container and returns its stdout, stderr, exit code, and any error
func executeCommandWithOutput(ctx context.Context, containerID string, cmd string) (stdout string, stderr string, exitCode int, err error) {
	cli, err := client.NewClientWithOpts(
		client.FromEnv,
		client.WithAPIVersionNegotiation(),
	)
	if err != nil {
		return "", "", -1, fmt.Errorf("failed to create Docker client: %w", err)
	}
	defer cli.Close()

	// Create the exec configuration
	exec, err := cli.ContainerExecCreate(ctx, containerID, container.ExecOptions{
		Cmd:          []string{"sh", "-c", cmd},
		AttachStdout: true,
		AttachStderr: true,
	})
	if err != nil {
		return "", "", -1, fmt.Errorf("failed to create exec: %w", err)
	}

	// Attach to the exec instance to get output
	resp, err := cli.ContainerExecAttach(ctx, exec.ID, container.ExecAttachOptions{})
	if err != nil {
		return "", "", -1, fmt.Errorf("failed to attach to exec: %w", err)
	}
	defer resp.Close()

	// Read the output
	var stdoutBuf, stderrBuf strings.Builder
	_, err = stdcopy.StdCopy(&stdoutBuf, &stderrBuf, resp.Reader)
	if err != nil {
		return "", "", -1, fmt.Errorf("failed to read command output: %w", err)
	}

	// Get the exit code
	inspect, err := cli.ContainerExecInspect(ctx, exec.ID)
	if err != nil {
		return "", "", -1, fmt.Errorf("failed to inspect exec: %w", err)
	}

	return stdoutBuf.String(), stderrBuf.String(), inspect.ExitCode, nil
}