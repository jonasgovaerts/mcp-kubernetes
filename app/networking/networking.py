import logging
from typing import Any, Dict, List, Optional

from kubernetes.client.rest import ApiException
from utils.helpers import calculate_age

logger = logging.getLogger(__name__)


class NetworkingResources:
    def __init__(self, networking_api):
        self.networking_api = networking_api

    def get_ingresses(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of ingress resources, optionally filtered by namespace."""
        try:
            if namespace:
                ingresses = self.networking_api.list_namespaced_ingress(namespace).items  # noqa: E501
            else:
                ingresses = self.networking_api.list_ingress_for_all_namespaces().items  # noqa: E501

            result = []
            for ing in ingresses:
                rules = []
                if ing.spec and ing.spec.rules:
                    for rule in ing.spec.rules:
                        host = rule.host if rule.host else "*"
                        paths = [path.path for path in rule.http.paths] if rule.http and rule.http.paths else []
                        # noqa: E501
                        rules.append({"host": host, "paths": paths})

                result.append(
                    {
                        "name": ing.metadata.name,
                        "namespace": ing.metadata.namespace,
                        "rules": rules,
                        "age": calculate_age(ing.metadata.creation_timestamp),
                    }
                )

            return result
        except ApiException as e:
            logger.error(f"Kubernetes API error in {__name__}: {e.status} - {e.reason}", exc_info=True)
            return {"error": f"API Error: {e.reason}"}
        except Exception as e:
            logger.error(f"Error getting ingresses: {e}", exc_info=True)
            return []
