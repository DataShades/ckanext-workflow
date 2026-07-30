from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk

SHOW_ADMIN_TAB = "ckanext.workflow.ui.show_admin_tab"
TASK_LIST = "ckanext.workflow.automated_tasks"


def show_admin_tab() -> bool:
    """Display the tab for workflows in the CKAN Admin UI."""
    return tk.config[SHOW_ADMIN_TAB]


def get_automated_tasks() -> list[dict[str, str]]:
    """Get the list of available automated tasks from the configuration."""
    keys = tk.config[TASK_LIST]
    if not keys:
        return [
            {"value": "validation_task", "text": "Validate Dataset Data"},
            {"value": "notification_task", "text": "Send Slack Notification"},
            {"value": "noop_test_task", "text": "No-Op Test Task"},
        ]

    tasks: list[dict[str, Any]] = []
    for key in keys:
        title = tk.config.get(f"ckanext.workflow.automated_task.{key}.title", key)
        tasks.append({"value": key, "text": title})
    return tasks
