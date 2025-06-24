# Nmstate MCP

## About the Project

A mcp server implementation that works with the MCP SuperAssistant Chrome browser extension to enable any web based LLM chat API to call local nmstate tools using MCP.

### Prerequisites

* `npm`
* `python` (version 3.8+)
* `pip`
* python3-libnmstate

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
uv venv --system-site-packages .venv
```

```bash
uv sync
```

### Run the proxy server
This will also run the nmstate mcp server implementation. See `mcpconfig.json`.

```bash
npx @srbhptl39/mcp-superassistant-proxy@latest --config ./mcpconfig.json
```

### Prerequisites

List any software, libraries, or dependencies that need to be installed before running the project.

* `npm`
* `python` (version 3.8+)
* `pip`
* python3-libnmstate
