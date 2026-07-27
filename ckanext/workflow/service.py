from __future__ import annotations

import datetime
from typing import Any
import uuid
import logging
import json
import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.model.meta import Session
from ckanext.workflow.model import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowInstance,
    WorkflowTask,
    WorkflowNotification,
)
from ckan import authz

log = logging.getLogger(__name__)


def user_has_role(user_name: str, organization_id: str, required_role: str):
    permission = {"member": "read", "editor": "create_dataset", "admin": "admin"}[required_role]
    return authz.has_user_permission_for_group_or_org(organization_id, user_name, permission)


class WorkflowService(object):
    @classmethod
    def start_workflow(cls, package_dict: dict[str, Any]):
        dataset_type = package_dict.get("type", "dataset")

        # First check specific trigger/type match
        wf = (
            Session.query(WorkflowDefinition)
            .filter(WorkflowDefinition.enabled == True, WorkflowDefinition.dataset_type == dataset_type)
            .first()
        )

        if not wf:
            # Fall back to default trigger on all datasets
            wf = (
                Session.query(WorkflowDefinition)
                .filter(WorkflowDefinition.enabled == True, WorkflowDefinition.dataset_type == "all")
                .first()
            )

        if not wf or not wf.steps:
            return None

        # Check if an instance already exists for this package to avoid duplicates
        existing = (
            Session.query(WorkflowInstance)
            .filter(
                WorkflowInstance.package_id == package_dict["id"], WorkflowInstance.status.in_(["active", "overdue"])
            )
            .first()
        )
        if existing:
            return existing

        instance_id = str(uuid.uuid4())
        wf_inst = WorkflowInstance(
            id=instance_id,
            package_id=package_dict["id"],
            workflow_id=wf.id,
            current_step_index=0,
            status="active",
            started_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        Session.add(wf_inst)

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
            Session.add(task)

        Session.commit()

        # Set dataset state to draft
        cls._set_dataset_state(package_dict["id"], "draft")

        # If the first step is automated, run it recursively. Else notify assignees.
        first_step = wf.steps[0]
        if first_step.step_type == "automated_task":
            cls.execute_automated_task(wf_inst.id, 0)
        else:
            cls._notify_assignees(wf_inst.id, 0)

        return wf_inst

    @classmethod
    def execute_post_actions(cls, package_id: str, actions_list: list[dict[str, Any]]):
        if not actions_list:
            return
        for action in actions_list:
            action_type = action.get("type")
            if action_type == "change_field":
                field_name = action.get("field")
                value = action.get("value")
                if field_name:
                    cls._set_dataset_field(package_id, field_name, value)
            elif action_type == "send_notification":
                recipient = action.get("recipient")
                message = action.get("message")
                if recipient and message:
                    cls._send_notification_to_recipient(package_id, recipient, message)

    @classmethod
    def _set_dataset_field(cls, package_id: str, field_name: str, value: Any):
        user = tk.get_action("get_site_user")({"ignore_auth": True}, {})
        tk.get_action("package_patch")(
            {"ignore_auth": True, "user": user["name"], "ignore_workflow": True},
            {"id": package_id, field_name: value},
        )

    @classmethod
    def _send_notification_to_recipient(cls, package_id: str, recipient: str, message: str):
        pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": package_id})
        org_id = pkg.get("owner_org")

        if recipient == "owner":
            creator = pkg.get("creator_user_id")
            if creator:
                cls.add_notification(creator, message)
        elif recipient == "admin":
            users = Session.query(model.User).filter(model.User.sysadmin == True).all()
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
        instance = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance or instance.status not in ["active", "overdue"]:
            return

        task = (
            Session.query(WorkflowTask)
            .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == sequence)
            .first()
        )

        if not task or task.status != "pending" or task.step_type != "automated_task":
            return

        instructions = (task.instructions or "").lower()
        success = "fail" not in instructions

        task.completed_by = "system"
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)

        actions_dict = {}
        if task.post_actions:
            actions_dict = json.loads(task.post_actions)

        if success:
            task.status = "completed"
            Session.flush()

            # Run success post actions
            cls.execute_post_actions(instance.package_id, actions_dict.get("on_success"))

            next_step_index = sequence + 1
            total_steps = len(instance.tasks)

            if next_step_index >= total_steps:
                instance.status = "completed"
                instance.current_step_index = total_steps
                instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
                cls._set_dataset_state(instance.package_id, "active")
                cls._notify_owner(instance.package_id, "Workflow completed successfully! Dataset was published.")
                Session.commit()
            else:
                instance.current_step_index = next_step_index
                instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
                cls._notify_assignees(instance_id, next_step_index)
                Session.commit()

                # Run next step recursively if automated
                next_task = (
                    Session.query(WorkflowTask)
                    .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == next_step_index)
                    .first()
                )
                if next_task and next_task.step_type == "automated_task":
                    cls.execute_automated_task(instance_id, next_step_index)
        else:
            task.status = "rejected"
            instance.status = "rejected"
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
            Session.flush()

            # Run failure post actions
            cls.execute_post_actions(instance.package_id, actions_dict.get("on_failure"))

            cls._set_dataset_state(instance.package_id, "draft")
            cls._notify_owner(instance.package_id, f"Automated workflow step '{task.name}' failed.")
            Session.commit()

    @classmethod
    def _set_dataset_state(cls, package_id: str, state: str):
        user = tk.get_action("get_site_user")({"ignore_auth": True}, {})

        tk.get_action("package_patch")(
            {"ignore_auth": True, "user": user["name"], "ignore_workflow": True}, {"id": package_id, "state": state}
        )

    @classmethod
    def get_instance_for_package(cls, package_id: str):
        return (
            Session.query(WorkflowInstance)
            .filter(WorkflowInstance.package_id == package_id, WorkflowInstance.status.in_(["active", "overdue"]))
            .first()
        )

    @classmethod
    def get_all_instances(cls):
        return Session.query(WorkflowInstance).order_by(WorkflowInstance.started_at.desc()).all()

    @classmethod
    def get_user_tasks(cls, user_name: str) -> list[dict[str, Any]]:
        if not user_name:
            return []

        pending_tasks = (
            Session.query(WorkflowTask)
            .join(WorkflowInstance)
            .filter(WorkflowTask.status == "pending", WorkflowInstance.status.in_(["active", "overdue"]))
            .all()
        )

        user_tasks: list[dict[str, Any]] = []
        for task in pending_tasks:
            if task.sequence != task.instance.current_step_index:
                continue

            package_id = task.instance.package_id
            try:
                pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": package_id})
                org_id = pkg.get("owner_org")
                if user_has_role(user_name, org_id, task.assigned_role):
                    user_tasks.append({"task": task, "package": pkg, "instance": task.instance})
            except Exception as e:
                log.error("Error retrieving package for user task: %s", e)
        return user_tasks

    @classmethod
    def complete_task(
        cls, instance_id: int, sequence: int, action_type: str, comment: str | None = None, user_name: str | None = None
    ):
        instance = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance or instance.status not in ["active", "overdue"]:
            return False, "Instance is not active"

        task = (
            Session.query(WorkflowTask)
            .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == sequence)
            .first()
        )

        if not task or task.status != "pending":
            return False, "Task is not pending"

        # Verify role permission
        try:
            pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": instance.package_id})
            org_id = pkg.get("owner_org")
            if not user_has_role(user_name, org_id, task.assigned_role):
                return False, "Unauthorized to complete this step"
        except Exception as e:
            return False, f"Failed to verify permissions: {e}"

        actions_dict = {}
        if task.post_actions:
            try:
                actions_dict = json.loads(task.post_actions)
            except Exception:
                pass

        if action_type == "reject":
            task.status = "rejected"
            task.completed_by = user_name
            task.completed_at = datetime.datetime.now(datetime.timezone.utc)
            task.comments = comment

            instance.status = "rejected"
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)

            # Execute rejection post actions
            cls.execute_post_actions(instance.package_id, actions_dict.get("on_reject"))

            cls._set_dataset_state(instance.package_id, "draft")
            cls._notify_owner(
                instance.package_id,
                f"Workflow task '{task.name}' was rejected by {user_name}. Reason: {comment or 'No comments'}",
            )
            Session.commit()
            return True, "Workflow rejected"

        task.status = "completed"
        task.completed_by = user_name
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        task.comments = comment

        # Run completion/approval post actions
        if task.step_type == "approval":
            cls.execute_post_actions(instance.package_id, actions_dict.get("on_approve"))
        else:
            cls.execute_post_actions(instance.package_id, actions_dict.get("on_complete"))

        next_step_index = sequence + 1
        total_steps = len(instance.tasks)

        if next_step_index >= total_steps:
            instance.status = "completed"
            instance.current_step_index = total_steps
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
            cls._set_dataset_state(instance.package_id, "active")
            cls._notify_owner(instance.package_id, "Workflow completed successfully! Dataset was published.")
            Session.commit()
            return True, "Workflow completed"
        else:
            instance.current_step_index = next_step_index
            instance.status = "active"
            instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
            cls._notify_assignees(instance_id, next_step_index)
            Session.commit()

            # Run next step recursively if automated
            next_task = (
                Session.query(WorkflowTask)
                .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == next_step_index)
                .first()
            )
            if next_task and next_task.step_type == "automated_task":
                cls.execute_automated_task(instance_id, next_step_index)

            return True, "Task completed, workflow advanced"

    @classmethod
    def cancel_workflow(cls, instance_id: int, user_name: str | None = None):
        instance = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        if not instance or instance.status not in ["active", "overdue"]:
            return False, "Instance is not active"

        instance.status = "cancelled"
        instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
        cls._set_dataset_state(instance.package_id, "draft")
        cls._notify_owner(instance.package_id, f"Workflow was cancelled by {user_name}.")
        Session.commit()
        return True, "Workflow cancelled"

    @classmethod
    def check_and_update_overdue_tasks(cls):
        now = datetime.datetime.now(datetime.timezone.utc)
        instances = Session.query(WorkflowInstance).filter(WorkflowInstance.status.in_(["active", "overdue"])).all()
        for inst in instances:
            current_task = (
                Session.query(WorkflowTask)
                .filter(WorkflowTask.instance_id == inst.id, WorkflowTask.sequence == inst.current_step_index)
                .first()
            )
            if not current_task:
                continue

            start_time = inst.started_at
            if current_task.sequence > 0:
                prev_task = (
                    Session.query(WorkflowTask)
                    .filter(WorkflowTask.instance_id == inst.id, WorkflowTask.sequence == current_task.sequence - 1)
                    .first()
                )
                if prev_task and prev_task.completed_at:
                    start_time = prev_task.completed_at

            step_def = (
                Session.query(WorkflowStep)
                .filter(WorkflowStep.workflow_id == inst.workflow_id, WorkflowStep.sequence == current_task.sequence)
                .first()
            )

            if step_def and step_def.timeout_duration:
                elapsed = (now - start_time).total_seconds()
                if elapsed > step_def.timeout_duration:
                    if inst.status != "overdue":
                        inst.status = "overdue"
                        inst.updated_at = now
                        cls._notify_admin(
                            inst.id, f"Workflow for dataset {inst.package_id} is OVERDUE at step: {current_task.name}"
                        )
        Session.commit()

    @classmethod
    def _notify_assignees(cls, instance_id: int, step_sequence: int):
        instance = Session.query(WorkflowInstance).filter(WorkflowInstance.id == instance_id).first()
        task = (
            Session.query(WorkflowTask)
            .filter(WorkflowTask.instance_id == instance_id, WorkflowTask.sequence == step_sequence)
            .first()
        )
        if not instance or not task:
            return

        try:
            pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": instance.package_id})
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
                            f"New workflow task '{task.name}' is assigned to your role ({task.assigned_role}) for dataset '{pkg['title'] or pkg['name']}'.",
                        )
        except Exception as e:
            log.error("Failed to notify assignees: %s", e)

    @classmethod
    def _notify_owner(cls, package_id: str, message: str):
        try:
            pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": package_id})
            creator = pkg.get("creator_user_id")
            if creator:
                cls.add_notification(creator, message)
        except Exception as e:
            log.error("Failed to notify owner: %s", e)

    @classmethod
    def _notify_admin(cls, instance_id: str, message: str):
        users = Session.query(model.User).filter(model.User.sysadmin == True).all()
        for user in users:
            cls.add_notification(user.name, message)

    @classmethod
    def add_notification(cls, user_name: str, message: str):
        notification = WorkflowNotification(user_name=user_name, message=message, read=False)
        Session.add(notification)
        Session.commit()

    @classmethod
    def get_notifications(cls, user_name: str, unread_only: bool = True):
        q = Session.query(WorkflowNotification).filter(WorkflowNotification.user_name == user_name)
        if unread_only:
            q = q.filter(WorkflowNotification.read == False)
        return q.order_by(WorkflowNotification.created_at.desc()).all()

    @classmethod
    def mark_notifications_read(cls, user_name: str):
        Session.query(WorkflowNotification).filter(
            WorkflowNotification.user_name == user_name, WorkflowNotification.read == False
        ).update({WorkflowNotification.read: True}, synchronize_session=False)
        Session.commit()
