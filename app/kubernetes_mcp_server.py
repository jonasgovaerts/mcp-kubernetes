"""
Kubernetes MCP Server - Cluster Inspection Tool

This module provides a FastMCP server for inspecting Kubernetes clusters.
It exposes various tools to query cluster status, resources, and logs.
"""
import argparse
import sys
import logging
from typing import Optional

# Configure logging
from certificates.certificates import CertificateResources
from cni.cni_resources import CniResources
from core.core_resources import CoreResources
from logs.logs import LogResources
from metrics.metrics import MetricsResources
from networking.networking import NetworkingResources
from storage.storage import StorageResources
from workloads.workloads import Workloads

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

try:
    from kubernetes import client, config
except ImportError:
    print("Kubernetes Python client not installed", file=sys.stderr)
    sys.exit(1)

try:
    from fastmcp import FastMCP
except ImportError:
    print("FastMCP not installed", file=sys.stderr)
    sys.exit(1)


class KubernetesMCPServer:
    """Main class for the Kubernetes MCP Server."""

    def __init__(self, kubeconfig_path: Optional[str] = None):
        """Initialize the server with optional kubeconfig path."""
        self.kubeconfig_path = kubeconfig_path
        self.core_api = None
        self.apps_api = None
        self.batch_api = None
        self.custom_objects_api = None
        self.networking_api = None
        self.mcp = FastMCP(name="kubernetes-mcp")

        # Initialize resource managers
        self.core_resources = None
        self.workload_resources = None
        self.networking_resources = None
        self.storage_resources = None
        self.metrics_resources = None
        self.certificate_resources = None
        self.log_resources = None
        self.cni_resources = None

    def initialize(self) -> bool:
        """Initialize the Kubernetes client."""
        try:
            logger.info("Initializing Kubernetes client...")
            if self.kubeconfig_path:
                logger.info(f"Loading kubeconfig from: {self.kubeconfig_path}")
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                logger.info("Loading in-cluster config")
                config.load_incluster_config()

            logger.info("Creating API clients...")
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.batch_api = client.BatchV1Api()
            self.policy_api = client.PolicyV1Api()
            self.custom_objects_api = client.CustomObjectsApi()
            self.networking_api = client.NetworkingV1Api()

            # Initialize resource managers with API clients
            self.core_resources = CoreResources(self.core_api, self.policy_api)
            self.workload_resources = Workloads(self.apps_api, self.batch_api)
            self.networking_resources = NetworkingResources(self.networking_api)
            self.storage_resources = StorageResources(self.core_api)
            self.metrics_resources = MetricsResources(self.custom_objects_api)
            self.certificate_resources = CertificateResources(self.custom_objects_api)
            self.log_resources = LogResources(self.core_api)
            self.cni_resources = CniResources(self.custom_objects_api)

            logger.info("Kubernetes client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}", exc_info=True)
            return False


def register_mcp_tools(server: KubernetesMCPServer):
    """Register all Kubernetes tools with FastMCP."""

    @server.mcp.tool
    def get_cluster_status():
        """Get overall cluster status including nodes and namespaces."""
        return server.core_resources.get_cluster_status()

    @server.mcp.tool
    def list_nodes():
        """List all nodes with their status, capacity, and allocatable resources."""
        return server.core_resources.get_nodes()

    @server.mcp.tool
    def list_namespaces():
        """List all namespaces with their status and age."""
        return server.core_resources.get_namespaces()

    @server.mcp.tool
    def list_pods(namespace: Optional[str] = None):
        """List pods, optionally filtered by namespace."""
        return server.core_resources.get_pods(namespace)

    @server.mcp.tool
    def list_deployments(namespace: Optional[str] = None):
        """List deployments, optionally filtered by namespace."""
        return server.workload_resources.get_deployments(namespace)

    @server.mcp.tool
    def list_statefulsets(namespace: Optional[str] = None):
        """List stateful sets, optionally filtered by namespace."""
        return server.workload_resources.get_statefulsets(namespace)

    @server.mcp.tool
    def list_daemonsets(namespace: Optional[str] = None):
        """List daemon sets, optionally filtered by namespace."""
        return server.workload_resources.get_daemonsets(namespace)

    @server.mcp.tool
    def list_jobs(namespace: Optional[str] = None):
        """List jobs, optionally filtered by namespace."""
        return server.workload_resources.get_jobs(namespace)

    @server.mcp.tool
    def list_cronjobs(namespace: Optional[str] = None):
        """List cron jobs, optionally filtered by namespace."""
        return server.workload_resources.get_cronjobs(namespace)

    @server.mcp.tool
    def list_ingresses(namespace: Optional[str] = None):
        """List ingress resources, optionally filtered by namespace."""
        return server.networking_resources.get_ingresses(namespace)

    @server.mcp.tool
    def list_events(namespace: Optional[str] = None):
        """List recent events, optionally filtered by namespace."""
        return server.core_resources.get_events(namespace)

    @server.mcp.tool
    def get_pod_logs(pod_name: str, namespace: Optional[str] = None, tail_lines: int = 100):
        """Get logs from a specific pod. Optionally specify namespace and number of lines to tail."""
        return server.log_resources.get_pod_logs(pod_name, namespace, tail_lines)

    @server.mcp.tool
    def get_node_metrics():
        """Get CPU and memory usage for all nodes in the cluster (kubectl top nodes)."""
        return server.metrics_resources.get_node_metrics()

    @server.mcp.tool
    def get_pod_metrics(namespace: Optional[str] = None):
        """Get CPU and memory usage for pods, optionally filtered by namespace (kubectl top pods)."""
        return server.metrics_resources.get_pod_metrics(namespace)

    @server.mcp.tool
    def list_persistent_volumes():
        """List all persistent volumes with their status, capacity, and storage class."""
        return server.storage_resources.get_persistent_volumes()

    @server.mcp.tool
    def list_persistent_volume_claims(namespace: Optional[str] = None):
        """List persistent volume claims with their status, requested size, and used storage. Optionally filter by namespace."""
        return server.storage_resources.get_persistent_volume_claims(namespace)

    @server.mcp.tool
    def list_certificates(namespace: Optional[str] = None):
        """List certificates from cert-manager with their status and expiration. Optionally filter by namespace."""
        return server.certificate_resources.get_certificates(namespace)

    @server.mcp.tool
    def list_network_attachment_definitions(namespace: Optional[str] = None):
        """List network attachment definitions from the CNI, optionally filtered by namespace."""
        return server.cni_resources.get_network_attachment_definitions(namespace)

    @server.mcp.tool
    def list_pod_disruption_budgets(namespace: Optional[str] = None):
        """List pod disruption budgets, optionally filtered by namespace."""
        return server.core_resources.get_pod_disruption_budgets(namespace)

    @server.mcp.tool
    def inspect_whereabouts_networking():
        """Inspect Whereabouts CNI for IP address management issues."""
        return server.cni_resources.inspect_whereabouts_networking()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kubernetes MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--kubeconfig", help="Path to kubeconfig file")
    args = parser.parse_args()

    server = KubernetesMCPServer(kubeconfig_path=args.kubeconfig)
    if not server.initialize():
        print("Failed to initialize Kubernetes client", file=sys.stderr)
        sys.exit(1)

    register_mcp_tools(server)
    print(f"\nStarting Kubernetes MCP Server on {args.host}:{args.port}/mcp")
    print("Use this URL in your MCP client configuration:")
    print(f"  http://{args.host}:{args.port}/mcp")
    server.mcp.run(transport="streamable-http", host=args.host, port=args.port)