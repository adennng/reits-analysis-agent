// Import the @automatalabs/mcp-server-playwright package
import * as mcp from "@automatalabs/mcp-server-playwright/dist/index.js";

console.log(JSON.stringify(mcp.Tools, ["name", "description"], 2));
