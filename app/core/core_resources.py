import logging
from typing import Any, Dict, List, Optional

from kubernetes.client.rest import ApiException
from utils.helpers import calculate_age, get_pod_status, is_node_ready

logger = logging.getLogger(__name__)


class CoreResources:
    def __init__(self, core_api, policy_api):
        self.core_api = core_api
        self.policy_api = policy_api

    def get_cluster_status(self) -> Dict[str, Any]:
        """Get overall cluster status."""
        try:
            logger.info("Fetching cluster status...")
            nodes = self.core_api.list_node().items
            namespaces = self.core_api.list_namespace().items

            ready_nodes = sum(1 for node in nodes if is_node_ready(node))
            total_nodes = len(nodes)

            cluster_status = "Healthy" if ready_nodes == total_nodes else "Degraded"
            logger.info(
                f"Cluster status: {cluster_status} ({ready_nodes}/{total_nodes} nodes ready, {len(namespaces)} "
                f"namespaces)"
            )

            return {
                "status": cluster_status,
                "nodes": {"ready": ready_nodes, "total": total_nodes},
                "namespaces": len(namespaces),
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error getting cluster status: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {"error": "An unexpected server error occurred."}

    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get list of all nodes with their status and resources."""
        try:
            logger.info("Fetching node list...")
            nodes = self.core_api.list_node().items
            logger.info(f"Found {len(nodes)} nodes")

            result = []
            for node in nodes:
                status = "Ready" if is_node_ready(node) else "NotReady"
                roles = self._get_node_roles(node)

                logger.debug(f"Node {node.metadata.name}: status={status}, roles={roles}")

                result.append(
                    {
                        "name": node.metadata.name,
                        "status": status,
                        "roles": roles,
                        "age": calculate_age(node.metadata.creation_timestamp),
                        "version": node.status.node_info.kubelet_version if node.status.node_info else "Unknown",
                        "internal_ip": self._get_node_address(node, "InternalIP"),
                        "external_ip": self._get_node_address(node, "ExternalIP"),
                        "os_image": node.status.node_info.os_image if node.status.node_info else "Unknown",
                        "kernel_version": node.status.node_info.kernel_version if node.status.node_info else "Unknown",
                    }
                )

            logger.info(f"Successfully retrieved {len(result)} nodes")
            return result
        except ApiException as e:
            logger.error(f"Kubernetes API error getting nodes: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {"error": "An unexpected server error occurred."}

    def get_namespaces(self) -> List[Dict[str, Any]]:
        """Get list of all namespaces with their status and age."""
        try:
            logger.info("Fetching namespace list...")
            namespaces = self.core_api.list_namespace().items
            logger.info(f"Found {len(namespaces)} namespaces")

            result = []
            for ns in namespaces:
                # Handle cases where phase attribute might not exist
                phase = getattr(ns.status, "phase", None)
                status = (
                    "Active"
                    if phase == "Active"
                    else ("Terminating" if phase == "Terminating" else str(phase) if phase else "Unknown")
                )
                logger.debug(f"Namespace {ns.metadata.name}: status={status}")

                result.append(
                    {"name": ns.metadata.name, "status": status, "age": calculate_age(ns.metadata.creation_timestamp)}
                )

            logger.info(f"Successfully retrieved {len(result)} namespaces")
            return sorted(result, key=lambda x: x["name"])
        except ApiException as e:
            logger.error(f"Kubernetes API error getting namespaces: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {"error": "An unexpected server error occurred."}

    def get_pods(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of pods, optionally filtered by namespace."""
        try:
            target = f"namespace={namespace}" if namespace else "all namespaces"
            logger.info(f"Fetching pods for {target}...")

            if namespace:
                pods = self.core_api.list_namespaced_pod(namespace).items
            else:
                pods = self.core_api.list_pod_for_all_namespaces().items

            logger.info(f"Found {len(pods)} pods")

            result = []
            for pod in pods:
                status = get_pod_status(pod)
                logger.debug(f"Pod {pod.metadata.namespace}/{pod.metadata.name}: phase={status}")

                result.append(
                    {
                        "name": pod.metadata.name,
                        "namespace": pod.metadata.namespace,
                        "phase": status,
                        "age": calculate_age(pod.metadata.creation_timestamp),
                        "node": pod.spec.node_name if pod.spec and pod.spec.node_name else "N/A",
                    }
                )

            logger.info(f"Successfully retrieved {len(result)} pods")
            return result
        except ApiException as e:
            logger.error(f"Kubernetes API error getting pods: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {"error": "An unexpected server error occurred."}

    def get_events(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered by namespace."""
        try:
            if namespace:
                events = self.core_api.list_namespaced_event(namespace).items
            else:
                events = self.core_api.list_event_for_all_namespaces().items

            result = []
            for event in events:
                result.append(
                    {
                        "type": event.type,
                        "reason": event.reason if event.reason else "N/A",
                        "message": event.message if event.message else "N/A",
                        "involved_kind": event.involved_object.kind if event.involved_object else "N/A",  # noqa: E501
                        "involved_name": event.involved_object.name if event.involved_object else "N/A",  # noqa: E501
                        "namespace": event.metadata.namespace,
                        "age": calculate_age(event.metadata.creation_timestamp),
                    }
                )

            return sorted(result, key=lambda x: x["age"], reverse=True)[:50]
        except ApiException as e:
            logger.error(f"Kubernetes API error getting events: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {"error": "An unexpected server error occurred."}

    def get_pod_disruption_budgets(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of pod disruption budgets, optionally filtered by namespace."""
        try:
            if namespace:
                pdb_list = self.policy_api.list_namespaced_pod_disruption_budget(namespace).items
            else:
                pdb_list = self.policy_api.list_pod_disruption_budget_for_all_namespaces().items

            result = []
            for pdb in pdb_list:
                min_available = pdb.spec.min_available if pdb.spec else None
                max_unavailable = pdb.spec.max_unavailable if pdb.spec else None

                result.append(
                    {
                        "name": pdb.metadata.name,
                        "namespace": pdb.metadata.namespace,
                        "min_available": min_available,
                        "max_unavailable": max_unavailable,
                        "age": calculate_age(pdb.metadata.creation_timestamp),
                        "allowed_disruptions": pdb.status.disruptions_allowed if pdb.status else 0,
                    }
                )

            return result
        except ApiException as e:
            logger.error(f"Kubernetes API error getting pod disruption budgets: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return {"error": "An unexpected server error occurred."}

    def _get_node_roles(self, node) -> List[str]:
        """Get node roles from labels."""
        label_key = "node-role.kubernetes.io/"
        roles = []

        if hasattr(node, "metadata") and hasattr(node.metadata, "labels"):
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
