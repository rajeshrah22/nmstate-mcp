# Project Title

Nmstate MCP

## About the Project

A mcp server implementation that works with the MCP SuperAssistant Chrome browser extension to enable any web based LLM chat API to call local or remote tools using MCP.

### Prerequisites

* `npm`
* `python` (version 3.8+)
* `pip`
* python3-libnmstate

## Getting Started

```bash
sudo dnf install python3-libnmstate uv
```
```bash
source .venv/bin/activate
```

```bash
uv sync
```

```bash
npx @srbhptl39/mcp-superassistant-proxy@latest --config ./mcpconfig.json
```
