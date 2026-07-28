from __future__ import annotations

import contextlib
import datetime
import logging
import uuid
from typing import Any

import sqlalchemy as sa

import ckan.plugins.toolkit as tk
from ckan import authz, model

from ckanext.workflow.model import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowNotification,
    WorkflowTask,
)

log = logging.getLogger(__name__)


def user_has_role(user_name: str | None, organization_id: str, required_role: str):
    permission = {"member": "read", "editor": "create_dataset", "admin": "admin"}[required_role]
    return authz.has_user_permission_for_group_or_org(organization_id, user_name, permission)


def start_workflow(package_dict: dict[str, Any]):
    dataset_type = package_dict.get("type", "dataset")
    # First check specific trigger/type match

    wf = model.Session.scalar(
        sa.select(WorkflowDefinition).where(
            WorkflowDefinition.enabled == sa.true(), WorkflowDefinition.dataset_type == dataset_type
        )
    )

    if not wf:
        # Fall back to default trigger on all datasets
        wf = model.Session.scalar(
            sa.select(WorkflowDefinition).where(
                WorkflowDefinition.enabled == sa.true(), WorkflowDefinition.dataset_type == "all"
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
            post_actions=step.post_actions,
        )
        model.Session.add(task)

    model.Session.commit()

    # Set dataset state to draft
    WorkflowService._set_dataset_state(package_dict["id"], "draft")  # pyright: ignore[reportPrivateUsage]

    # If the first step is automated, run it recursively. Else notify assignees.
    first_step = wf.steps[0]
    if first_step.step_type == "automated_task":
        WorkflowService.execute_automated_task(wf_inst.id, 0)
    else:
        WorkflowService._notify_assignees(wf_inst.id, 0)  # pyright: ignore[reportPrivateUsage]

    return wf_inst


class WorkflowService:
    @classmethod
    def execute_post_actions(cls, object_id: str, actions_list: list[dict[str, Any]]):
        if not actions_list:
            return
        for action in actions_list:
            action_type = action.get("type")
            if action_type == "change_field":
                field_name = action.get("field")
                value = action.get("value")
                if field_name:
                    cls._set_dataset_field(object_id, field_name, value)
            elif action_type == "send_notification":
                recipient = action.get("recipient")
                message = action.get("message")
                if recipient and message:
                    cls._send_notification_to_recipient(object_id, recipient, message)

    @classmethod
    def _set_dataset_field(cls, object_id: str, field_name: str, value: Any):
        user = tk.get_action("get_site_user")({"ignore_auth": True}, {})
        tk.get_action("package_patch")(
            {"ignore_auth": True, "user": user["name"], "ignore_workflow": True},
            {"id": object_id, field_name: value},
        )

    @classmethod
    def _send_notification_to_recipient(cls, object_id: str, recipient: str, message: str):
        pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": object_id})
        org_id = pkg.get("owner_org")

        if recipient == "owner":
            creator = pkg.get("creator_user_id")
            if creator:
                cls.add_notification(creator, message)
        elif recipient == "admin":
            users = model.Session.query(model.User).filter(model.User.sysadmin == True).all()
            for u in users:
                cls.add_notification(u.name, message)
        elif recipient in ["member", "editor", "admin_role"]:
            role_name = "admin" if recipient == "admin_role" else recipient
            if org_id:
                org = tk.get_action("organization_show")({"ignore_auth": True}, {"id": org_id, "include_users": True})
                for u in org.get("users", []):
                    if u.get("capacity") == role_name:
                        cls.add_notification(u["name"], message)
        else:
            # Direct username
            cls.add_notification(recipient, message)

    @classmethod
    def execute_automated_task(cls, instance_id: str, sequence: int):
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

        from ckanext.workflow.adapters import get_automated_task_runner
        runner = get_automated_task_runner()

        # Build absolute callback URL
        site_url = tk.config.get("ckan.site_url", "http://localhost:5000")
        callback_url = f"{site_url.rstrip('/')}/api/action/workflow_task_complete"

        # Prepare parameters / config
        webhook_url = task.instructions or ""
        # If instructions doesn't look like a URL, use a default fallback from config
        if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
            webhook_url = tk.config.get("ckan.plugins.workflow.default_webhook_url", "")

        config_dict = {
            "webhook_url": webhook_url,
            "cancel_url": tk.config.get("ckan.plugins.workflow.default_cancel_url", ""),
            "parameters": {}
        }

        # Trigger external task runner adapter
        triggered = runner.trigger_task(
            task_id=task.id,
            dataset_id=instance.object_id,
            callback_url=callback_url,
            config=config_dict
        )

        if triggered:
            # Task is successfully handed off to external engine.
            task.comments = "Triggered external automated execution"
            model.Session.commit()
        else:
            # Failed to trigger: immediately fail/reject the task to avoid hanging
            task.completed_by = "system"
            task.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.status = "rejected"
            task.comments = "Failed to trigger external execution webhook"
            instance.status = "rejected"
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
            
            # Execute failure post actions
            actions_dict = {}
            if task.post_actions:
                import contextlib
                with contextlib.suppress(Exception):
                    actions_dict = task.post_actions
            cls.execute_post_actions(instance.object_id, actions_dict.get("on_failure", []))
            
            cls._set_dataset_state(instance.object_id, "draft")
            cls._notify_owner(instance.object_id, f"Automated workflow step '{task.name}' failed to trigger.")
            model.Session.commit()


    @classmethod
    def _set_dataset_state(cls, object_id: str, state: str):
        user = tk.get_action("get_site_user")({"ignore_auth": True}, {})

        tk.get_action("package_patch")(
            {"ignore_auth": True, "user": user["name"], "ignore_workflow": True}, {"id": object_id, "state": state}
        )

    @classmethod
    def get_instance_for_package(cls, object_id: str):
        return (
            model.Session.query(WorkflowInstance)
            .filter(WorkflowInstance.object_id == object_id, WorkflowInstance.status.in_(["active", "overdue"]))
            .first()
        )

    @classmethod
    def get_user_tasks(cls, user_name: str) -> list[dict[str, Any]]:
        if not user_name:
            return []

        pending_tasks = (
            model.Session.query(WorkflowTask)
            .join(WorkflowInstance)
            .filter(WorkflowTask.status == "pending", WorkflowInstance.status.in_(["active", "overdue"]))
            .all()
        )

        user_tasks: list[dict[str, Any]] = []
        for task in pending_tasks:
            if task.sequence != task.instance.current_step_index:
                continue

            object_id = task.instance.object_id
            try:
                pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": object_id})
                org_id = pkg.get("owner_org")
                if user_has_role(user_name, org_id, task.assigned_role):
                    user_tasks.append({"task": task, "package": pkg, "instance": task.instance})
            except Exception:
                log.exception("Error retrieving package for user task")
        return user_tasks

    @classmethod
    def complete_task(  # noqa: PLR0911
        cls, instance_id: str, sequence: int, action_type: str, comment: str | None = None, user_name: str | None = None
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
        if task.post_actions:
            with contextlib.suppress(Exception):
                actions_dict = task.post_actions

        if action_type == "reject":
            task.status = "rejected"
            task.completed_by = user_name
            task.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.comments = comment

            instance.status = "rejected"
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)

            # Execute rejection post actions
            cls.execute_post_actions(instance.object_id, actions_dict.get("on_reject", []))

            cls._set_dataset_state(instance.object_id, "draft")
            cls._notify_owner(
                instance.object_id,
                f"Workflow task '{task.name}' was rejected by {user_name}. Reason: {comment or 'No comments'}",
            )
            model.Session.commit()
            return True, "Workflow rejected"

        task.status = "completed"
        task.completed_by = user_name
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        task.comments = comment

        # Run completion/approval post actions
        if task.step_type == "approval":
            cls.execute_post_actions(instance.object_id, actions_dict.get("on_approve", []))
        else:
            cls.execute_post_actions(instance.object_id, actions_dict.get("on_complete", []))

        next_step_index = sequence + 1
        total_steps = len(instance.tasks)

        if next_step_index >= total_steps:
            instance.status = "completed"
            instance.current_step_index = total_steps
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
            cls._set_dataset_state(instance.object_id, "active")
            cls._notify_owner(instance.object_id, "Workflow completed successfully! Dataset was published.")
            model.Session.commit()
            return True, "Workflow completed"
        instance.current_step_index = next_step_index
        instance.status = "active"
        instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
        cls._notify_assignees(instance_id, next_step_index)
        model.Session.commit()

        # Run next step recursively if automated
        next_task = (
            model.Session.query(WorkflowTask)
            .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == next_step_index)
            .first()
        )
        if next_task and next_task.step_type == "automated_task":
            cls.execute_automated_task(instance_id, next_step_index)

        return True, "Task completed, workflow advanced"

    @classmethod
    def cancel_workflow(cls, instance_id: int, user_name: str | None = None):
        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance or instance.status not in ["active", "overdue"]:
            return False, "Instance is not active"

        instance.status = "cancelled"
        instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
        cls._set_dataset_state(instance.object_id, "draft")
        cls._notify_owner(instance.object_id, f"Workflow was cancelled by {user_name}.")
        model.Session.commit()
        return True, "Workflow cancelled"

    @classmethod
    def _notify_assignees(cls, instance_id: str, step_sequence: int):
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
            org_id = pkg.get("owner_org")
            if org_id:
                org = tk.get_action("organization_show")({"ignore_auth": True}, {"id": org_id, "include_users": True})
                for user in org.get("users", []):
                    user_role = user.get("capacity")
                    role_hierarchy = {"member": 1, "editor": 2, "admin": 3}
                    req_level = role_hierarchy.get(task.assigned_role, 0)
                    user_level = role_hierarchy.get(user_role, 0)
                    if user_level >= req_level or user.get("sysadmin"):
                        cls.add_notification(
                            user["name"],
                            (
                                f"New workflow task '{task.name}' is assigned to your role "
                                f"({task.assigned_role}) for dataset '{pkg['title'] or pkg['name']}'."
                            ),
                        )
        except Exception:
            log.exception("Failed to notify assignees")

    @classmethod
    def _notify_owner(cls, object_id: str, message: str):
        try:
            pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": object_id})
            creator = pkg.get("creator_user_id")
            if creator:
                cls.add_notification(creator, message)
        except Exception:
            log.exception("Failed to notify owner")

    @classmethod
    def add_notification(cls, user_name: str, message: str):
        notification = WorkflowNotification(user_name=user_name, message=message, read=False)
        model.Session.add(notification)
        model.Session.commit()

    @classmethod
    def get_notifications(cls, user_name: str, unread_only: bool = True):
        q = model.Session.query(WorkflowNotification).filter(WorkflowNotification.user_name == user_name)
        if unread_only:
            q = q.filter(WorkflowNotification.read == False)
        return q.order_by(WorkflowNotification.created_at.desc()).all()

    @classmethod
    def mark_notifications_read(cls, user_name: str):
        model.Session.query(WorkflowNotification).filter(
            WorkflowNotification.user_name == user_name, WorkflowNotification.read == False
        ).update({WorkflowNotification.read: True}, synchronize_session=False)
        model.Session.commit()
