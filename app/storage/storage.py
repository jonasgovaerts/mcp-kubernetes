from typing import Optional, List, Dict, Any
import logging

from utils.helpers import calculate_age

logger = logging.getLogger(__name__)


class StorageResources:
    def __init__(self, core_api):
        self.core_api = core_api

    def get_persistent_volumes(self) -> List[Dict[str, Any]]:
        """Get list of all persistent volumes with their status and capacity."""
        try:
            logger.info("Fetching persistent volumes...")
            pvs = self.core_api.list_persistent_volume().items
            logger.info(f"Found {len(pvs)} persistent volumes")

            result = []
            for pv in pvs:
                storage_class = pv.spec.storage_class_name if pv.spec else "default"
                capacity = pv.spec.capacity.get("storage", "Unknown") if pv.spec and pv.spec.capacity else "Unknown"
                # noqa: E501

                logger.debug(
                    f"PV {pv.metadata.name}: status={pv.status.phase if pv.status else 'Pending'}, capacity={capacity}")

                result.append({
                    "name": pv.metadata.name,
                    "status": pv.status.phase if pv.status else "Pending",
                    "capacity": capacity,
                    "storage_class": storage_class,
                    "access_modes": pv.spec.access_modes if pv.spec and pv.spec.access_modes else [],  # noqa: E501
                    "age": calculate_age(pv.metadata.creation_timestamp),
                    "reclaim_policy": pv.spec.persistent_volume_reclaim_policy if pv.spec else "Retain"  # noqa: E501
                })

            logger.info(f"Successfully retrieved {len(result)} persistent volumes")
            return sorted(result, key=lambda x: x["name"])
        except Exception as e:
            logger.error(f"Error getting persistent volumes: {e}", exc_info=True)
            return []

    def get_persistent_volume_claims(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:  # noqa: E501
        """Get list of persistent volume claims with their status and usage."""
        try:
            target = f"namespace={namespace}" if namespace else "all namespaces"
            logger.info(f"Fetching persistent volume claims for {target}...")

            if namespace:
                pvcs = self.core_api.list_namespaced_persistent_volume_claim(namespace).items  # noqa: E501
            else:
                pvcs = self.core_api.list_persistent_volume_claim_for_all_namespaces().items  # noqa: E501

            logger.info(f"Found {len(pvcs)} persistent volume claims")

            result = []
            for pvc in pvcs:
                status = "Bound" if pvc.status and pvc.status.phase == "Bound" else pvc.status.phase if pvc.status else "Pending"  # noqa: E501

                request_size = pvc.spec.resources.requests.get("storage",
                                                               "Unknown") if pvc.spec and pvc.spec.resources and pvc.spec.resources.requests else "Unknown"  # noqa: E501

                used_size = "N/A"
                if pvc.status and hasattr(pvc.status, 'capacity') and pvc.status.capacity:  # noqa: E501
                    used_size = pvc.status.capacity.get("storage", "N/A")

                logger.debug(
                    f"PVC {pvc.metadata.namespace}/{pvc.metadata.name}: status={status}, requested={request_size}")

                result.append({
                    "name": pvc.metadata.name,
                    "namespace": pvc.metadata.namespace,
                    "status": status,
                    "volume": pvc.spec.volume_name if pvc.spec else "N/A",
                    "storage_class": pvc.spec.storage_class_name if pvc.spec else "default",  # noqa: E501
                    "requested_size": request_size,
                    "used_size": used_size,
                    "age": calculate_age(pvc.metadata.creation_timestamp)
                })

            logger.info(f"Successfully retrieved {len(result)} persistent volume claims")
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            logger.error(f"Error getting persistent volume claims: {e}", exc_info=True)
            return []