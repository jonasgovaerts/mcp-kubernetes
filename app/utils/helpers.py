import ipaddress
from typing import Any, Dict, List, Optional


def is_node_ready(node) -> bool:
    """Check if a node is ready."""
    for condition in node.status.conditions or []:
        if condition.type == "Ready":
            return condition.status == "True"
    return False


def get_node_roles(node) -> List[str]:
    """Get node roles from labels."""
    label_key = "node-role.kubernetes.io/"
    roles = []

    if hasattr(node, "metadata") and hasattr(node.metadata, "labels"):
        for key, value in node.metadata.labels.items():
            if key.startswith(label_key):
                roles.append(value)
    return roles if roles else ["worker"]  # Default to worker if no role label


def get_node_address(node, address_type: str) -> Optional[str]:
    """Get node address by type."""
    for address in node.status.addresses or []:
        if address.type == address_type:
            return address.address
    return None


def get_pod_status(pod) -> str:
    """Get detailed pod status."""
    if not pod.status:
        return "Unknown"

    # Check for specific conditions
    if pod.status.phase == "Running":
        if any(
            hasattr(container, "status")
            and hasattr(container.status, "waiting")
            and container.status.waiting
            and container.status.waiting.reason == "CrashLoopBackOff"
            for container in (pod.status.container_statuses or [])
        ):
            return "CrashLoopBackOff"
        elif any(
            hasattr(container, "status") and hasattr(container.status, "waiting") and container.status.waiting
            for container in (pod.status.container_statuses or [])
        ):
            return "Waiting"

    # Check pod conditions
    for condition in pod.status.conditions or []:
        if condition.type == "Ready" and condition.status == "False":
            return f"NotReady ({condition.reason})"

    return pod.status.phase


def calculate_age(timestamp) -> str:
    """Calculate age from timestamp."""
    if not timestamp:
        return "Unknown"
    try:
        # Simple age calculation (could be more precise)
        from datetime import datetime

        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00").replace("+00:00", ""))
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


def format_timestamp(timestamp) -> str:
    """Format timestamp for display."""
    if not timestamp:
        return "N/A"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00").replace("+00:00", ""))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp if timestamp else "N/A"


def calculate_certificate_expiration(not_after: str) -> Optional[str]:
    """Calculate days until certificate expiration."""
    if not not_after or not_after == "Unknown":
        return None
    try:
        from datetime import datetime

        # Parse the RFC3339 timestamp
        dt = datetime.fromisoformat(not_after.replace("Z", "+00:00").replace("+00:00", ""))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        delta = dt - now

        if delta.days < 0:
            return "Expired"
        elif delta.days == 0:
            return "Today"
        elif delta.days == 1:
            return "1 day"
        else:
            return f"{delta.days} days"
    except Exception:
        return None


def parse_cidr(cidr_str: str) -> Optional[ipaddress.IPv4Network]:
    """Parse a CIDR string into an IP network object."""
    try:
        return ipaddress.ip_network(cidr_str)
    except ValueError:
        return None


def cidrs_overlap(cidr1: ipaddress.IPv4Network, cidr2: ipaddress.IPv4Network) -> bool:
    """Check if two CIDR ranges overlap."""
    return cidr1.overlaps(cidr2)


def cidr_contains(cidr1: ipaddress.IPv4Network, cidr2: ipaddress.IPv4Network) -> bool:
    """Check if cidr1 contains cidr2."""
    return cidr1.overlaps(cidr2) and cidr1.prefixlen <= cidr2.prefixlen


def calculate_cidr_utilization(cidr: ipaddress.IPv4Network, allocated_ips: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate CIDR utilization based on allocated IPs."""
    total_ips = cidr.num_addresses

    # Count allocated IPs (excluding network and broadcast addresses)
    allocated_count = 0
    if allocated_ips:
        for ip_range in allocated_ips.get("ipRanges", []):
            try:
                start_ip = ipaddress.ip_address(ip_range.get("start", "0.0.0.0"))
                end_ip = ipaddress.ip_address(ip_range.get("end", "0.0.0.0"))
                allocated_count += end_ip - start_ip + 1
            except (ValueError, TypeError):
                continue

    # Calculate utilization percentage
    usable_ips = total_ips - 2  # Exclude network and broadcast addresses
    utilization = (allocated_count / usable_ips * 100) if usable_ips > 0 else 0

    return {
        "total_ips": total_ips,
        "usable_ips": usable_ips,
        "allocated_ips": allocated_count,
        "utilization_percent": round(utilization, 2),
    }


def is_cidr_exhausted(cidr: ipaddress.IPv4Network, allocated_ips: Dict[str, Any], threshold: float = 90.0) -> bool:
    """Check if a CIDR is exhausted based on utilization threshold."""
    utilization = calculate_cidr_utilization(cidr, allocated_ips)
    return utilization["utilization_percent"] >= threshold


def is_cidr_invalid(cidr_str: str) -> bool:
    """Check if a CIDR string is invalid."""
    return cidr_str.startswith("Invalid:")


def is_reservation_stale(reservation: Dict[str, Any], ippool: Optional[Dict[str, Any]] = None) -> bool:
    """Check if a reservation is stale (e.g., pod no longer exists)."""
    # Check if the reservation has a corresponding pod
    if ippool:
        # Simple check: if IPPool is exhausted, reservation might be stale
        for cidr in ippool.get("cidrs", []):
            if not is_cidr_invalid(cidr) and is_cidr_exhausted(parse_cidr(cidr), ippool.get("allocated_ips", {})):
                return True

    # Check age - reservations older than 1 day might be stale
    if reservation.get("age", "0d") and any(reservation["age"].endswith(suffix) for suffix in ["d", "m", "y"]):
        age_value = int(reservation["age"][:-1])
        if reservation["age"].endswith("d") and age_value > 1:
            return True
        elif reservation["age"].endswith("m") and age_value > 1:
            return True
        elif reservation["age"].endswith("y") and age_value > 0:
            return True

    return False
