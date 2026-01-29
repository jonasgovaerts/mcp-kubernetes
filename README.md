# Kubernetes MCP Agent

A FastMCP-based agent that provides comprehensive Kubernetes cluster inspection capabilities, allowing AI assistants to query cluster status, resources, and logs.

## Features

### Cluster Monitoring
- Get overall cluster health status
- List all nodes with their status and resource utilization
- List all namespaces in the cluster

### Resource Management
- List pods (with optional namespace filtering)
- List deployments (with optional namespace filtering)
- List stateful sets (with optional namespace filtering)
- List daemon sets (with optional namespace filtering)
- List jobs (with optional namespace filtering)
- List cron jobs (with optional namespace filtering)
- List ingress resources (with optional namespace filtering)
- List persistent volumes with their status, capacity, and storage class
- List persistent volume claims with their status, requested size, and used storage (optionally filtered by namespace)
- List pod disruption budgets (with optional namespace filtering)
- List network attachment definitions (with optional namespace filtering)

### Event & Log Management
- List recent cluster events and warnings
- Retrieve logs from specific pods with configurable line limits

## Usage

### Basic Agent Setup
```bash
# Start the MCP server
python app/kubernetes_mcp_server.py --host 0.0.0.0 --port 8000
```

### Integration with AI Assistants
Configure your AI assistant to connect to:
```
http://localhost:8000/mcp
```

## Available Tools

1. `get_cluster_status()` - Get overall cluster status
2. `list_nodes()` - List all nodes with their status and resources
3. `list_namespaces()` - List all namespaces
4. `list_pods(namespace)` - List pods (optionally filtered by namespace)
5. `list_deployments(namespace)` - List deployments (optionally filtered by namespace)
6. `list_statefulsets(namespace)` - List stateful sets
7. `list_daemonsets(namespace)` - List daemon sets
8. `list_jobs(namespace)` - List jobs
9. `list_cronjobs(namespace)` - List cron jobs
10. `list_ingresses(namespace)` - List ingress resources
11. `list_events(namespace)` - List recent events
12. `get_pod_logs(pod_name, namespace, tail_lines)` - Get logs from a specific pod
13. `list_persistent_volumes()` - List all persistent volumes with their status, capacity, and storage class
14. `list_persistent_volume_claims(namespace)` - List persistent volume claims with their status, requested size, and used storage (optionally filtered by namespace)
15. `list_pod_disruption_budgets(namespace)` - List pod disruption budgets (optionally filtered by namespace)
16. `list_network_attachment_definitions(namespace)` - List network attachment definitions from the CNI (optionally filtered by namespace)

## Configuration

The agent can be configured using command line arguments:
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to listen on (default: 8000)
- `--kubeconfig`: Path to kubeconfig file

## Security Considerations

- The agent exposes cluster information and logs through an HTTP interface
- Ensure appropriate network security measures are in place
- Use RBAC permissions appropriately for the Kubernetes service account
- Consider using HTTPS in production environments

## Example Usage

```bash
# Start the server
python app/kubernetes_mcp_server.py --host 0.0.0.0 --port 8000

# In another terminal, you can test with curl
curl http://localhost:8000/tools/get_cluster_status
```

## Requirements

- Python 3.7+
- Kubernetes cluster access
- Required Python packages listed in requirements.txt or Pipfile