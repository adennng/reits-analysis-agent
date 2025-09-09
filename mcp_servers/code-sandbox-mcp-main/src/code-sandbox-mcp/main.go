package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"

	"github.com/Automata-Labs-team/code-sandbox-mcp/installer"
	"github.com/Automata-Labs-team/code-sandbox-mcp/resources"
	"github.com/Automata-Labs-team/code-sandbox-mcp/tools"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func init() {
	// Check for --install flag
	installFlag := flag.Bool("install", false, "Add this binary to Claude Desktop config")
	noUpdateFlag := flag.Bool("no-update", false, "Disable auto-update check")
	flag.Parse()

	if *installFlag {
		if err := installer.InstallConfig(); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
		os.Exit(0)
	}

	// Check for updates unless disabled
	if !*noUpdateFlag {
		if hasUpdate, downloadURL, err := installer.CheckForUpdate(); err != nil {
			fmt.Fprintf(os.Stderr, "Warning: Failed to check for updates: %v\n", err)
			os.Exit(1)
		} else if hasUpdate {
			fmt.Println("Updating to new version...")
			if err := installer.PerformUpdate(downloadURL); err != nil {
				fmt.Fprintf(os.Stderr, "Warning: Failed to update: %v\n", err)
			}
			fmt.Println("Update complete. Restarting...")
		}
	}
}

func main() {
	port := flag.String("port", "9520", "Port to listen on")
	transport := flag.String("transport", "stdio", "Transport to use (stdio, sse)")
	flag.Parse()
	s := server.NewMCPServer("code-sandbox-mcp", "v1.0.0", server.WithLogging(), server.WithResourceCapabilities(true, true), server.WithPromptCapabilities(false))
	s.AddNotificationHandler("notifications/error", handleNotification)
	// Register tools
	// Initialize a new compute environment for code execution
	initializeTool := mcp.NewTool("sandbox_initialize",
		mcp.WithDescription(
			"Initialize a new compute environment for code execution. \n"+
				"Creates a container based on the specified Docker image or defaults to a slim debian image with Python. \n"+
				"Returns a container_id that can be used with other tools to interact with this environment.",
		),
		mcp.WithString("image",
			mcp.Description("Docker image to use as the base environment (e.g., 'python:3.12-slim-bookworm')"),
			mcp.DefaultString("python:3.12-slim-bookworm"),
		),
	)

	// Copy a directory to the sandboxed filesystem
	copyProjectTool := mcp.NewTool("copy_project",
		mcp.WithDescription(
			"Copy a directory to the sandboxed filesystem. \n"+
				"Transfers a local directory and its contents to the specified container.",
		),
		mcp.WithString("container_id",
			mcp.Required(),
			mcp.Description("ID of the container returned from the initialize call"),
		),
		mcp.WithString("local_src_dir",
			mcp.Required(),
			mcp.Description("Path to a directory in the local file system"),
		),
		mcp.WithString("dest_dir",
			mcp.Description("Path to save the src directory in the sandbox environment, relative to the container working dir"),
		),
	)

	// Write a file to the sandboxed filesystem
	writeFileTool := mcp.NewTool("write_file_sandbox",
		mcp.WithDescription(
			"Write a file to the sandboxed filesystem. \n"+
				"Creates a file with the specified content in the container.",
		),
		mcp.WithString("container_id",
			mcp.Required(),
			mcp.Description("ID of the container returned from the initialize call"),
		),
		mcp.WithString("file_name",
			mcp.Required(),
			mcp.Description("Name of the file to create"),
		),
		mcp.WithString("file_contents",
			mcp.Required(),
			mcp.Description("Contents to write to the file"),
		),
		mcp.WithString("dest_dir",
			mcp.Description("Directory to create the file in, relative to the container working dir"),
			mcp.Description("Default: ${WORKDIR}"),
		),
	)

	// Execute commands in the sandboxed environment
	execTool := mcp.NewTool("sandbox_exec",
		mcp.WithDescription(
			"Execute commands in the sandboxed environment. \n"+
				"Runs one or more shell commands in the specified container and returns the output.",
		),
		mcp.WithString("container_id",
			mcp.Required(),
			mcp.Description("ID of the container returned from the initialize call"),
		),
		mcp.WithArray("commands",
			mcp.Required(),
			mcp.Description("List of command(s) to run in the sandboxed environment"),
			mcp.Description("Example: [\"apt-get update\", \"pip install numpy\", \"python script.py\"]"),
		),
	)

	// Copy a single file to the sandboxed filesystem
	copyFileTool := mcp.NewTool("copy_file",
		mcp.WithDescription(
			"Copy a single file to the sandboxed filesystem. \n"+
				"Transfers a local file to the specified container.",
		),
		mcp.WithString("container_id",
			mcp.Required(),
			mcp.Description("ID of the container returned from the initialize call"),
		),
		mcp.WithString("local_src_file",
			mcp.Required(),
			mcp.Description("Path to a file in the local file system"),
		),
		mcp.WithString("dest_path",
			mcp.Description("Path to save the file in the sandbox environment, relative to the container working dir"),
		),
	)

	// Copy a file from container to local filesystem
	copyFileFromContainerTool := mcp.NewTool("copy_file_from_sandbox",
		mcp.WithDescription(
			"Copy a single file from the sandboxed filesystem to the local filesystem. \n"+
				"Transfers a file from the specified container to the local system.",
		),
		mcp.WithString("container_id",
			mcp.Required(),
			mcp.Description("ID of the container to copy from"),
		),
		mcp.WithString("container_src_path",
			mcp.Required(),
			mcp.Description("Path to the file in the container to copy"),
		),
		mcp.WithString("local_dest_path",
			mcp.Description("Path where to save the file in the local filesystem"),
			mcp.Description("Default: Current directory with the same filename"),
		),
	)

	// Stop and remove a container
	stopContainerTool := mcp.NewTool("sandbox_stop",
		mcp.WithDescription(
			"Stop and remove a running container sandbox. \n"+
				"Gracefully stops the specified container and removes it along with its volumes.",
		),
		mcp.WithString("container_id",
			mcp.Required(),
			mcp.Description("ID of the container to stop and remove"),
		),
	)

	// Register dynamic resource for container logs
	// Dynamic resource example - Container Logs by ID
	containerLogsTemplate := mcp.NewResourceTemplate(
		"containers://{id}/logs",
		"Container Logs",
		mcp.WithTemplateDescription("Returns all container logs from the specified container. Logs are returned as a single text resource."),
		mcp.WithTemplateMIMEType("text/plain"),
		mcp.WithTemplateAnnotations([]mcp.Role{mcp.RoleAssistant, mcp.RoleUser}, 0.5),
	)

	s.AddResourceTemplate(containerLogsTemplate, resources.GetContainerLogs)
	s.AddTool(initializeTool, tools.InitializeEnvironment)
	s.AddTool(copyProjectTool, tools.CopyProject)
	s.AddTool(writeFileTool, tools.WriteFile)
	s.AddTool(execTool, tools.Exec)
	s.AddTool(copyFileTool, tools.CopyFile)
	s.AddTool(copyFileFromContainerTool, tools.CopyFileFromContainer)
	s.AddTool(stopContainerTool, tools.StopContainer)
	switch *transport {
	case "stdio":
		if err := server.ServeStdio(s); err != nil {
			s.SendNotificationToClient(context.Background(), "notifications/error", map[string]interface{}{
				"message": fmt.Sprintf("Failed to start stdio server: %v", err),
			})
		}
	case "sse":
		sseServer := server.NewSSEServer(s)
		if err := sseServer.Start(fmt.Sprintf(":%s", *port)); err != nil {
			s.SendNotificationToClient(context.Background(), "notifications/error", map[string]interface{}{
				"message": fmt.Sprintf("Failed to start SSE server: %v", err),
			})
		}
	default:
		s.SendNotificationToClient(context.Background(), "notifications/error", map[string]interface{}{
			"message": fmt.Sprintf("Invalid transport: %s", *transport),
		})
	}
}

func handleNotification(
	ctx context.Context,
	notification mcp.JSONRPCNotification,
) {
	log.Printf("Received notification from client: %s", notification.Method)
}
