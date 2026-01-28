# Kubernetes MCP Agent

This agent provides comprehensive Kubernetes cluster inspection capabilities through the FastMCP framework. It allows AI assistants to query cluster status, resources, and logs.

## Capabilities

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

### Event & Log Management
- List recent cluster events and warnings
- Retrieve logs from specific pods with configurable line limits

## Usage Examples

### Basic Agent Setup
```bash
# Start the MCP server
python app/kubernetes_mcp_server.py --host 0.0.0.0 --port 8000
```

### Integration with AI Assistants
Configure your AI assistant to connect to:
```
http://localhost:8000
```

### Available Tools
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