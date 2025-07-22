# Nmstate MCP

!! WORK IN PROGRESS !!

An MCP server that applies network configuration with nmstate.

The vision is to make network management easier with the power of LLMs and MCP.
Please submit issues with ideas :)

The current code is just prototyping. This should probably be rewritten with more thoughtful coding.

### Prerequisites

* `npm` (Optional: for MCP-Superassistant)
* `python3`
* `uv`
* `python3-libnmstate`

## Getting Started

## From DNF Copr

Instructions on how to set up and run your project from the `dnf` package manager.

### Install from Copr repo: rrajesh/nmstate-mcp

```bash
sudo dnf copr enable rrajesh/nmstate-mcp
sudo dnf install nmstate-mcp
```

### Run the setup script

```bash
nmstate-mcp-setup
```

This corresponds to `setup_cursor.py` for now, and currently only supports `Cursor` IDE.

### Setup inventory.yaml

Setup `~/.nmstate-mcp/inventory.yaml` to include remote hosts that you want to configure.
nmstate-mcp uses `Ansible` for remote host configuration.

## From Source

Instructions on how to set up and run your project from source.

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

You will not need to activate the Python virtual environment with this command manually.

### Configure the MCP client

Claude Desktop and Cursor, and potentially others, support this "mcpServers" format:

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

## Remote Host Configuration

Pre-requisites:
- Ansible.
- SSH.
- For demo purposes, you can give passwordless sudo in the VM or figure out another way to authenticate. You cannot get a password prompt through Cursor.
