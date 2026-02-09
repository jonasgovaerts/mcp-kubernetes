from typing import Optional, List, Dict, Any
import logging

from utils.helpers import calculate_age

logger = logging.getLogger(__name__)


class Workloads:
    def __init__(self, apps_api, batch_api):
        self.apps_api = apps_api
        self.batch_api = batch_api

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
                    "desired_replicas": dep.status.replicas if dep.status and dep.status.replicas is not None else 0,
                    # noqa: E501
                    "age": calculate_age(dep.metadata.creation_timestamp),
                    "strategy": dep.spec.strategy.type if dep.spec and dep.spec.strategy else "RollingUpdate"
                    # noqa: E501
                })

            return result
        except Exception as e:
            logger.error(f"Error getting deployments: {e}", exc_info=True)
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
                    "age": calculate_age(ss.metadata.creation_timestamp)
                })

            return result
        except Exception as e:
            logger.error(f"Error getting statefulsets: {e}", exc_info=True)
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
                    "age": calculate_age(ds.metadata.creation_timestamp)
                })

            return result
        except Exception as e:
            logger.error(f"Error getting daemonsets: {e}", exc_info=True)
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
                    "age": calculate_age(job.metadata.creation_timestamp),
                    "status": "Completed" if job.status and job.status.succeeded else "Running"  # noqa: E501
                })

            return result
        except Exception as e:
            logger.error(f"Error getting jobs: {e}", exc_info=True)
            return []

    def get_cronjobs(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of cron jobs, optionally filtered by namespace."""
        try:
            if namespace:
                cronjobs = self.batch_api.list_namespaced_cron_job(namespace).items  # noqa: E501
            else:
                cronjobs = self.batch_api.list_cron_job_for_all_namespaces().items  # noqa: E501

            result = []
            for cj in cronjobs:
                result.append({
                    "name": cj.metadata.name,
                    "namespace": cj.metadata.namespace,
                    "schedule": cj.spec.schedule if cj.spec else "N/A",
                    "suspend": cj.spec.suspend if cj.spec else False,
                    "age": calculate_age(cj.metadata.creation_timestamp)
                })

            return result
        except Exception as e:
            logger.error(f"Error getting cronjobs: {e}", exc_info=True)
            return []