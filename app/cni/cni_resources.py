from typing import Optional, List, Dict, Any
import ipaddress
import logging

from utils.helpers import calculate_age, parse_cidr, is_cidr_invalid, is_cidr_exhausted, cidrs_overlap, \
    cidr_contains, is_reservation_stale, calculate_cidr_utilization

logger = logging.getLogger(__name__)


class CniResources:
    def __init__(self, custom_objects_api):
        self.custom_objects_api = custom_objects_api

    def get_network_attachment_definitions(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:  # noqa: E501
        """Get list of network attachment definitions, optionally filtered by namespace."""
        try:
            target = f"namespace={namespace}" if namespace else "all namespaces"
            logger.info(f"Fetching network attachment definitions for {target}...")

            if namespace:
                nads = self.custom_objects_api.list_namespaced_custom_object(
                    group="k8s.cni.cncf.io",
                    version="v1",
                    plural="network-attachment-definitions",
                    namespace=namespace
                )
            else:
                nads = self.custom_objects_api.list_cluster_custom_object(
                    group="k8s.cni.cncf.io",
                    version="v1",
                    plural="network-attachment-definitions"
                )

            result = []
            for nad in nads.get("items", []):
                config = nad.get("spec", {}).get("config", "N/A")

                logger.info(f"NAD {nad['metadata']['namespace']}/{nad['metadata']['name']}")

                result.append({
                    "name": nad["metadata"]["name"],
                    "namespace": nad["metadata"]["namespace"],
                    "config": config,
                    "age": calculate_age(nad["metadata"]["creationTimestamp"])
                })

            logger.info(f"Successfully retrieved {len(result)} network attachment definitions")
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            logger.error(f"Error getting network attachment definitions: {e}", exc_info=True)
            return []

    def get_ippools(self) -> List[Dict[str, Any]]:
        """Get list of all IPPool resources from Whereabouts CNI."""
        try:
            logger.info("Fetching IPPool resources from Whereabouts CNI...")
            ippools = self.custom_objects_api.list_cluster_custom_object(
                group="whereabouts.cni.cncf.io",
                version="v1alpha1",
                plural="ippools"
            )

            result = []
            for ippool in ippools.get("items", []):
                spec = ippool.get("spec", {})
                status = ippool.get("status", {})

                # Parse CIDR ranges
                cidrs = spec.get("cidrs", [])
                parsed_cidrs = []
                for cidr in cidrs:
                    try:
                        parsed_cidrs.append(str(ipaddress.ip_network(cidr)))
                    except ValueError:
                        parsed_cidrs.append(f"Invalid: {cidr}")

                # Get allocation status
                allocated = status.get("allocated", {})

                logger.debug(f"IPPool {ippool['metadata']['name']}: {len(parsed_cidrs)} CIDRs, allocated={allocated}")

                result.append({
                    "name": ippool["metadata"]["name"],
                    "namespace": ippool["metadata"]["namespace"],
                    "cidrs": parsed_cidrs,
                    "gateway": spec.get("gateway", "N/A"),
                    "nat_outgoing": spec.get("natOutgoing", True),
                    "allocated_ips": allocated,
                    "age": calculate_age(ippool["metadata"]["creationTimestamp"]),
                    "labels": ippool["metadata"].get("labels", {})
                })

            logger.info(f"Successfully retrieved {len(result)} IPPools")
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            logger.error(f"Error getting IPPools: {e}", exc_info=True)
            return []

    def get_overlapping_range_ipreservations(self) -> List[Dict[str, Any]]:
        """Get list of all OverlappingRangeIPReservation resources from Whereabouts CNI."""
        try:
            logger.info("Fetching OverlappingRangeIPReservation resources from Whereabouts CNI...")
            reservations = self.custom_objects_api.list_cluster_custom_object(
                group="whereabouts.cni.cncf.io",
                version="v1alpha1",
                plural="overlappingrangeipreservations"
            )

            result = []
            for reservation in reservations.get("items", []):
                spec = reservation.get("spec", {})
                status = reservation.get("status", {})

                # Parse CIDR
                cidr = spec.get("cidr", "N/A")
                try:
                    parsed_cidr = str(ipaddress.ip_network(cidr))
                except ValueError:
                    parsed_cidr = f"Invalid: {cidr}"

                # Get reservation status
                allocated = status.get("allocated", {})

                logger.debug(f"OverlappingRangeIPReservation {reservation['metadata']['name']}: CIDR={parsed_cidr}")

                result.append({
                    "name": reservation["metadata"]["name"],
                    "namespace": reservation["metadata"]["namespace"],
                    "cidr": parsed_cidr,
                    "gateway": spec.get("gateway", "N/A"),
                    "nat_outgoing": spec.get("natOutgoing", True),
                    "allocated_ips": allocated,
                    "age": calculate_age(reservation["metadata"]["creationTimestamp"]),
                    "labels": reservation["metadata"].get("labels", {})
                })

            logger.info(f"Successfully retrieved {len(result)} OverlappingRangeIPReservations")
            return sorted(result, key=lambda x: (x["namespace"], x["name"]))
        except Exception as e:
            logger.error(f"Error getting OverlappingRangeIPReservations: {e}", exc_info=True)
            return []

    def inspect_whereabouts_networking(self) -> Dict[str, Any]:
        """
        Inspect Whereabouts CNI IPPools and OverlappingRangeIPReservations for issues.

        Returns a structured report with:
        - Overlapping CIDRs
        - Exhausted or invalid IPPools
        - Stale or inconsistent overlapping reservations
        - Unprotected overlaps
        - Misconfigurations that could cause duplicate IP allocation or pod networking failures
        """
        try:
            logger.info("Starting Whereabouts CNI networking inspection...")

            # Get all IPPools and reservations
            ippools = self.get_ippools()
            reservations = self.get_overlapping_range_ipreservations()

            logger.info(f"Found {len(ippools)} IPPools and {len(reservations)} OverlappingRangeIPReservations")

            # Initialize report
            report = {
                "summary": {
                    "total_ippools": len(ippools),
                    "total_reservations": len(reservations),
                    "issues_found": 0,
                    "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0}
                },
                "issues": [],
                "ippools": ippools,
                "reservations": reservations
            }

            # Analyze each IPPool for issues
            for ippool in ippools:
                namespace = ippool.get("namespace", "")
                pool_name = ippool.get("name", "")

                # Check for invalid CIDRs
                for cidr in ippool.get("cidrs", []):
                    if is_cidr_invalid(cidr):
                        report["issues"].append({
                            "severity": "high",
                            "type": "invalid_cidr",
                            "resource_type": "IPPool",
                            "resource_name": pool_name,
                            "namespace": namespace,
                            "message": f"IPPool {pool_name} has invalid CIDR: {cidr}",
                            "remediation": f"Fix the CIDR configuration for IPPool {pool_name}. Valid examples: 10.244.0.0/24, 192.168.1.0/25"
                        })

                # Check for exhausted CIDRs
                allocated_ips = ippool.get("allocated_ips", {})
                for cidr in ippool.get("cidrs", []):
                    if not is_cidr_invalid(cidr):
                        parsed_cidr = parse_cidr(cidr)
                        if parsed_cidr and is_cidr_exhausted(parsed_cidr, allocated_ips):
                            utilization = calculate_cidr_utilization(parsed_cidr, allocated_ips)
                            report["issues"].append({
                                "severity": "critical",
                                "type": "exhausted_cidr",
                                "resource_type": "IPPool",
                                "resource_name": pool_name,
                                "namespace": namespace,
                                "message": f"IPPool {pool_name} CIDR {cidr} is exhausted ({utilization['utilization_percent']}% utilized)",
                                "remediation": f"Add more CIDR ranges to IPPool {pool_name} or increase the prefix length (e.g., from /24 to /23)"
                            })

                # Check for overlapping CIDRs within the same IPPool
                cidrs = [c for c in ippool.get("cidrs", []) if not is_cidr_invalid(c)]
                for i in range(len(cidrs)):
                    for j in range(i + 1, len(cidrs)):
                        cidr1 = parse_cidr(cidrs[i])
                        cidr2 = parse_cidr(cidrs[j])
                        if cidr1 and cidr2 and cidrs_overlap(cidr1, cidr2):
                            report["issues"].append({
                                "severity": "high",
                                "type": "overlapping_cidrs_same_pool",
                                "resource_type": "IPPool",
                                "resource_name": pool_name,
                                "namespace": namespace,
                                "message": f"IPPool {pool_name} has overlapping CIDRs: {cidrs[i]} and {cidrs[j]}",
                                "remediation": f"Remove overlapping CIDR {cidrs[j]} from IPPool {pool_name} or adjust the ranges"
                            })

            # Analyze reservations for issues
            for reservation in reservations:
                namespace = reservation.get("namespace", "")
                res_name = reservation.get("name", "")

                # Check for invalid CIDR
                cidr = reservation.get("cidr", "")
                if is_cidr_invalid(cidr):
                    report["issues"].append({
                        "severity": "high",
                        "type": "invalid_reservation_cidr",
                        "resource_type": "OverlappingRangeIPReservation",
                        "resource_name": res_name,
                        "namespace": namespace,
                        "message": f"OverlappingRangeIPReservation {res_name} has invalid CIDR: {cidr}",
                        "remediation": f"Fix the CIDR configuration for OverlappingRangeIPReservation {res_name}"
                    })

                # Check for stale reservations
                if is_reservation_stale(reservation):
                    report["issues"].append({
                        "severity": "medium",
                        "type": "stale_reservation",
                        "resource_type": "OverlappingRangeIPReservation",
                        "resource_name": res_name,
                        "namespace": namespace,
                        "message": f"OverlappingRangeIPReservation {res_name} appears to be stale (age: {reservation.get('age', 'unknown')})",
                        "remediation": f"Investigate and remove stale OverlappingRangeIPReservation {res_name} if no longer needed"
                    })

            # Check for overlaps between IPPools and reservations
            for ippool in ippools:
                namespace = ippool.get("namespace", "")
                pool_name = ippool.get("name", "")

                for reservation in reservations:
                    res_namespace = reservation.get("namespace", "")
                    res_name = reservation.get("name", "")

                    # Skip if not in the same namespace
                    if namespace != res_namespace:
                        continue

                    # Check each CIDR in the IPPool against the reservation's CIDR
                    for cidr in ippool.get("cidrs", []):
                        if is_cidr_invalid(cidr):
                            continue

                        res_cidr = reservation.get("cidr", "")
                        if is_cidr_invalid(res_cidr):
                            continue

                        parsed_pool_cidr = parse_cidr(cidr)
                        parsed_res_cidr = parse_cidr(res_cidr)

                        if parsed_pool_cidr and parsed_res_cidr:
                            # Check for overlap
                            if cidrs_overlap(parsed_pool_cidr, parsed_res_cidr):
                                # Check if the reservation's CIDR is contained within the pool
                                if cidr_contains(parsed_pool_cidr, parsed_res_cidr):
                                    report["issues"].append({
                                        "severity": "low",
                                        "type": "reservation_within_pool",
                                        "resource_type": "OverlappingRangeIPReservation",
                                        "resource_name": res_name,
                                        "namespace": namespace,
                                        "message": f"OverlappingRangeIPReservation {res_name} CIDR {res_cidr} is contained within IPPool {pool_name} CIDR {cidr}",
                                        "remediation": f"Verify that OverlappingRangeIPReservation {res_name} is intentionally contained within IPPool {pool_name}"
                                    })
                                else:
                                    # Unprotected overlap - this is a critical issue
                                    report["issues"].append({
                                        "severity": "critical",
                                        "type": "unprotected_overlap",
                                        "resource_type": "OverlappingRangeIPReservation",
                                        "resource_name": res_name,
                                        "namespace": namespace,
                                        "message": f"OverlappingRangeIPReservation {res_name} CIDR {res_cidr} overlaps with IPPool {pool_name} CIDR {cidr} but is not contained within it",
                                        "remediation": f"Adjust the CIDR ranges so that OverlappingRangeIPReservation {res_name} is either fully contained within IPPool {pool_name} or does not overlap at all"
                                    })

            # Count severity levels
            for issue in report["issues"]:
                severity = issue.get("severity", "low")
                report["summary"]["severity_counts"][severity] += 1

            report["summary"]["issues_found"] = len(report["issues"])

            # Sort issues by severity
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            report["issues"].sort(key=lambda x: severity_order[x.get("severity", "low")])

            logger.info(f"Inspection complete: {len(report['issues'])} issues found")
            return report
        except Exception as e:
            logger.error(f"Error during Whereabouts CNI inspection: {e}", exc_info=True)
            return {"error": str(e), "issues": []}