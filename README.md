# Kubernetes MCP Server

This is a Kubernetes MCP (Model Control Protocol) server that provides an interface for interacting with Kubernetes clusters through the MCP protocol. It allows you to query and manage Kubernetes resources using MCP-compatible clients.

## Features

- Connects to Kubernetes clusters
- Provides MCP endpoints for cluster management
- Exposes Kubernetes resources through MCP protocol:
  - Cluster status and overview
  - Nodes information
  - Namespaces listing
  - Pods monitoring
  - Deployments, StatefulSets, DaemonSets
  - Jobs and CronJobs
  - Ingress resources
  - Events monitoring
  - Pod logs retrieval
- Dockerized for easy deployment

## Prerequisites

- Python 3.12
- Docker (for containerized deployment)
- Access to a Kubernetes cluster with appropriate permissions
- Kubernetes configuration file (kubeconfig) accessible to the server

## Installation

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd kubernetes-mcp
```

2. Install dependencies:
```bash
pip install -r app/requirements
```

3. Run the server:
```bash
python3 app/kubernetes_mcp_server.py
```

### Docker Deployment

Build and run with Docker:
```bash
docker build -t kubernetes-mcp-server .
docker run -p 8000:8000 kubernetes-mcp-server
```

For running with custom kubeconfig:
```bash
docker run -p 8000:8000 \
  -v /path/to/your/kubeconfig:/kubeconfig \
  -e KUBECONFIG=/kubeconfig \
  kubernetes-mcp-server
```

## Usage

The server will start on port 8000 and provide MCP endpoints for Kubernetes cluster interaction.

### Default Endpoints

Once running, the server exposes the following MCP tools:

- `get_cluster_status` - Get overall cluster status including nodes and namespaces
- `list_nodes` - List all nodes with their status, capacity, and allocatable resources
- `list_namespaces` - List all namespaces with their status and age
- `list_pods` - List pods, optionally filtered by namespace
- `list_deployments` - List deployments, optionally filtered by namespace
- `list_statefulsets` - List stateful sets, optionally filtered by namespace
- `list_daemonsets` - List daemon sets, optionally filtered by namespace
- `list_jobs` - List jobs, optionally filtered by namespace
- `list_cronjobs` - List cron jobs, optionally filtered by namespace
- `list_ingresses` - List ingress resources, optionally filtered by namespace
- `list_events` - List recent events, optionally filtered by namespace
- `get_pod_logs` - Get logs from a specific pod

### Running with Custom Configuration

```bash
python3 app/kubernetes_mcp_server.py --host 0.0.0.0 --port 8000 --kubeconfig /path/to/kubeconfig
```

## Configuration

The server can be configured through:
1. Command-line arguments:
   - `--host`: Host to bind to (default: 0.0.0.0)
   - `--port`: Port to listen on (default: 8000)
   - `--kubeconfig`: Path to kubeconfig file

2. Environment variables:
   - `KUBECONFIG`: Path to kubeconfig file
   - `MCP_SERVER_HOST`: Host to bind to
   - `MCP_SERVER_PORT`: Port to listen on

## MCP Client Integration

This server is designed to work with MCP-compatible clients. The tools exposed by this server can be used in an MCP client configuration like:

```json
{
  "tools": [
    {
      "name": "get_cluster_status",
      "description": "Get overall cluster status including nodes and namespaces"
    },
    {
      "name": "list_nodes",
      "description": "List all nodes with their status, capacity, and allocatable resources"
    }
  ]
}
```

## Development

To contribute:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests if applicable
5. Submit a pull request

## Security Considerations

- The server runs as a non-root user in the Docker container for security
- Access to Kubernetes cluster is controlled by the kubeconfig file permissions
- The server should be protected by appropriate network security measures

## License

This project is licensed under the MIT License.