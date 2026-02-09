import logging
from typing import Any, Dict, List, Optional

from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class MetricsResources:
    def __init__(self, custom_objects_api):
        self.custom_objects_api = custom_objects_api

    def get_node_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all nodes in the cluster."""
        try:
            logger.info("Fetching node metrics...")
            metrics = self.custom_objects_api.list_cluster_custom_object(
                group="metrics.k8s.io", version="v1beta1", plural="nodes"
            )

            result = []
            for metric in metrics.get("items", []):
                logger.debug(
                    f"Node {metric['metadata']['name']}: cpu={metric['usage']['cpu']}, mem={metric['usage']['memory']}"
                )
                result.append(
                    {
                        "name": metric["metadata"]["name"],
                        "cpu": metric["usage"]["cpu"],
                        "memory": metric["usage"]["memory"],
                    }
                )

            logger.info(f"Successfully retrieved metrics for {len(result)} nodes")
            return sorted(result, key=lambda x: x["name"])
        except ApiException as e:
            logger.error(f"Kubernetes API error in {__name__}: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"Error getting node metrics: {e}", exc_info=True)
            return []

    def get_pod_metrics(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get metrics for pods, optionally filtered by namespace."""
        try:
            target = f"namespace={namespace}" if namespace else "all namespaces"
            logger.info(f"Fetching pod metrics for {target}...")

            if namespace:
                metrics = self.custom_objects_api.list_namespaced_custom_object(
                    group="metrics.k8s.io", version="v1beta1", plural="pods", namespace=namespace
                )
            else:
                metrics = self.custom_objects_api.list_cluster_custom_object(
                    group="metrics.k8s.io", version="v1beta1", plural="pods"
                )

            result = []
            for metric in metrics.get("items", []):
                containers = []
                for container in metric.get("containers", []):
                    containers.append(
                        {
                            "container_name": container["name"],
                            "cpu": container["usage"]["cpu"],
                            "memory": container["usage"]["memory"],
                        }
                    )

                logger.debug(
                    f"Pod {metric['metadata']['namespace']}/{metric['metadata']['name']}: {len(containers)} containers"
                )

                result.append(
                    {
                        "namespace": metric["metadata"]["namespace"],
                        "name": metric["metadata"]["name"],
                        "containers": containers,
                    }
                )

            logger.info(f"Successfully retrieved metrics for {len(result)} pods")
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except ApiException as e:
            logger.error(f"Kubernetes API error in {__name__}: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"Error getting pod metrics: {e}", exc_info=True)
            return []
