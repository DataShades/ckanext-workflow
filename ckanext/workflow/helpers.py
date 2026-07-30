from __future__ import annotations

import sqlalchemy as sa

import ckan.plugins.toolkit as tk
from ckan import model

from ckanext.workflow.model import WorkflowInstance, WorkflowNotification

from . import config
from .service import user_has_role


def workflow_show_admin_tab():
    """Check if the workflow admin tab should be displayed in the CKAN Admin UI."""
    return config.show_admin_tab()


def workflow_get_instance_for_package(object_id: str):
    stmt = sa.select(WorkflowInstance).where(
        WorkflowInstance.object_id == object_id, WorkflowInstance.status.in_(["active", "overdue"])
    )
    return model.Session.scalar(stmt)


def workflow_get_unread_notifications() -> list[WorkflowNotification]:
    stmt = (
        sa.select(WorkflowNotification)
        .where(WorkflowNotification.user_name == tk.current_user.name, WorkflowNotification.read == sa.false())
        .order_by(WorkflowNotification.created_at.desc())
    )
    return list(model.Session.scalars(stmt))


def workflow_user_has_role(user_name: str, organization_id: str, required_role: str):
    return user_has_role(user_name, organization_id, required_role)


def workflow_get_automated_tasks() -> list[dict[str, str]]:
    """Helper to retrieve available automated tasks from the configuration."""
    return config.get_automated_tasks()


def workflow_get_users() -> list[dict[str, str]]:
    """Helper to retrieve all active users in the system."""
    users = tk.get_action("user_list")({"ignore_auth": True}, {})
    return [
        {"value": f"user:{u['name']}", "text": u.get("display_name") or u["name"]}
        for u in users
        if u.get("state") == "active"
    ]
