from typing import Optional, List, Dict, Any
import logging

from utils.helpers import calculate_certificate_expiration, calculate_age

logger = logging.getLogger(__name__)


class CertificateResources:
    def __init__(self, custom_objects_api):
        self.custom_objects_api = custom_objects_api

    def get_certificates(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of certificates from cert-manager, optionally filtered by namespace."""
        try:
            target = f"namespace={namespace}" if namespace else "all namespaces"
            logger.info(f"Fetching certificates for {target}...")

            if namespace:
                certificates = self.custom_objects_api.list_namespaced_custom_object(
                    group="cert-manager.io",
                    version="v1",
                    plural="certificates",
                    namespace=namespace
                )
            else:
                certificates = self.custom_objects_api.list_cluster_custom_object(
                    group="cert-manager.io",
                    version="v1",
                    plural="certificates"
                )

            result = []
            for cert in certificates.get("items", []):
                status = cert.get("status", {})
                conditions = status.get("conditions", [])

                # Get certificate readiness
                ready = False
                reason = "Unknown"
                message = "N/A"
                for condition in conditions:
                    if condition.get("type") == "Ready":
                        ready = condition.get("status") == "True"
                        reason = condition.get("reason", "Unknown")
                        message = condition.get("message", "N/A")
                        break

                # Get certificate expiration
                not_after = status.get("notAfter", "Unknown")
                expiration_days = calculate_certificate_expiration(not_after)

                logger.debug(
                    f"Certificate {cert['metadata']['namespace']}/{cert['metadata']['name']}: ready={ready}, expires={expiration_days}")

                result.append({
                    "name": cert["metadata"]["name"],
                    "namespace": cert["metadata"]["namespace"],
                    "ready": ready,
                    "reason": reason,
                    "message": message,
                    "issuer": cert.get("spec", {}).get("issuerRef", {}).get("name", "N/A"),
                    "secret_name": cert.get("spec", {}).get("secretName", "N/A"),
                    "duration": cert.get("spec", {}).get("duration", "N/A"),
                    "not_after": not_after,
                    "expiration_days": expiration_days,
                    "age": calculate_age(cert["metadata"]["creationTimestamp"])
                })

            logger.info(f"Successfully retrieved {len(result)} certificates")
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            logger.error(f"Error getting certificates: {e}", exc_info=True)
            return []