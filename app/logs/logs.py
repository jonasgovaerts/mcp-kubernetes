import logging
from typing import Optional

from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class LogResources:
    def __init__(self, core_api):
        self.core_api = core_api

    def get_pod_logs(self, pod_name: str, namespace: Optional[str] = None, tail_lines: int = 100) -> str:  # noqa: E501
        """Get logs from a specific pod."""
        try:
            logger.info(f"Fetching logs for pod {pod_name} in namespace {namespace or 'all namespaces'}...")

            if not namespace:
                # Try to find the pod in all namespaces
                logger.info("Searching for pod across all namespaces...")
                pods = self.core_api.list_pod_for_all_namespaces().items
                matching_pods = [p for p in pods if p.metadata.name == pod_name]

                if len(matching_pods) == 1:
                    namespace = matching_pods[0].metadata.namespace
                    logger.info(f"Found pod in namespace: {namespace}")
                elif len(matching_pods) > 1:
                    error_msg = f"Error: Multiple pods found with name '{pod_name}'. Please specify a namespace."
                    logger.error(error_msg)
                    return error_msg
                else:
                    error_msg = f"Error: Pod '{pod_name}' not found in any namespace."
                    logger.error(error_msg)
                    return error_msg

            logger.info(f"Reading {tail_lines} lines from pod logs...")
            log = self.core_api.read_namespaced_pod_log(
                pod_name, namespace, tail_lines=tail_lines, _preload_content=False
            )

            logger.info("Successfully retrieved pod logs")
            return log.data.decode("utf-8")
        except ApiException as e:
            logger.error(f"Kubernetes API error in {__name__}: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            error_msg = f"Error getting logs: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
