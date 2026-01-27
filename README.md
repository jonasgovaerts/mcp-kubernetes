# Kubernetes MCP Server

A read-only Kubernetes cluster inspection tool using the Model Context Protocol (MCP) pattern and the official Kubernetes Python client.

## Features

- **Cluster-Level Status**: Version, API server health, node readiness
- **Node Inspection**: Capacity vs allocatable resources, conditions
- **Namespace Management**: List and status
- **Workload Discovery**: Pods, Deployments, StatefulSets, DaemonSets, Jobs, CronJobs
- **Application Health**: Group by namespace/labels, summarize health
- **Events & Diagnostics**: Recent warnings/errors, pod readiness issues

## Safety Constraints

✅ **Read-only operations** - No create/update/delete operations
✅ **RBAC aware** - Gracefully handles permission errors
✅ **No shell execution** - Only uses Kubernetes APIs
✅ **No data fabrication** - Returns only real cluster state

## Installation

### Prerequisites
- Python 3.8+
- pipenv

### Setup

```bash
# Install pipenv if not available
pip install pipenv

# Create and activate virtual environment
pipenv --python 3.x

# Install dependencies
pipenv install
```

## Usage as MCP Server

This server implements the Model Context Protocol (MCP) using FastMCP.

### Running the MCP Server

```bash
# Run the MCP server (stdio transport)
pipenv run python kubernetes_mcp_server.py
```

### Available Tools

The server provides 10 tools for Kubernetes inspection:

1. **get_cluster_status** - Get overall cluster health and status
2. **list_nodes** - List all nodes with capacity and allocatable resources
3. **list_namespaces** - List all namespaces
4. **list_pods** - List pods (with optional namespace filter)
5. **list_deployments** - List deployments (with optional namespace filter)
6. **list_statefulsets** - List stateful sets (with optional namespace filter)
7. **list_daemonsets** - List daemon sets (with optional namespace filter)
8. **list_jobs** - List jobs (with optional namespace filter)
9. **list_cronjobs** - List cron jobs (with optional namespace filter)
10. **list_events** - List recent events (with optional namespace filter)

### MCP Configuration

An `mcp.json` configuration file is provided for integration with MCP clients:

```json
{
  "name": "kubernetes-mcp",
  "description": "Kubernetes cluster inspection tool",
  "version": "0.1.0",
  "server": {
    "type": "stdio",
    "command": "python3",
    "args": ["kubernetes_mcp_server.py"]
  }
}
```

### Using with MCP Clients

You can use this server with any MCP-compatible client (VS Code, Cursor, Windsurf, etc.) by pointing to the `mcp.json` configuration file.

### Testing with FastMCP CLI

```bash
# Install fastmcp-cli
pip install fastmcp-cli

# Run the MCP server and interact with it
fastmcp run kubernetes_mcp_server.py
```

## Legacy Usage (Direct Python API)

The original direct Python API is still available:

```python
from kubernetes_mcp_server import KubernetesMCPServer

server = KubernetesMCPServer()
if server.initialize():
    # Get cluster status
    status = server.get_cluster_status()
    
    # List nodes
    nodes = server.get_nodes()
    
    # List pods in specific namespace
    pods = server.get_pods(namespace="default")
```

## Configuration

The server automatically:
1. Tries to use in-cluster config when running inside Kubernetes
2. Falls back to `~/.kube/config` for local development
3. Handles API version differences gracefully

## Dependencies

- Python 3.8+
- kubernetes >= 25.0.0
- requests
- ujson
- fastmcp (for MCP protocol support)

Managed via Pipenv.

## Development

```bash
# Install dependencies for development
pipenv install --dev

# Run tests
pipenv run python test_connection.py

# Format code
pipenv run black kubernetes_mcp_server.py
```

## License

MIT License - see LICENSE file for details.
