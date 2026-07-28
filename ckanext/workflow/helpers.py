from __future__ import annotations

import ckan.plugins.toolkit as tk

from ckanext.workflow.model import WorkflowNotification

from . import config
from .service import WorkflowService, user_has_role


def workflow_show_admin_tab():
    """Check if the workflow admin tab should be displayed in the CKAN Admin UI."""
    return config.show_admin_tab()


def workflow_get_instance_for_package(object_id: str):
    return WorkflowService.get_instance_for_package(object_id)


def workflow_get_unread_notifications() -> list[WorkflowNotification]:
    if tk.current_user.is_authenticated:
        return WorkflowService.get_notifications(tk.current_user.name)

    return []


def workflow_user_has_role(user_name: str, organization_id: str, required_role: str):
    return user_has_role(user_name, organization_id, required_role)
