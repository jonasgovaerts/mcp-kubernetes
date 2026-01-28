"""
Kubernetes MCP Server - Cluster Inspection Tool

This module provides a FastMCP server for inspecting Kubernetes clusters.
It exposes various tools to query cluster status, resources, and logs.
"""

import sys
from typing import Optional, List, Dict, Any

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
        self.mcp = FastMCP(name="kubernetes-mcp")

    def initialize(self) -> bool:
        """Initialize the Kubernetes client."""
        try:
            if self.kubeconfig_path:
                config.load_kube_config(config_file=self.kubeconfig_path)
            else:
                config.load_incluster_config()
            
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.batch_api = client.BatchV1Api()
            self.custom_objects_api = client.CustomObjectsApi()
            return True
        except Exception as e:
            print(f"Failed to initialize Kubernetes client: {e}", file=sys.stderr)
            return False

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get overall cluster status."""
        try:
            nodes = self.core_api.list_node().items
            namespaces = self.core_api.list_namespace().items
            
            ready_nodes = sum(1 for node in nodes if self._is_node_ready(node))
            total_nodes = len(nodes)
            
            return {
                "status": "Healthy" if ready_nodes == total_nodes else "Degraded",
                "nodes": {
                    "ready": ready_nodes,
                    "total": total_nodes
                },
                "namespaces": len(namespaces)
            }
        except Exception as e:
            return {"error": str(e)}

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get list of all nodes with their status and resources."""
        try:
            nodes = self.core_api.list_node().items
            result = []
            
            for node in nodes:
                status = "Ready" if self._is_node_ready(node) else "NotReady"
                roles = self._get_node_roles(node)
                
                result.append({
                    "name": node.metadata.name,
                    "status": status,
                    "roles": roles,
                    "age": self._calculate_age(node.metadata.creation_timestamp),
                    "version": node.status.node_info.kubelet_version if node.status.node_info else "Unknown",
                    "internal_ip": self._get_node_address(node, "InternalIP"),
                    "external_ip": self._get_node_address(node, "ExternalIP"),
                    "os_image": node.status.node_info.os_image if node.status.node_info else "Unknown",
                    "kernel_version": node.status.node_info.kernel_version if node.status.node_info else "Unknown"
                })
            
            return result
        except Exception as e:
            print(f"Error getting nodes: {e}", file=sys.stderr)
            return []

    def get_namespaces(self) -> List[Dict[str, Any]]:
        """Get list of all namespaces with their status and age."""
        try:
            namespaces = self.core_api.list_namespace().items
            result = []
            
            for ns in namespaces:
                status = "Active" if ns.status.phase == "Active" else "Terminating"
                
                result.append({
                    "name": ns.metadata.name,
                    "status": status,
                    "age": self._calculate_age(ns.metadata.creation_timestamp)
                })
            
            return sorted(result, key=lambda x: x["name"])
        except Exception as e:
            print(f"Error getting namespaces: {e}", file=sys.stderr)
            return []

    def get_pods(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of pods, optionally filtered by namespace."""
        try:
            if namespace:
                pods = self.core_api.list_namespaced_pod(namespace).items
            else:
                pods = self.core_api.list_pod_for_all_namespaces().items
            
            result = []
            for pod in pods:
                result.append({
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": self._get_pod_status(pod),
                    "age": self._calculate_age(pod.metadata.creation_timestamp),
                    "node": pod.spec.node_name if pod.spec and pod.spec.node_name else "N/A"
                })
            
            return result
        except Exception as e:
            print(f"Error getting pods: {e}", file=sys.stderr)
            return []

    def get_deployments(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of deployments, optionally filtered by namespace."""
        try:
            if namespace:
                deployments = self.apps_api.list_namespaced_deployment(namespace).items
            else:
                deployments = self.apps_api.list_deployment_for_all_namespaces().items
            
            result = []
            for dep in deployments:
                result.append({
                    "name": dep.metadata.name,
                    "namespace": dep.metadata.namespace,
                    "replicas": dep.spec.replicas if dep.spec else 0,
                    "available_replicas": dep.status.available_replicas if dep.status else 0,
                    "desired_replicas": dep.status.replicas if dep.status and dep.status.replicas is not None else 0,  # noqa: E501
                    "age": self._calculate_age(dep.metadata.creation_timestamp),
                    "strategy": dep.spec.strategy.type if dep.spec and dep.spec.strategy else "RollingUpdate"  # noqa: E501
                })
            
            return result
        except Exception as e:
            print(f"Error getting deployments: {e}", file=sys.stderr)
            return []

    def get_statefulsets(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of stateful sets, optionally filtered by namespace."""
        try:
            if namespace:
                statefulsets = self.apps_api.list_namespaced_stateful_set(namespace).items
            else:
                statefulsets = self.apps_api.list_stateful_set_for_all_namespaces().items
            
            result = []
            for ss in statefulsets:
                result.append({
                    "name": ss.metadata.name,
                    "namespace": ss.metadata.namespace,
                    "replicas": ss.spec.replicas if ss.spec else 0,
                    "ready_replicas": ss.status.ready_replicas if ss.status else 0,
                    "age": self._calculate_age(ss.metadata.creation_timestamp)
                })
            
            return result
        except Exception as e:
            print(f"Error getting statefulsets: {e}", file=sys.stderr)
            return []

    def get_daemonsets(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of daemon sets, optionally filtered by namespace."""
        try:
            if namespace:
                daemonsets = self.apps_api.list_namespaced_daemon_set(namespace).items
            else:
                daemonsets = self.apps_api.list_daemon_set_for_all_namespaces().items
            
            result = []
            for ds in daemonsets:
                result.append({
                    "name": ds.metadata.name,
                    "namespace": ds.metadata.namespace,
                    "desired": ds.status.desired_number_scheduled if ds.status else 0,
                    "current": ds.status.current_number_scheduled if ds.status else 0,
                    "ready": ds.status.number_ready if ds.status else 0,
                    "age": self._calculate_age(ds.metadata.creation_timestamp)
                })
            
            return result
        except Exception as e:
            print(f"Error getting daemonsets: {e}", file=sys.stderr)
            return []

    def get_jobs(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of jobs, optionally filtered by namespace."""
        try:
            if namespace:
                jobs = self.batch_api.list_namespaced_job(namespace).items
            else:
                jobs = self.batch_api.list_job_for_all_namespaces().items
            
            result = []
            for job in jobs:
                result.append({
                    "name": job.metadata.name,
                    "namespace": job.metadata.namespace,
                    "completions": job.spec.completions if job.spec else 0,
                    "parallelism": job.spec.parallelism if job.spec else 1,
                    "age": self._calculate_age(job.metadata.creation_timestamp),
                    "status": "Completed" if job.status and job.status.succeeded else "Running"  # noqa: E501
                })
            
            return result
        except Exception as e:
            print(f"Error getting jobs: {e}", file=sys.stderr)
            return []

    def get_cronjobs(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of cron jobs, optionally filtered by namespace."""
        try:
            from kubernetes import client as batchv1beta1
            
            if namespace:
                cronjobs = batchv1beta1.BatchV1beta1Api().list_namespaced_cron_job(namespace).items  # noqa: E501
            else:
                cronjobs = batchv1beta1.BatchV1beta1Api().list_cron_job_for_all_namespaces().items  # noqa: E501
            
            result = []
            for cj in cronjobs:
                result.append({
                    "name": cj.metadata.name,
                    "namespace": cj.metadata.namespace,
                    "schedule": cj.spec.schedule if cj.spec else "N/A",
                    "suspend": cj.spec.suspend if cj.spec else False,
                    "age": self._calculate_age(cj.metadata.creation_timestamp)
                })
            
            return result
        except Exception as e:
            print(f"Error getting cronjobs: {e}", file=sys.stderr)
            return []

    def get_ingresses(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of ingress resources, optionally filtered by namespace."""
        try:
            from kubernetes import client as networkingv1
            
            if namespace:
                ingresses = networkingv1.NetworkingV1Api().list_namespaced_ingress(namespace).items  # noqa: E501
            else:
                ingresses = networkingv1.NetworkingV1Api().list_ingress_for_all_namespaces().items  # noqa: E501
            
            result = []
            for ing in ingresses:
                rules = []
                if ing.spec and ing.spec.rules:
                    for rule in ing.spec.rules:
                        host = rule.host if rule.host else "*"
                        paths = [path.path for path in rule.http.paths] if rule.http and rule.http.paths else []  # noqa: E501
                        rules.append({"host": host, "paths": paths})
                
                result.append({
                    "name": ing.metadata.name,
                    "namespace": ing.metadata.namespace,
                    "rules": rules,
                    "age": self._calculate_age(ing.metadata.creation_timestamp)
                })
            
            return result
        except Exception as e:
            print(f"Error getting ingresses: {e}", file=sys.stderr)
            return []

    def get_events(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered by namespace."""
        try:
            if namespace:
                events = self.core_api.list_namespaced_event(namespace).items
            else:
                events = self.core_api.list_event_for_all_namespaces().items
            
            result = []
            for event in events:
                result.append({
                    "type": event.type,
                    "reason": event.reason if event.reason else "N/A",
                    "message": event.message if event.message else "N/A",
                    "involved_kind": event.involved_object.kind if event.involved_object else "N/A",  # noqa: E501
                    "involved_name": event.involved_object.name if event.involved_object else "N/A",  # noqa: E501
                    "namespace": event.metadata.namespace,
                    "age": self._calculate_age(event.metadata.creation_timestamp)
                })
            
            return sorted(result, key=lambda x: x["age"], reverse=True)[:50]
        except Exception as e:
            print(f"Error getting events: {e}", file=sys.stderr)
            return []

    def get_pod_logs(self, pod_name: str, namespace: Optional[str] = None, tail_lines: int = 100) -> str:  # noqa: E501
        """Get logs from a specific pod."""
        try:
            if not namespace:
                # Try to find the pod in all namespaces
                pods = self.core_api.list_pod_for_all_namespaces().items
                matching_pods = [p for p in pods if p.metadata.name == pod_name]
                
                if len(matching_pods) == 1:
                    namespace = matching_pods[0].metadata.namespace
                elif len(matching_pods) > 1:
                    return f"Error: Multiple pods found with name '{pod_name}'. Please specify a namespace."  # noqa: E501
                else:
                    return f"Error: Pod '{pod_name}' not found in any namespace."
            
            log = self.core_api.read_namespaced_pod_log(
                pod_name,
                namespace,
                tail_lines=tail_lines,
                _preload_content=False
            )
            
            return log.data.decode('utf-8')
        except Exception as e:
            return f"Error getting logs: {str(e)}"

    def _is_node_ready(self, node) -> bool:
        """Check if a node is ready."""
        for condition in node.status.conditions or []:
            if condition.type == "Ready":
                return condition.status == "True"
        return False

    def _get_node_roles(self, node) -> List[str]:
        """Get node roles from labels."""
        label_key = "node-role.kubernetes.io/"
        roles = []
        
        if hasattr(node, 'metadata') and hasattr(node.metadata, 'labels'):
            for key, value in node.metadata.labels.items():
                if key.startswith(label_key):
                    roles.append(value)
        return roles if roles else ["worker"]  # Default to worker if no role label

    def _get_node_address(self, node, address_type: str) -> Optional[str]:
        """Get node address by type."""
        for address in node.status.addresses or []:
            if address.type == address_type:
                return address.address
        return None

    def _get_pod_status(self, pod) -> str:
        """Get detailed pod status."""
        if not pod.status:
            return "Unknown"

        # Check for specific conditions
        if pod.status.phase == "Running":
            if any(
                hasattr(container, 'status') and hasattr(container.status, 'waiting') and 
                container.status.waiting and container.status.waiting.reason == "CrashLoopBackOff"
                for container in (pod.status.container_statuses or [])
            ):
                return "CrashLoopBackOff"
            elif any(
                hasattr(container, 'status') and hasattr(container.status, 'waiting') and 
                container.status.waiting
                for container in (pod.status.container_statuses or [])
            ):
                return "Waiting"

        # Check pod conditions
        for condition in pod.status.conditions or []:
            if condition.type == "Ready" and condition.status == "False":
                return f"NotReady ({condition.reason})"

        return pod.status.phase

    def _calculate_age(self, timestamp) -> str:
        """Calculate age from timestamp."""
        if not timestamp:
            return "Unknown"
        try:
            # Simple age calculation (could be more precise)
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00').replace('+00:00', ''))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            delta = now - dt

            if delta.days > 365:
                return f"{delta.days // 365}y"
            elif delta.days > 30:
                return f"{delta.days // 30}m"
            elif delta.days > 0:
                return f"{delta.days}d"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m"
            else:
                return f"{delta.seconds}s"
        except Exception:
            return "Unknown"

    def _format_timestamp(self, timestamp) -> str:
        """Format timestamp for display."""
        if not timestamp:
            return "N/A"
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00').replace('+00:00', ''))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return timestamp if timestamp else "N/A"

    def get_node_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all nodes in the cluster."""
        try:
            metrics = self.custom_objects_api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes"
            )
            
            result = []
            for metric in metrics.get("items", []):
                result.append({
                    "name": metric["metadata"]["name"],
                    "cpu": metric["usage"]["cpu"],
                    "memory": metric["usage"]["memory"]
                })
            
            return sorted(result, key=lambda x: x["name"])
        except Exception as e:
            print(f"Error getting node metrics: {e}", file=sys.stderr)
            return []

    def get_persistent_volumes(self) -> List[Dict[str, Any]]:
        """Get list of all persistent volumes with their status and capacity."""
        try:
            pvs = self.core_api.list_persistent_volume().items
            
            result = []
            for pv in pvs:
                storage_class = pv.spec.storage_class_name if pv.spec else "default"
                capacity = pv.spec.capacity.get("storage", "Unknown") if pv.spec and pv.spec.capacity else "Unknown"  # noqa: E501
                
                result.append({
                    "name": pv.metadata.name,
                    "status": pv.status.phase if pv.status else "Pending",
                    "capacity": capacity,
                    "storage_class": storage_class,
                    "access_modes": pv.spec.access_modes if pv.spec and pv.spec.access_modes else [],  # noqa: E501
                    "age": self._calculate_age(pv.metadata.creation_timestamp),
                    "reclaim_policy": pv.spec.persistent_volume_reclaim_policy if pv.spec else "Retain"  # noqa: E501
                })
            
            return sorted(result, key=lambda x: x["name"])
        except Exception as e:
            print(f"Error getting persistent volumes: {e}", file=sys.stderr)
            return []

    def get_persistent_volume_claims(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:  # noqa: E501
        """Get list of persistent volume claims with their status and usage."""
        try:
            if namespace:
                pvcs = self.core_api.list_namespaced_persistent_volume_claim(namespace).items  # noqa: E501
            else:
                pvcs = self.core_api.list_persistent_volume_claim_for_all_namespaces().items  # noqa: E501
            
            result = []
            for pvc in pvcs:
                status = "Bound" if pvc.status and pvc.status.phase == "Bound" else pvc.status.phase if pvc.status else "Pending"  # noqa: E501
                
                request_size = pvc.spec.resources.requests.get("storage", "Unknown") if pvc.spec and pvc.spec.resources and pvc.spec.resources.requests else "Unknown"  # noqa: E501
                
                used_size = "N/A"
                if pvc.status and hasattr(pvc.status, 'capacity') and pvc.status.capacity:  # noqa: E501
                    used_size = pvc.status.capacity.get("storage", "N/A")
                
                result.append({
                    "name": pvc.metadata.name,
                    "namespace": pvc.metadata.namespace,
                    "status": status,
                    "volume": pvc.spec.volume_name if pvc.spec else "N/A",
                    "storage_class": pvc.spec.storage_class_name if pvc.spec else "default",  # noqa: E501
                    "requested_size": request_size,
                    "used_size": used_size,
                    "age": self._calculate_age(pvc.metadata.creation_timestamp)
                })
            
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            print(f"Error getting persistent volume claims: {e}", file=sys.stderr)
            return []

    def get_pod_metrics(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get metrics for pods, optionally filtered by namespace."""
        try:
            if namespace:
                metrics = self.custom_objects_api.list_namespaced_custom_object(
                    group="metrics.k8s.io",
                    version="v1beta1",
                    plural="pods",
                    namespace=namespace
                )
            else:
                metrics = self.custom_objects_api.list_cluster_custom_object(
                    group="metrics.k8s.io",
                    version="v1beta1",
                    plural="pods"
                )
            
            result = []
            for metric in metrics.get("items", []):
                containers = []
                for container in metric.get("containers", []):
                    containers.append({
                        "container_name": container["name"],
                        "cpu": container["usage"]["cpu"],
                        "memory": container["usage"]["memory"]
                    })
                
                result.append({
                    "namespace": metric["metadata"]["namespace"],
                    "name": metric["metadata"]["name"],
                    "containers": containers
                })
            
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            print(f"Error getting pod metrics: {e}", file=sys.stderr)
            return []


def register_mcp_tools(server):
    """Register all Kubernetes tools with FastMCP."""

    @server.mcp.tool
    def get_cluster_status():
        """Get overall cluster status including nodes and namespaces."""
        return server.get_cluster_status()

    @server.mcp.tool
    def list_nodes():
        """List all nodes with their status, capacity, and allocatable resources."""
        return server.get_nodes()

    @server.mcp.tool
    def list_namespaces():
        """List all namespaces with their status and age."""
        return server.get_namespaces()

    @server.mcp.tool
    def list_pods(namespace: Optional[str] = None):
        """List pods, optionally filtered by namespace."""
        return server.get_pods(namespace)

    @server.mcp.tool
    def list_deployments(namespace: Optional[str] = None):
        """List deployments, optionally filtered by namespace."""
        return server.get_deployments(namespace)

    @server.mcp.tool
    def list_statefulsets(namespace: Optional[str] = None):
        """List stateful sets, optionally filtered by namespace."""
        return server.get_statefulsets(namespace)

    @server.mcp.tool
    def list_daemonsets(namespace: Optional[str] = None):
        """List daemon sets, optionally filtered by namespace."""
        return server.get_daemonsets(namespace)

    @server.mcp.tool
    def list_jobs(namespace: Optional[str] = None):
        """List jobs, optionally filtered by namespace."""
        return server.get_jobs(namespace)

    @server.mcp.tool
    def list_cronjobs(namespace: Optional[str] = None):
        """List cron jobs, optionally filtered by namespace."""
        return server.get_cronjobs(namespace)

    @server.mcp.tool
    def list_ingresses(namespace: Optional[str] = None):
        """List ingress resources, optionally filtered by namespace."""
        return server.get_ingresses(namespace)

    @server.mcp.tool
    def list_events(namespace: Optional[str] = None):
        """List recent events, optionally filtered by namespace."""
        return server.get_events(namespace)

    @server.mcp.tool
    def get_pod_logs(pod_name: str, namespace: Optional[str] = None, tail_lines: int = 100):
        """Get logs from a specific pod. Optionally specify namespace and number of lines to tail."""
        return server.get_pod_logs(pod_name, namespace, tail_lines)

    @server.mcp.tool
    def get_node_metrics():
        """Get CPU and memory usage for all nodes in the cluster (kubectl top nodes)."""
        return server.get_node_metrics()

    @server.mcp.tool
    def get_pod_metrics(namespace: Optional[str] = None):
        """Get CPU and memory usage for pods, optionally filtered by namespace (kubectl top pods)."""
        return server.get_pod_metrics(namespace)

    @server.mcp.tool
    def get_node_metrics():
        """Get CPU and memory usage for all nodes in the cluster (kubectl top nodes)."""
        return server.get_node_metrics()

    @server.mcp.tool
    def get_pod_metrics(namespace: Optional[str] = None):
        """Get CPU and memory usage for pods, optionally filtered by namespace (kubectl top pods)."""
        return server.get_pod_metrics(namespace)

    @server.mcp.tool
    def list_persistent_volumes():
        """List all persistent volumes with their status, capacity, and storage class."""
        return server.get_persistent_volumes()

    @server.mcp.tool
    def list_persistent_volume_claims(namespace: Optional[str] = None):
        """List persistent volume claims with their status, requested size, and used storage. Optionally filter by namespace."""
        return server.get_persistent_volume_claims(namespace)


def main():
    """Main entry point for the Kubernetes MCP server."""
    print("Kubernetes MCP Server - Cluster Inspection Tool")
    print("=" * 50)

    parser = argparse.ArgumentParser(description="Kubernetes MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--kubeconfig", help="Path to kubeconfig file")
    args = parser.parse_args()

    server = KubernetesMCPServer(kubeconfig_path=args.kubeconfig)
    if not server.initialize():
        print("Failed to initialize Kubernetes client", file=sys.stderr)
        sys.exit(1)

    # Get cluster status
    cluster_status = server.get_cluster_status()
    if "error" in cluster_status:
        print(f"Error: {cluster_status['error']}", file=sys.stderr)
        sys.exit(1)

    print("\nCluster Status Summary:")
    print(f"  Status: {cluster_status['status']}")
    print(f"  Nodes: {cluster_status['nodes']['ready']}/{cluster_status['nodes']['total']} Ready")
    print(f"  Namespaces: {cluster_status['namespaces']}")

    # Get and display nodes
    nodes = server.get_nodes()
    print(f"\nNodes ({len(nodes)}):")
    for node in nodes:
        status_icon = "✓" if node["status"] == "Ready" else "✗"
        print(f"  {status_icon} {node['name']} ({node['status']})")

    # Get and display namespaces
    namespaces = server.get_namespaces()
    print(f"\nNamespaces ({len(namespaces)}):")
    for ns in namespaces:
        print(f"  • {ns['name']} ({ns['status']}, {ns['age']})")

    # Get and display pod summary
    pods = server.get_pods()
    if pods:
        running = sum(1 for p in pods if p["phase"] == "Running")
        pending = sum(1 for p in pods if p["phase"] == "Pending")
        failed = sum(1 for p in pods if p["phase"] == "Failed")

        print(f"\nPods ({len(pods)} total):")
        print(f"  • Running: {running}")
        print(f"  • Pending: {pending}")
        print(f"  • Failed: {failed}")

    # Get and display deployment summary
    deployments = server.get_deployments()
    if deployments:
        healthy = sum(1 for d in deployments if d["available_replicas"] == d["desired_replicas"])  # noqa: E501
        print(f"\nDeployments ({len(deployments)}):")
        print(f"  • Healthy: {healthy}")

    # Get recent events
    events = server.get_events()
    if events:
        warnings = [e for e in events if e["type"] == "Warning"]
        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for event in warnings[:5]:  # Show top 5 warnings
                print(f"  • {event['reason']}: {event['message']}")

    print("\nUse specific commands to query detailed information.")


if __name__ == "__main__":
    import argparse

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
    print(f"\nStarting Kubernetes MCP Server on {args.host}:{args.port}")
    print("Use this URL in your MCP client configuration:")
    print(f"  http://{args.host}:{args.port}")
    server.mcp.run(transport="streamable-http", host=args.host, port=args.port)
