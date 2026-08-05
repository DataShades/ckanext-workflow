from __future__ import annotations

import contextlib
import datetime
import logging
import uuid
from typing import Any, Literal

import sqlalchemy as sa

import ckan.plugins.toolkit as tk
from ckan import authz, model
from ckan.lib.search import rebuild

from ckanext.workflow.adapters import get_automated_task_runner
from ckanext.workflow.model import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowNotification,
    WorkflowTask,
)

log = logging.getLogger(__name__)


def _commit():
    model.Session.commit()


def user_has_role(user_name: str | None, organization_id: str, required_role: str):
    if not user_name:
        return False

    if authz.is_sysadmin(user_name):
        return True

    if required_role.startswith("user:"):
        return user_name == required_role[5:]
    permission = {"member": "read", "editor": "create_dataset", "admin": "admin"}.get(required_role)
    if not permission:
        return False
    return authz.has_user_permission_for_group_or_org(organization_id, user_name, permission)


def start_workflow(package_dict: dict[str, Any], trigger: Literal["create", "update", "manual"] = "manual"):
    dataset_type = package_dict.get("type", "dataset")
    # First check specific trigger/type match

    wf = model.Session.scalar(
        sa.select(WorkflowDefinition).where(
            sa.and_(
                WorkflowDefinition.enabled == sa.true(),
                WorkflowDefinition.dataset_type == dataset_type,
                WorkflowDefinition.trigger_type.like(f"%{trigger}%"),
            )
        )
    )

    if not wf:
        # Fall back to default trigger on all datasets
        wf = model.Session.scalar(
            sa.select(WorkflowDefinition).where(
                sa.and_(
                    WorkflowDefinition.enabled == sa.true(),
                    WorkflowDefinition.dataset_type == "all",
                    WorkflowDefinition.trigger_type.like(f"%{trigger}%"),
                )
            )
        )

    if not wf or not wf.steps:
        return None

    # Check if an instance already exists for this package to avoid duplicates
    existing = model.Session.scalar(
        sa.select(WorkflowInstance).where(
            WorkflowInstance.object_id == package_dict["id"], WorkflowInstance.status.in_(["active", "overdue"])
        )
    )
    if existing:
        return existing

    instance_id = str(uuid.uuid4())
    wf_inst = WorkflowInstance(
        id=instance_id,
        object_id=package_dict["id"],
        workflow_id=wf.id,
        current_step_index=0,
        status="active",
        started_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    model.Session.add(wf_inst)

    # Create tasks based on steps
    for step in wf.steps:
        task = WorkflowTask(
            instance_id=instance_id,
            sequence=step.sequence,
            name=step.name,
            assigned_role=step.assigned_role,
            step_type=step.step_type,
            instructions=step.instructions,
            status="pending",
            config=step.config,
        )
        model.Session.add(task)

    _commit()
    rebuild(wf_inst.object_id)

    # If the first step is automated, run it recursively. Else notify assignees.
    first_step = wf.steps[0]
    if first_step.step_type == "automated_task":
        _execute_automated_task(wf_inst.id, 0)
    else:
        _notify_assignees(wf_inst.id, 0)

    return wf_inst


def _send_notification_to_recipient(object_id: str, recipient: str, message: str):
    pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": object_id})
    org_id = pkg.get("owner_org")

    if recipient == "owner":
        creator = pkg.get("creator_user_id")
        if creator:
            add_notification(creator, message)
    elif recipient == "admin":
        users = model.Session.query(model.User).filter(model.User.sysadmin == True).all()
        for u in users:
            add_notification(u.name, message)
    elif recipient in ["member", "editor", "admin_role"]:
        role_name = "admin" if recipient == "admin_role" else recipient
        if org_id:
            org = tk.get_action("organization_show")({"ignore_auth": True}, {"id": org_id, "include_users": True})
            for u in org.get("users", []):
                if u.get("capacity") == role_name:
                    add_notification(u["name"], message)
    else:
        # Direct username
        add_notification(recipient, message)


def _execute_post_actions(object_id: str, actions_list: list[dict[str, Any]]):
    if not actions_list:
        return
    for action in actions_list:
        action_type = action.get("type")
        if action_type == "change_field":
            field_name = action.get("field")
            value = action.get("value")
            if field_name:
                _set_dataset_field(object_id, field_name, value)
        elif action_type == "send_notification":
            recipient = action.get("recipient")
            message = action.get("message")
            if recipient and message:
                _send_notification_to_recipient(object_id, recipient, message)


def _set_dataset_field(object_id: str, field_name: str, value: Any):
    user = tk.get_action("get_site_user")({"ignore_auth": True}, {})
    tk.get_action("package_patch")(
        {"ignore_auth": True, "user": user["name"], "ignore_workflow": True},
        {"id": object_id, field_name: value},
    )


def add_notification(user_name: str, message: str):
    notification = WorkflowNotification(user_name=user_name, message=message, read=False)
    model.Session.add(notification)
    _commit()


def notify_owner(object_id: str, message: str):
    try:
        pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": object_id})
        creator = pkg.get("creator_user_id")
        if creator:
            add_notification(creator, message)
    except Exception:
        log.exception("Failed to notify owner")


def _notify_assignees(instance_id: str, step_sequence: int):
    instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    task = (
        model.Session.query(WorkflowTask)
        .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == step_sequence)
        .first()
    )
    if not instance or not task:
        return

    try:
        pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": instance.object_id})
    except tk.ObjectNotFound:
        log.warning("Failed to notify assignees about wokflow instance %s, step %s", instance_id, step_sequence)
        return

    if task.assigned_role.startswith("user:"):
        target_user = task.assigned_role[5:]
        add_notification(
            target_user,
            (
                f"New confidential workflow task '{task.name}' is assigned to you "
                f"for dataset '{pkg['title'] or pkg['name']}'."
            ),
        )
        return

    org_id = pkg.get("owner_org")
    if org_id:
        org = tk.get_action("organization_show")({"ignore_auth": True}, {"id": org_id, "include_users": True})
        for user in org.get("users", []):
            user_role = user.get("capacity")
            role_hierarchy = {"member": 1, "editor": 2, "admin": 3}
            req_level = role_hierarchy.get(task.assigned_role, 0)
            user_level = role_hierarchy.get(user_role, 0)
            if user_level >= req_level or user.get("sysadmin"):
                add_notification(
                    user["name"],
                    (
                        f"New workflow task '{task.name}' is assigned to your role "
                        f"({task.assigned_role}) for dataset '{pkg['title'] or pkg['name']}'."
                    ),
                )


def _execute_transition(
    instance: WorkflowInstance,
    current_sequence: int,
    target_transition: str | dict[str, Any] | None,
    user_name: str | None,
    comment: str | None = None,
):
    target_type = "next"
    target_index = current_sequence + 1

    if isinstance(target_transition, dict):
        tt_type = target_transition.get("type")
        if tt_type == "go_to_step":
            target_type = "go_to_step"
            target_index = int(target_transition.get("step_index", current_sequence + 1))
        elif tt_type == "reject":
            target_type = "reject"
    elif isinstance(target_transition, str):
        if target_transition.startswith("step:"):
            target_type = "go_to_step"
            target_index = int(target_transition[5:])
        elif target_transition == "reject":
            target_type = "reject"

    if target_type == "reject":
        instance.status = "rejected"
        instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
        _commit()
        rebuild(instance.object_id)
        notify_owner(
            instance.object_id,
            f"Workflow was rejected. Reason: {comment or 'No comments'}",
        )
        return True, "Workflow rejected"

    total_steps = len(instance.tasks)
    if target_index >= total_steps:
        instance.status = "completed"
        instance.current_step_index = total_steps
        instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
        _commit()
        rebuild(instance.object_id)
        notify_owner(instance.object_id, "Workflow completed successfully! Dataset was published.")
        return True, "Workflow completed"

    # If jumping backward, reset intermediate tasks
    if target_index < current_sequence:
        for t in instance.tasks:
            if target_index <= t.sequence <= current_sequence:
                t.status = "pending"
                t.completed_by = None
                t.completed_at = None
                t.comments = None
    # If jumping forward, mark intermediate tasks as skipped
    elif target_index > current_sequence:
        for t in instance.tasks:
            if current_sequence < t.sequence < target_index:
                t.status = "skipped"
                t.completed_by = "system"
                t.completed_at = datetime.datetime.now(datetime.timezone.utc)

    instance.current_step_index = target_index
    instance.status = "active"
    instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
    _notify_assignees(instance.id, target_index)
    _commit()
    rebuild(instance.object_id)

    # Run next task if automated
    next_task = next((t for t in instance.tasks if t.sequence == target_index), None)
    if next_task and next_task.step_type == "automated_task":
        _execute_automated_task(instance.id, target_index)

    return True, "Workflow advanced"


def complete_task(  # noqa: PLR0911, PLR0915, C901
    instance_id: str, sequence: int, action_type: str, comment: str | None = None, user_name: str | None = None
):
    instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance or instance.status not in ["active", "overdue"]:
        return False, "Instance is not active"

    task = (
        model.Session.query(WorkflowTask)
        .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == sequence)
        .first()
    )

    if not task or task.status != "pending":
        return False, "Task is not pending"

    # Verify role permission
    if task.step_type != "automated_task":
        try:
            pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": instance.object_id})
            org_id = pkg.get("owner_org")
            if not user_has_role(user_name, org_id, task.assigned_role):
                return False, "Unauthorized to complete this step"
        except tk.ObjectNotFound:
            return False, "Failed to verify permissions due to missing package"

    actions_dict = {}
    if task.config:
        with contextlib.suppress(Exception):
            actions_dict = task.config

    if action_type == "reject":
        task.status = "rejected"
        task.completed_by = user_name
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        task.comments = comment

        # Execute rejection post actions
        _execute_post_actions(instance.object_id, actions_dict.get("on_reject", []))

        rejection_transition = actions_dict.get("on_reject_transition") or "reject"
        success, msg = _execute_transition(instance, sequence, rejection_transition, user_name, comment)
        return success, msg

    if action_type in ["branch_a", "branch_b"]:
        task.status = "completed"
        task.completed_by = user_name
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)

        # Use user-defined option label for comments
        label_key = f"{action_type}_label"
        option_label = actions_dict.get(label_key) or action_type.upper().replace("_", " ")
        task.comments = f"Selected option: {option_label}. Comment: {comment or ''}"

        # Execute branching post actions (if any)
        _execute_post_actions(instance.object_id, actions_dict.get(f"on_{action_type}", []))

        transition_key = f"{action_type}_transition"
        transition = actions_dict.get(transition_key) or "next"
        success, msg = _execute_transition(instance, sequence, transition, user_name, comment)
        return success, msg

    task.status = "completed"
    task.completed_by = user_name
    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
    task.comments = comment

    # Run completion/approval post actions
    if task.step_type == "approval":
        _execute_post_actions(instance.object_id, actions_dict.get("on_approve", []))
    else:
        _execute_post_actions(instance.object_id, actions_dict.get("on_complete", []))

    success, msg = _execute_transition(instance, sequence, "next", user_name, comment)
    return success, msg


def _execute_automated_task(instance_id: str, sequence: int):
    instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
    if not instance or instance.status not in ["active", "overdue"]:
        return

    task = (
        model.Session.query(WorkflowTask)
        .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == sequence)
        .first()
    )

    if not task or task.status != "pending" or task.step_type != "automated_task":
        return

    runner = get_automated_task_runner()

    # Build absolute callback URL
    site_url = tk.config.get("ckan.site_url", "http://localhost:5000")
    callback_url = f"{site_url.rstrip('/')}/api/action/workflow_task_complete"

    # Resolve webhook URL from task instructions (which store the task key chosen by the user)
    task_key = task.instructions or ""
    webhook_url = tk.config.get(f"ckanext.workflow.automated_task.{task_key}.webhook_url", "")

    # Fallback to direct instructions URL if it starts with http
    if not webhook_url and (task_key.startswith(("http://", "https://"))):
        webhook_url = task_key

    # Global fallback if still not found
    if not webhook_url:
        webhook_url = tk.config.get("ckan.plugins.workflow.default_webhook_url", "")

    config_dict = {
        "webhook_url": webhook_url,
        "cancel_url": tk.config.get("ckan.plugins.workflow.default_cancel_url", ""),
        "parameters": {},
    }

    # Trigger external task runner adapter
    triggered = runner.trigger_task(
        task_id=task.id, dataset_id=instance.object_id, callback_url=callback_url, config=config_dict
    )

    if triggered:
        # Task is successfully handed off to external engine.
        task.comments = "Triggered external automated execution"
        _commit()
    else:
        # Failed to trigger: immediately fail/reject the task to avoid hanging
        task.completed_by = "system"
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        task.status = "rejected"
        task.comments = "Failed to trigger external execution webhook"

        # Execute failure post actions
        actions_dict = {}
        if task.config:
            with contextlib.suppress(Exception):
                actions_dict = task.config
        _execute_post_actions(instance.object_id, actions_dict.get("on_failure", []))

        # Use transition logic for failure
        failure_transition = actions_dict.get("on_failure_transition") or "reject"
        _execute_transition(instance, sequence, failure_transition, "system", "Failed to trigger automated task")

    rebuild(instance.object_id)
