package main

import (
	"fmt"
	"os"
	cmd "github.com/docker/cli/cli/command"
)

func main() {
	fmt.Println("Hello, World!")
	os.Exit(0)
	cmd.PrettyPrint("Hello, World!")
}
