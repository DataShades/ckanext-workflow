from __future__ import annotations

import importlib
import logging
from typing import Any

import requests
from typing_extensions import override

import ckan.plugins.toolkit as tk
from ckan import model

from ckanext.workflow.interfaces import TaskRunner
from ckanext.workflow.model import WorkflowTask

from . import config

log = logging.getLogger(__name__)


class N8nAdapter(TaskRunner):
    """Adapter for triggering and cancelling tasks in n8n."""

    @override
    def trigger_task(self, task_id: str, dataset_id: str, callback_url: str, config: dict[str, Any]) -> bool:
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
            "parameters": config.get("parameters", {}),
        }

        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
        except requests.RequestException:
            log.exception("N8nAdapter: error triggering task %s on %s", task_id, webhook_url)
            return False

        if response.status_code in (200, 201):
            log.info("N8nAdapter: task %s successfully triggered on %s", task_id, webhook_url)
            return True

        log.error(
            "N8nAdapter: failed to trigger task %s. Status: %s, Body: %s",
            task_id,
            response.status_code,
            response.text,
        )
        return False

    @override
    def cancel_task(self, task_id: str, config: dict[str, Any]) -> bool:
        cancel_url = config.get("cancel_url")
        if not cancel_url:
            log.warning("N8nAdapter: cancel_url not configured for task %s", task_id)
            return True

        payload = {"task_id": task_id}

        try:
            response = requests.post(cancel_url, json=payload, timeout=10)
        except requests.RequestException:
            log.exception("N8nAdapter: error cancelling task %s on %s", task_id, cancel_url)
            return False

        if response.status_code in (200, 201):
            log.info("N8nAdapter: task %s successfully cancelled on %s", task_id, cancel_url)
            return True

        log.error("N8nAdapter: failed to cancel task %s. Status: %s", task_id, response.status_code)
        return False

    @override
    def get_task_status(self, task_id: str, config: dict[str, Any]) -> str:
        status_url = config.get("status_url")
        if not status_url:
            log.warning("N8nAdapter: status_url not configured for task %s", task_id)
            return "unknown"

        try:
            response = requests.get(status_url, params={"task_id": task_id}, timeout=10)
        except requests.RequestException:
            log.exception("N8nAdapter: error getting task status %s on %s", task_id, status_url)
            return "unknosn"

        if response.status_code == requests.status_codes.codes.ok:
            data = response.json()
            return data.get("status", "running")
        return "unknown"


class NoOpAdapter(TaskRunner):
    """No-op adapter that immediately completes the task for local testing."""

    @override
    def trigger_task(self, task_id: str, dataset_id: str, callback_url: str, config: dict[str, Any]) -> bool:
        from ckanext.workflow.service import complete_task  # noqa: PLC0415

        log.info("NoOpAdapter: immediately completing task %s", task_id)

        task = model.Session.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        if not task:
            log.error("NoOpAdapter: task %s not found in database", task_id)
            return False

        success, msg = complete_task(
            instance_id=task.instance_id,
            sequence=task.sequence,
            action_type="complete",
            comment="Completed automatically by NoOpAdapter",
            user_name="system",
        )

        if not success:
            log.error("NoOpAdapter: failed to complete task %s: %s", task_id, msg)
            return False

        return True

    @override
    def cancel_task(self, task_id: str, config: dict[str, Any]) -> bool:
        log.info("NoOpAdapter: cancel requested for task %s", task_id)
        return True

    @override
    def get_task_status(self, task_id: str, config: dict[str, Any]) -> str:
        return "completed"


def get_automated_task_runner() -> TaskRunner:
    """Loads the configured IWorkflowAutomatedTaskRunner implementation."""
    runner_setting = config.runner()

    if runner_setting == "n8n":
        return N8nAdapter()

    if runner_setting == "noop":
        return NoOpAdapter()

    module_path, class_name = runner_setting.split(":")
    module = importlib.import_module(module_path)
    runner_class = getattr(module, class_name)

    runner = runner_class()
    if not isinstance(runner, TaskRunner):
        msg = f"Runner class {runner_setting} must implement IWorkflowAutomatedTaskRunner"
        raise TypeError(msg)
    return runner
