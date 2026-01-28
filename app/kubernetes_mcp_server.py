#!/usr/bin/env python3
"""
Kubernetes MCP (Model Context Protocol) Server
A read-only Kubernetes cluster inspection tool using the official Python client.
"""

import sys
from typing import Dict, List, Optional, Tuple
from kubernetes import config, client
from kubernetes.client.exceptions import ApiException
from fastmcp import FastMCP


class KubernetesMCPServer:
    """Main Kubernetes MCP Server class for cluster inspection."""

    def __init__(self, kubeconfig_path: Optional[str] = None):
        self.core_api = None
        self.apps_api = None
        self.batch_api = None
        self.events_api = None
        self.initialized = False
        self.mcp = FastMCP(name="Kubernetes MCP Server")
        self.kubeconfig_path = kubeconfig_path
        
    def initialize(self):
        """Initialize the Kubernetes client."""
        try:
            # Try in-cluster config first, fall back to kubeconfig
            try:
                config.load_incluster_config()
            except Exception:
                if self.kubeconfig_path:
                    config.load_kube_config(config_file=self.kubeconfig_path)
                else:
                    config.load_kube_config()
            
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.batch_api = client.BatchV1Api()
            # Events API is available in newer versions
            try:
                self.events_api = client.EventsV1Api()
            except Exception:
                pass  # Fall back to core API for events
            
            self.initialized = True
        except Exception as e:
            print(f"Error initializing Kubernetes client: {e}")
            return False
        return True
    
    def get_cluster_status(self) -> Dict:
        """Get overall cluster status."""
        if not self.initialized:
            return {"error": "Not initialized"}
        
        try:
            nodes = self.core_api.list_node().items
            ready_nodes = sum(1 for node in nodes if self._is_node_ready(node))
            total_nodes = len(nodes)
            
            namespaces = self.core_api.list_namespace().items
            namespace_count = len(namespaces)
            
            # Check cluster conditions
            cluster_healthy = ready_nodes == total_nodes and total_nodes > 0
            
            return {
                "status": "Healthy" if cluster_healthy else "Degraded",
                "nodes": {
                    "total": total_nodes,
                    "ready": ready_nodes,
                    "not_ready": total_nodes - ready_nodes
                },
                "namespaces": namespace_count,
                "api_server": "Healthy"  # Basic health check passed
            }
        except ApiException as e:
            return {"error": f"API Error: {e.reason}", "status_code": e.status}
        except Exception as e:
            return {"error": str(e)}
    
    def get_nodes(self) -> List[Dict]:
        """Get list of all nodes with status."""
        if not self.initialized:
            return []
        
        try:
            nodes = []
            for node in self.core_api.list_node().items:
                node_info = {
                    "name": node.metadata.name,
                    "status": "Ready" if self._is_node_ready(node) else "NotReady",
                    "roles": self._get_node_labels(node, "kubernetes.io/role"),
                    "internal_ip": self._get_node_address(node, "InternalIP"),
                    "external_ip": self._get_node_address(node, "ExternalIP"),
                    "os_image": node.status.node_info.os_image,
                    "kernel_version": node.status.node_info.kernel_version,
                    "container_runtime": node.status.node_info.container_runtime_version,
                }
                
                # Add capacity and allocatable info
                if node.status.capacity:
                    node_info["capacity"] = {
                        "cpu": node.status.capacity.get("cpu", "N/A"),
                        "memory": node.status.capacity.get("memory", "N/A"),
                        "pods": node.status.capacity.get("pods", "N/A")
                    }
                
                if node.status.allocatable:
                    node_info["allocatable"] = {
                        "cpu": node.status.allocatable.get("cpu", "N/A"),
                        "memory": node.status.allocatable.get("memory", "N/A"),
                        "pods": node.status.allocatable.get("pods", "N/A")
                    }
                
                nodes.append(node_info)
            
            return nodes
        except ApiException as e:
            print(f"API Error getting nodes: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting nodes: {e}", file=sys.stderr)
            return []
    
    def get_namespaces(self) -> List[Dict]:
        """Get list of all namespaces with status."""
        if not self.initialized:
            return []
        
        try:
            namespaces = []
            for ns in self.core_api.list_namespace().items:
                namespaces.append({
                    "name": ns.metadata.name,
                    "status": "Active" if ns.status.phase == "Active" else ns.status.phase,
                    "age": self._calculate_age(ns.metadata.creation_timestamp)
                })
            return namespaces
        except ApiException as e:
            print(f"API Error getting namespaces: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting namespaces: {e}", file=sys.stderr)
            return []
    
    def get_pods(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of pods, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                pods_list = self.core_api.list_namespaced_pod(namespace).items
            else:
                pods_list = self.core_api.list_pod_for_all_namespaces().items
            
            pods = []
            for pod in pods_list:
                ns = pod.metadata.namespace if namespace is None else namespace
                pods.append({
                    "name": pod.metadata.name,
                    "namespace": ns,
                    "phase": pod.status.phase if pod.status else "Unknown",
                    "status": self._get_pod_status(pod),
                    "restart_count": sum(
                        container.status.restart_count 
                        for container in (pod.status.container_statuses or []) 
                        if hasattr(container, 'status') and hasattr(container.status, 'restart_count')
                    ),
                    "node": pod.spec.node_name,
                    "age": self._calculate_age(pod.metadata.creation_timestamp),
                    "labels": pod.metadata.labels or {}
                })
            
            return pods
        except ApiException as e:
            print(f"API Error getting pods: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting pods: {e}", file=sys.stderr)
            return []
    
    def get_deployments(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of deployments, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                deps_list = self.apps_api.list_namespaced_deployment(namespace).items
            else:
                deps_list = self.apps_api.list_deployment_for_all_namespaces().items
            
            deployments = []
            for dep in deps_list:
                ns = dep.metadata.namespace if namespace is None else namespace
                deployments.append({
                    "name": dep.metadata.name,
                    "namespace": ns,
                    "desired_replicas": dep.spec.replicas,
                    "available_replicas": dep.status.available_replicas or 0,
                    "ready_replicas": dep.status.ready_replicas or 0,
                    "up_to_date_replicas": dep.status.updated_replicas or 0,
                    "age": self._calculate_age(dep.metadata.creation_timestamp),
                    "labels": dep.metadata.labels or {}
                })
            
            return deployments
        except ApiException as e:
            print(f"API Error getting deployments: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting deployments: {e}", file=sys.stderr)
            return []
    
    def get_statefulsets(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of stateful sets, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                sts_list = self.apps_api.list_namespaced_stateful_set(namespace).items
            else:
                sts_list = self.apps_api.list_stateful_set_for_all_namespaces().items
            
            statefulsets = []
            for sts in sts_list:
                ns = sts.metadata.namespace if namespace is None else namespace
                statefulsets.append({
                    "name": sts.metadata.name,
                    "namespace": ns,
                    "desired_replicas": sts.spec.replicas,
                    "ready_replicas": sts.status.ready_replicas or 0,
                    "current_revision": sts.status.current_revision or "N/A",
                    "update_revision": sts.status.update_revision or "N/A",
                    "age": self._calculate_age(sts.metadata.creation_timestamp),
                    "labels": sts.metadata.labels or {}
                })
            
            return statefulsets
        except ApiException as e:
            print(f"API Error getting stateful sets: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting stateful sets: {e}", file=sys.stderr)
            return []
    
    def get_daemonsets(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of daemon sets, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                ds_list = self.apps_api.list_namespaced_daemon_set(namespace).items
            else:
                ds_list = self.apps_api.list_daemon_set_for_all_namespaces().items
            
            daemonsets = []
            for ds in ds_list:
                ns = ds.metadata.namespace if namespace is None else namespace
                daemonsets.append({
                    "name": ds.metadata.name,
                    "namespace": ns,
                    "desired_replicas": ds.status.desired_number_scheduled or 0,
                    "current_replicas": ds.status.current_number_scheduled or 0,
                    "ready_replicas": ds.status.number_ready or 0,
                    "updated_replicas": ds.status.updated_number_scheduled or 0,
                    "age": self._calculate_age(ds.metadata.creation_timestamp),
                    "labels": ds.metadata.labels or {}
                })
            
            return daemonsets
        except ApiException as e:
            print(f"API Error getting daemon sets: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting daemon sets: {e}", file=sys.stderr)
            return []
    
    def get_jobs(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of jobs, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                jobs_list = self.batch_api.list_namespaced_job(namespace).items
            else:
                jobs_list = self.batch_api.list_job_for_all_namespaces().items
            
            jobs = []
            for job in jobs_list:
                ns = job.metadata.namespace if namespace is None else namespace
                jobs.append({
                    "name": job.metadata.name,
                    "namespace": ns,
                    "completions": job.spec.completions,
                    "parallelism": job.spec.parallelism,
                    "active": job.status.active or 0,
                    "succeeded": job.status.succeeded or 0,
                    "failed": job.status.failed or 0,
                    "age": self._calculate_age(job.metadata.creation_timestamp),
                    "labels": job.metadata.labels or {}
                })
            
            return jobs
        except ApiException as e:
            print(f"API Error getting jobs: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting jobs: {e}", file=sys.stderr)
            return []
    
    def get_cronjobs(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of cron jobs, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                cj_list = self.batch_api.list_namespaced_cron_job(namespace).items
            else:
                cj_list = self.batch_api.list_cron_job_for_all_namespaces().items
        
            cronjobs = []
            for cj in cj_list:
                ns = cj.metadata.namespace if namespace is None else namespace
                cronjobs.append({
                    "name": cj.metadata.name,
                    "namespace": ns,
                    "schedule": cj.spec.schedule,
                    "suspend": cj.spec.suspend,
                    "active_jobs": len(cj.status.active or []),
                    "last_run_time": self._format_timestamp(cj.status.last_schedule_time) if cj.status and cj.status.last_schedule_time else "N/A",
                    "age": self._calculate_age(cj.metadata.creation_timestamp),
                    "labels": cj.metadata.labels or {}
                })
        
            return cronjobs
        except ApiException as e:
            print(f"API Error getting cron jobs: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting cron jobs: {e}", file=sys.stderr)
            return []
    
    def get_ingresses(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of ingress resources, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            # Check if networking.k8s.io/v1 API is available
            has_networking_api = True
            try:
                test_api = client.NetworkingV1Api()
            except Exception:
                has_networking_api = False
            
            ingresses = []
            if namespace:
                if has_networking_api:
                    ing_list = client.NetworkingV1Api().list_namespaced_ingress(namespace).items
                else:
                    # Fallback to extensions/v1beta1 API
                    try:
                        ing_list = client.ExtensionsV1beta1Api().list_namespaced_ingress(namespace).items
                    except Exception:
                        return []
            else:
                if has_networking_api:
                    ing_list = client.NetworkingV1Api().list_ingress_for_all_namespaces().items
                else:
                    # Fallback to extensions/v1beta1 API
                    try:
                        ing_list = client.ExtensionsV1beta1Api().list_ingress_for_all_namespaces().items
                    except Exception:
                        return []
            
            for ing in ing_list:
                ns = ing.metadata.namespace if namespace is None else namespace
                
                # Get rules and paths
                rules = []
                for rule in ing.spec.rules or []:
                    host = rule.host if hasattr(rule, 'host') and rule.host else "*"
                    http_paths = []
                    
                    if hasattr(rule, 'http') and rule.http and hasattr(rule.http, 'paths'):
                        for path in rule.http.paths:
                            http_paths.append({
                                "path": path.path,
                                "backend_service": f"{path.backend.service_name} ({path.backend.service_port.number if hasattr(path.backend.service_port, 'number') else path.backend.service_port})"
                            })
                    
                    rules.append({
                        "host": host,
                        "paths": http_paths
                    })
                
                # Get ingress class
                ingress_class = ing.spec.ingress_class_name if hasattr(ing.spec, 'ingress_class_name') and ing.spec.ingress_class_name else "N/A"
            
                ingresses.append({
                    "name": ing.metadata.name,
                    "namespace": ns,
                    "ingress_class": ingress_class,
                    "rules": rules,
                    "tls": len(ing.spec.tls or []) > 0,
                    "age": self._calculate_age(ing.metadata.creation_timestamp),
                    "labels": ing.metadata.labels or {}
                })
            
            return ingresses
        except ApiException as e:
            print(f"API Error getting ingresses: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting ingresses: {e}", file=sys.stderr)
            return []

    def get_service_accounts(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of service accounts, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                sa_list = self.core_api.list_namespaced_service_account(namespace).items
            else:
                sa_list = self.core_api.list_service_account_for_all_namespaces().items
            
            service_accounts = []
            for sa in sa_list:
                ns = sa.metadata.namespace if namespace is None else namespace
                service_accounts.append({
                    "name": sa.metadata.name,
                    "namespace": ns,
                    "secrets": len(sa.secrets or []),
                    "automount": sa.automount_service_account_token,
                    "age": self._calculate_age(sa.metadata.creation_timestamp),
                    "labels": sa.metadata.labels or {}
                })
            
            return service_accounts
        except ApiException as e:
            print(f"API Error getting service accounts: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting service accounts: {e}", file=sys.stderr)
            return []
    
    def get_roles(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of roles, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                role_list = self.core_api.list_namespaced_role(namespace).items
            else:
                # Roles are namespaced, so we need to get them from all namespaces
                roles = []
                namespaces_resp = self.core_api.list_namespace()
                for ns in namespaces_resp.items:
                    try:
                        ns_roles = self.core_api.list_namespaced_role(ns.metadata.name).items
                        roles.extend(ns_roles)
                    except Exception:
                        continue
            
            result = []
            for role in role_list if namespace else roles:
                ns = role.metadata.namespace if namespace is None else namespace
                result.append({
                    "name": role.metadata.name,
                    "namespace": ns,
                    "rules": [
                        {
                            "api_groups": rule.rules[i].api_groups,
                            "resources": rule.rules[i].resources,
                            "verbs": rule.rules[i].verbs
                        }
                        for i in range(len(role.rules))
                    ],
                    "age": self._calculate_age(role.metadata.creation_timestamp),
                    "labels": role.metadata.labels or {}
                })
            
            return result
        except ApiException as e:
            print(f"API Error getting roles: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting roles: {e}", file=sys.stderr)
            return []
    
    def get_role_bindings(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get list of role bindings, optionally filtered by namespace."""
        if not self.initialized:
            return []
        
        try:
            if namespace:
                rb_list = self.core_api.list_namespaced_role_binding(namespace).items
            else:
                # RoleBindings are namespaced, so we need to get them from all namespaces
                rbs = []
                namespaces_resp = self.core_api.list_namespace()
                for ns in namespaces_resp.items:
                    try:
                        ns_rbs = self.core_api.list_namespaced_role_binding(ns.metadata.name).items
                        rbs.extend(ns_rbs)
                    except Exception:
                        continue
            
            result = []
            for rb in rb_list if namespace else rbs:
                ns = rb.metadata.namespace if namespace is None else namespace
                result.append({
                    "name": rb.metadata.name,
                    "namespace": ns,
                    "role_ref": {
                        "kind": rb.role_ref.kind,
                        "name": rb.role_ref.name,
                        "api_group": rb.role_ref.apigroup
                    } if rb.role_ref else None,
                    "subjects": [
                        {
                            "kind": sub.kind,
                            "name": sub.name,
                            "namespace": getattr(sub, 'namespace', None),
                            "api_group": getattr(sub, 'apigroup', None)
                        }
                        for sub in rb.subjects
                    ],
                    "age": self._calculate_age(rb.metadata.creation_timestamp),
                    "labels": rb.metadata.labels or {}
                })
            
            return result
        except ApiException as e:
            print(f"API Error getting role bindings: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting role bindings: {e}", file=sys.stderr)
            return []
    
    def get_cluster_roles(self) -> List[Dict]:
        """Get list of all cluster roles."""
        if not self.initialized:
            return []
        
        try:
            rbac_api = client.RbacAuthorizationV1Api()
            cr_list = rbac_api.list_cluster_role().items
            
            result = []
            for cr in cr_list:
                result.append({
                    "name": cr.metadata.name,
                    "rules": [
                        {
                            "api_groups": rule.api_groups,
                            "resources": rule.resources,
                            "verbs": rule.verbs,
                            "resource_names": getattr(rule, 'resource_names', [])
                        }
                        for rule in cr.rules
                    ],
                    "age": self._calculate_age(cr.metadata.creation_timestamp),
                    "labels": cr.metadata.labels or {}
                })
            
            return result
        except ApiException as e:
            print(f"API Error getting cluster roles: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting cluster roles: {e}", file=sys.stderr)
            return []
    
    def get_cluster_role_bindings(self) -> List[Dict]:
        """Get list of all cluster role bindings."""
        if not self.initialized:
            return []
        
        try:
            rbac_api = client.RbacAuthorizationV1Api()
            crb_list = rbac_api.list_cluster_role_binding().items
            
            result = []
            for crb in crb_list:
                result.append({
                    "name": crb.metadata.name,
                    "role_ref": {
                        "kind": crb.role_ref.kind,
                        "name": crb.role_ref.name,
                        "api_group": crb.role_ref.apigroup
                    } if crb.role_ref else None,
                    "subjects": [
                        {
                            "kind": sub.kind,
                            "name": sub.name,
                            "namespace": getattr(sub, 'namespace', None),
                            "api_group": getattr(sub, 'apigroup', None)
                        }
                        for sub in crb.subjects
                    ],
                    "age": self._calculate_age(crb.metadata.creation_timestamp),
                    "labels": crb.metadata.labels or {}
                })
            
            return result
        except ApiException as e:
            print(f"API Error getting cluster role bindings: {e.reason}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Error getting cluster role bindings: {e}", file=sys.stderr)
            return []
    
    def get_events(self, namespace: Optional[str] = None) -> List[Dict]:
        """Get recent events, optionally filtered by namespace."""
        # Always use fallback to avoid issues with EventsV1Api
        return self._get_events_fallback(namespace)
    
    def get_pod_logs(self, pod_name: str, namespace: Optional[str] = None, tail_lines: int = 100) -> str:
        """Get logs from a specific pod."""
        if not self.initialized:
            return "Server not initialized"
        
        try:
            # First check if the pod exists
            pods = []
            if namespace:
                pods_list = self.core_api.list_namespaced_pod(namespace).items
                pods = [p for p in pods_list if p.metadata.name == pod_name]
            else:
                pods_list = self.core_api.list_pod_for_all_namespaces().items
                pods = [p for p in pods_list if p.metadata.name == pod_name]
            
            if not pods:
                return f"Pod '{pod_name}' not found"
            elif len(pods) > 1:
                namespaces_found = [p.metadata.namespace for p in pods]
                return f"Multiple pods named '{pod_name}' found in namespaces: {', '.join(namespaces_found)}. Please specify a namespace."
            
            # Pod exists, now try to get logs
            pod_namespace = pods[0].metadata.namespace
            log_data = self.core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=pod_namespace,
                tail_lines=tail_lines
            )
            
            return log_data if log_data else "No logs available"
        except ApiException as e:
            error_msg = str(e)
            if e.status == 400 and "Bad Request" in error_msg:
                # Pod might exist but not be running or have issues
                return f"Cannot retrieve logs: The pod may not be running or has no logs. Error: {e.reason}"
            print(f"API Error getting pod logs: {e.reason}", file=sys.stderr)
            return f"Error: {e.reason}"
        except Exception as e:
            print(f"Error getting pod logs: {e}", file=sys.stderr)
            return f"Error: {str(e)}"
    
    def _get_events_fallback(self, namespace: Optional[str] = None) -> List[Dict]:
        """Fallback method to get events using CoreV1Api."""
        try:
            if namespace:
                events_list = self.core_api.list_namespaced_event(namespace).items
            else:
                events_list = self.core_api.list_event_for_all_namespaces().items
            
            events = []
            for event in events_list:
                ns = event.metadata.namespace if namespace is None else namespace
                events.append({
                    "name": event.metadata.name,
                    "namespace": ns,
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "involved_object": {
                        "kind": event.involved_object.kind,
                        "name": event.involved_object.name,
                        "namespace": getattr(event.involved_object, 'namespace', None)
                    },
                    "count": event.count
                })
            
            return events
        except Exception as e:
            print(f"Error getting events (fallback): {e}", file=sys.stderr)
            return []
    
    def _is_node_ready(self, node) -> bool:
        """Check if a node is ready."""
        for condition in node.status.conditions or []:
            if condition.type == "Ready":
                return condition.status == "True"
        return False
    
    def _get_node_labels(self, node, label_key: str) -> List[str]:
        """Get node labels by key."""
        roles = []
        for key, value in (node.metadata.labels or {}).items():
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
