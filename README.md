# Nmstate MCP

## About the Project

!! WORK IN PROGRESS !!

A mcp server implementation that works with the **MCP SuperAssistant** Chrome browser extension to enable any web based LLM chat API to call local nmstate tools using MCP.
Can also be used with **Claude Desktop and Cursor**.

The vision is to make network management easier with the power of LLMs and MCP.
Please submit issues with ideas :)

The current code is just prototyping. This should probably be re-written with more thoughtful coding.

### Prerequisites

* `npm`
* `python` (version 3.8+)
* `uv`
* `python3-libnmstate`

## Getting Started

Instructions on how to set up and run your project locally.

### Install libnmstate

```bash
sudo dnf install python3-libnmstate uv
```

### Create venv with system site packages to use libnmstate

```bash
uv venv --system-site-packages .venv
```

```bash
source .venv/bin/activate
```

### Download dependencies

```bash
uv sync
```

### Command to run the server

```bash
uv run --directory <path to project directory> main.py

```

or if you are in the project directory:

```bash
uv run main.py

```

You will not need to manually activate the python virtual environment with this command.

### Configure the MCP client

Claude Desktop and Cursor, and potentially others support this "mcpServers" format:

```
{
  "mcpServers": {
    "nmstate-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "<PATH TO YOUR PROJECT>",
        "main.py"
      ]
    },
  }
}
```

### For MCP SuperAssistant: Run the proxy server

This will also run the nmstate mcp server implementation. See `mcpconfig.json`, and please edit it to reflect your directory setup.
UV run documentation: [docs.astral.sh/uv/reference/cli/#uv-run](docs.astral.sh/uv/reference/cli/#uv-run)

```bash
npx @srbhptl39/mcp-superassistant-proxy@latest --config ./mcpconfig.json
```
