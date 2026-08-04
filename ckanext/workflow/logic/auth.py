from __future__ import annotations

from typing import Any

import ckan.plugins.toolkit as tk
from ckan.model.meta import Session
from ckan.types import Context

from ckanext.workflow.model import WorkflowInstance, WorkflowTask
from ckanext.workflow.service import user_has_role


def workflow_definition_create(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can create workflow definitions"}


def workflow_definition_update(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can update workflow definitions"}


def workflow_definition_delete(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can delete workflow definitions"}


def workflow_definition_show(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can view workflow definitions"}


def workflow_start(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can initiate workflows"}


def workflow_definition_list(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can list workflow definitions"}


def workflow_timeout_apply(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can mark workflows as overdue"}


def workflow_instance_list(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": False, "msg": "Only sysadmins can view workflow instances"}


@tk.auth_disallow_anonymous_access
def workflow_user_task_list(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": True}


@tk.auth_disallow_anonymous_access
def workflow_user_notification_list(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": True}


@tk.auth_disallow_anonymous_access
def workflow_user_notification_mark_read(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:  # pyright: ignore[reportUnusedParameter]
    return {"success": True}


@tk.auth_disallow_anonymous_access
def workflow_task_complete(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    instance_id = data_dict.get("id")
    sequence = data_dict.get("sequence")
    if not instance_id or sequence is None:
        return {"success": False, "msg": "Missing task identifiers"}

    inst = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not inst:
        return {"success": False, "msg": "Workflow instance not found"}

    task = (
        Session.query(WorkflowTask)
        .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == sequence)
        .first()
    )
    if not task:
        return {"success": False, "msg": "Workflow task not found"}

    # Fetch package to check organization and user role
    try:
        pkg = tk.get_action("package_show")(tk.fresh_context(context), {"id": inst.object_id})
    except (tk.ObjectNotFound, tk.NotAuthorized) as e:
        return {"success": False, "msg": f"Access check failed: {e}"}

    org_id = pkg.get("owner_org")

    if user_has_role(context["user"], org_id, task.assigned_role):
        return {"success": True}

    return {"success": False, "msg": "Unauthorized to complete this step"}


@tk.auth_disallow_anonymous_access
def workflow_instance_cancel(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    instance_id = data_dict.get("id")
    if not instance_id:
        return {"success": False, "msg": "Missing workflow instance identifier"}

    inst = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not inst:
        return {"success": False, "msg": "Workflow instance not found"}

    # Check package_update access for the dataset
    try:
        tk.check_access("package_update", tk.fresh_context(context), {"id": inst.object_id})
    except tk.NotAuthorized:
        return {"success": False, "msg": "Unauthorized to cancel this workflow"}
    return {"success": True}


@tk.auth_disallow_anonymous_access
def workflow_instance_show(context: Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    instance_id = data_dict.get("id")
    if not instance_id:
        return {"success": False, "msg": "Missing workflow instance identifier"}

    inst = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not inst:
        return {"success": False, "msg": "Workflow instance not found"}

    # Check package_show access for the dataset
    try:
        tk.check_access("package_show", tk.fresh_context(context), {"id": inst.object_id})
    except tk.NotAuthorized:
        return {"success": False, "msg": "Unauthorized to view this workflow instance"}
    return {"success": True}
