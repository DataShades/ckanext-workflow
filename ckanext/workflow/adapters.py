# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import ckan.plugins.toolkit as tk
from ckanext.workflow.interfaces import IWorkflowAutomatedTaskRunner

log = logging.getLogger(__name__)


class N8nAdapter(IWorkflowAutomatedTaskRunner):
    """Adapter for triggering and cancelling tasks in n8n."""

    def trigger_task(self, task_id: str, dataset_id: str, callback_url: str, config: dict) -> bool:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            log.error("N8nAdapter: webhook_url is missing in step configurations")
            return False

        # Read global config values
        api_key = tk.config.get("ckan.plugins.workflow.api_token", "")

        payload = {
            "dataset_id": dataset_id,
            "task_id": task_id,
            "callback_url": callback_url,
            "api_key": api_key,
            "parameters": config.get("parameters", {})
        }

        try:
            import requests
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code in (200, 201):
                log.info(f"N8nAdapter: task {task_id} successfully triggered on {webhook_url}")
                return True
            else:
                log.error(f"N8nAdapter: failed to trigger task {task_id}. Status: {response.status_code}, Body: {response.text}")
                return False
        except Exception as e:
            log.error(f"N8nAdapter: error triggering task {task_id} on {webhook_url}: {e}")
            return False

    def cancel_task(self, task_id: str, config: dict) -> bool:
        cancel_url = config.get("cancel_url")
        if not cancel_url:
            log.warning(f"N8nAdapter: cancel_url not configured for task {task_id}")
            return True

        payload = {
            "task_id": task_id
        }

        try:
            import requests
            response = requests.post(cancel_url, json=payload, timeout=10)
            if response.status_code in (200, 201):
                log.info(f"N8nAdapter: task {task_id} successfully cancelled on {cancel_url}")
                return True
            else:
                log.error(f"N8nAdapter: failed to cancel task {task_id}. Status: {response.status_code}")
                return False
        except Exception as e:
            log.error(f"N8nAdapter: error cancelling task {task_id}: {e}")
            return False

    def get_task_status(self, task_id: str, config: dict) -> str:
        status_url = config.get("status_url")
        if not status_url:
            log.warning(f"N8nAdapter: status_url not configured for task {task_id}")
            return "unknown"

        try:
            import requests
            response = requests.get(status_url, params={"task_id": task_id}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("status", "running")
            return "unknown"
        except Exception as e:
            log.error(f"N8nAdapter: error getting task status for {task_id}: {e}")
            return "unknown"


class NoOpAdapter(IWorkflowAutomatedTaskRunner):
    """No-op adapter that immediately completes the task for local testing."""

    def trigger_task(self, task_id: str, dataset_id: str, callback_url: str, config: dict) -> bool:
        log.info(f"NoOpAdapter: immediately completing task {task_id}")

        from ckan.model.meta import Session
        from ckanext.workflow.model import WorkflowTask

        task = Session.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        if not task:
            log.error(f"NoOpAdapter: task {task_id} not found in database")
            return False

        from ckanext.workflow.service import WorkflowService
        success, msg = WorkflowService.complete_task(
            instance_id=task.instance_id,
            sequence=task.sequence,
            action_type="complete",
            comment="Completed automatically by NoOpAdapter",
            user_name="system"
        )

        if not success:
            log.error(f"NoOpAdapter: failed to complete task {task_id}: {msg}")
            return False

        return True

    def cancel_task(self, task_id: str, config: dict) -> bool:
        log.info(f"NoOpAdapter: cancel requested for task {task_id}")
        return True

    def get_task_status(self, task_id: str, config: dict) -> str:
        return "completed"


def get_automated_task_runner() -> IWorkflowAutomatedTaskRunner:
    """Loads the configured IWorkflowAutomatedTaskRunner implementation."""
    runner_setting = tk.config.get("ckan.plugins.workflow.automated_runner", "n8n")

    if runner_setting == "n8n":
        return N8nAdapter()
    elif runner_setting == "noop":
        return NoOpAdapter()

    # Dynamic loading of custom runner classes
    try:
        import importlib
        module_path, class_name = runner_setting.split(":")
        module = importlib.import_module(module_path)
        runner_class = getattr(module, class_name)
        
        runner = runner_class()
        if not isinstance(runner, IWorkflowAutomatedTaskRunner):
            raise TypeError(f"Runner class {runner_setting} must implement IWorkflowAutomatedTaskRunner")
        return runner
    except Exception as e:
        log.error(f"Failed to load workflow automated runner '{runner_setting}': {e}. Falling back to N8nAdapter.")
        return N8nAdapter()
