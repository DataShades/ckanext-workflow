from __future__ import annotations

import datetime
import logging
from typing import Any

import sqlalchemy as sa

import ckan.plugins.toolkit as tk
from ckan import model, types
from ckan.lib.search import rebuild

from ckanext.workflow.model import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowNotification,
    WorkflowStep,
    WorkflowTask,
)
from ckanext.workflow.service import add_notification, complete_task, notify_owner, user_has_role

from . import schema

log = logging.getLogger(__name__)


@tk.validate_action_data(schema.workflow_definition_create)
def workflow_definition_create(context: types.Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Create a new workflow definition.

    :param name: Name of the workflow
    :param description: Optional description of the workflow
    :param enabled: Enable/disable the workflow. Defaults to True.
    :param trigger_type: Trigger type, defaults to "dataset_create"
    :param dataset_type: Dataset trigger type, defaults to "all"
    :param steps: Optional list of step configuration dicts
    """
    tk.check_access("workflow_definition_create", context, data_dict)

    wf = WorkflowDefinition(
        name=data_dict["name"],
        description=data_dict.get("description"),
        enabled=data_dict["enabled"],
        trigger_type=data_dict["trigger_type"],
        dataset_type=data_dict["dataset_type"],
        metadata_template=None,
    )
    model.Session.add(wf)
    model.Session.flush()

    for idx, step_data in enumerate(data_dict.get("steps", [])):
        step = WorkflowStep(
            workflow_id=wf.id,
            sequence=idx,
            name=step_data["name"],
            assigned_role=step_data["assigned_role"],
            step_type=step_data["step_type"],
            instructions=step_data.get("instructions"),
            post_actions=step_data["post_actions"],
        )
        model.Session.add(step)

    model.Session.commit()

    return wf.dictize()


@tk.validate_action_data(schema.workflow_definition_update)
def workflow_definition_update(context: types.Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Update an existing workflow definition.

    :param id: Numeric workflow definition ID
    :param name: Name of the workflow
    :param description: Optional description of the workflow
    :param enabled: Optional boolean to enable/disable the workflow. Defaults to True.
    :param trigger_type: Trigger type
    :param dataset_type: Dataset trigger type
    :param steps: Optional list of step configuration dicts
    """
    tk.check_access("workflow_definition_update", context, data_dict)

    wf = model.Session.get(WorkflowDefinition, data_dict["id"])
    if not wf:
        raise tk.ObjectNotFound("workflow_definition")

    wf.name = data_dict["name"]
    wf.description = data_dict.get("description")
    wf.enabled = data_dict["enabled"]
    wf.trigger_type = data_dict["trigger_type"]
    wf.dataset_type = data_dict["dataset_type"]
    wf.metadata_template = None

    # delete old steps
    model.Session.execute(sa.delete(WorkflowStep).where(WorkflowStep.workflow_id == wf.id))

    # add new steps
    for idx, step_data in enumerate(data_dict.get("steps", [])):
        step = WorkflowStep(
            workflow_id=wf.id,
            sequence=idx,
            name=step_data["name"],
            assigned_role=step_data["assigned_role"],
            step_type=step_data["step_type"],
            instructions=step_data.get("instructions"),
            post_actions=step_data["post_actions"],
        )
        model.Session.add(step)
    model.Session.flush()

    # synchronize all active/overdue instances of this workflow
    stmt = sa.select(WorkflowInstance).where(
        WorkflowInstance.workflow_id == wf.id, WorkflowInstance.status.in_(["active", "overdue"])
    )
    for inst in context["session"].scalars(stmt):
        _sync_instance_tasks(inst)

    model.Session.commit()

    return wf.dictize()


def _sync_instance_tasks(instance: WorkflowInstance):
    """Synchronizes task rows of the instance to match the workflow definition steps."""
    if not instance or not instance.workflow:
        return

    steps = instance.workflow.steps
    steps_count = len(steps)
    tasks = instance.tasks
    tasks_count = len(tasks)

    if tasks_count < steps_count:
        # Create missing tasks using the step values as fallback/initial data
        for i in range(tasks_count, steps_count):
            step = steps[i]
            task = WorkflowTask(
                instance_id=instance.id,
                sequence=i,
                name=step.name,
                assigned_role=step.assigned_role,
                step_type=step.step_type,
                instructions=step.instructions,
                post_actions=step.post_actions,
                status="pending",
            )
            model.Session.add(task)
        model.Session.flush()
    elif tasks_count > steps_count:
        # Delete extra tasks that haven't been completed
        for task in list(instance.tasks):
            if task.sequence >= steps_count and task.status == "pending":
                model.Session.delete(task)
        model.Session.flush()


@tk.side_effect_free
@tk.validate_action_data(schema.workflow_definition_show)
def workflow_definition_show(context: types.Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Show details of a workflow definition.

    :param id: Numeric workflow definition ID
    """
    tk.check_access("workflow_definition_show", context, data_dict)
    wf = model.Session.get(WorkflowDefinition, data_dict["id"])

    if not wf:
        raise tk.ObjectNotFound("workflow_definition")
    return wf.dictize()


@tk.validate_action_data(schema.workflow_definition_delete)
def workflow_definition_delete(context: types.Context, data_dict: dict[str, Any]) -> bool:
    """Delete a workflow definition.

    :param id: Numeric workflow definition ID
    """
    tk.check_access("workflow_definition_delete", context, data_dict)
    if wf := model.Session.get(WorkflowDefinition, data_dict["id"]):
        model.Session.delete(wf)
        model.Session.commit()
        return True
    raise tk.ObjectNotFound("workflow_definition")


@tk.side_effect_free
def workflow_definition_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List all workflow definitions."""
    tk.check_access("workflow_definition_list", context, data_dict)
    stmt = sa.select(WorkflowDefinition)
    items = model.Session.scalars(stmt)

    return [wf.dictize() for wf in items]


@tk.side_effect_free
def workflow_instance_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List all workflow instances."""
    tk.check_access("workflow_instance_list", context, data_dict)

    if False:
        _check_and_update_overdue_tasks(context["session"])  # pyright: ignore[reportUnreachable]

    stmt = sa.select(WorkflowInstance).order_by(WorkflowInstance.started_at.desc())
    instances = context["session"].scalars(stmt)
    return [inst.dictize() for inst in instances]


def _check_and_update_overdue_tasks(session: types.AlchemySession):
    now = datetime.datetime.now(datetime.timezone.utc)
    instances = session.scalars(sa.select(WorkflowInstance).where(WorkflowInstance.status.in_(["active", "overdue"])))
    has_overdue = False

    for inst in instances:
        current_task = session.scalar(
            sa.select(WorkflowTask).where(
                WorkflowTask.instance_id == inst.id, WorkflowTask.sequence == inst.current_step_index
            )
        )
        if not current_task:
            continue

        start_time = inst.started_at
        if current_task.sequence > 0:
            prev_task = session.scalar(
                sa.select(WorkflowTask).where(
                    WorkflowTask.instance_id == inst.id, WorkflowTask.sequence == current_task.sequence - 1
                )
            )
            if prev_task and prev_task.completed_at:
                start_time = prev_task.completed_at

        step_def = session.scalar(
            sa.select(WorkflowStep).where(
                WorkflowStep.workflow_id == inst.workflow_id, WorkflowStep.sequence == current_task.sequence
            )
        )

        if step_def and step_def.timeout_duration:
            elapsed = (now - start_time).total_seconds()
            if elapsed > step_def.timeout_duration and inst.status != "overdue":
                has_overdue = True
                inst.status = "overdue"
                inst.updated_at = now
                _notify_admin(f"Workflow for dataset {inst.object_id} is OVERDUE at step: {current_task.name}")

    if has_overdue:
        session.commit()


def _notify_admin(message: str):
    users = model.Session.query(model.User).filter(model.User.sysadmin == True).all()
    for user in users:
        add_notification(user.name, message)


@tk.side_effect_free
@tk.validate_action_data(schema.workflow_instance_show)
def workflow_instance_show(context: types.Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Show details of a workflow instance.

    :param id: Workflow instance UUID
    """
    tk.check_access("workflow_instance_show", context, data_dict)
    inst = model.Session.get(WorkflowInstance, data_dict["id"])
    if not inst:
        raise tk.ObjectNotFound("workflow_instance")
    return inst.dictize()


@tk.side_effect_free
def workflow_user_task_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List pending tasks for the logged in user."""
    tk.check_access("workflow_user_task_list", context, data_dict)

    pending_tasks = (
        model.Session.query(WorkflowTask)
        .join(WorkflowInstance)
        .filter(WorkflowTask.status == "pending", WorkflowInstance.status.in_(["active", "overdue"]))
        .all()
    )

    tasks: list[dict[str, Any]] = []
    for task in pending_tasks:
        if task.sequence != task.instance.current_step_index:
            continue

        object_id = task.instance.object_id
        try:
            pkg = tk.get_action("package_show")({"ignore_auth": True}, {"id": object_id})
            org_id = pkg.get("owner_org")
            if user_has_role(context["user"], org_id, task.assigned_role):
                tasks.append({"task": task, "package": pkg, "instance": task.instance})
        except Exception:
            log.exception("Error retrieving package for user task")

    results: list[dict[str, Any]] = [
        {
            "task": {
                "id": item["task"].id,
                "sequence": item["task"].sequence,
                "name": item["task"].name,
                "assigned_role": item["task"].assigned_role,
                "step_type": item["task"].step_type,
                "instructions": item["task"].instructions,
                "status": item["task"].status,
            },
            "package": item["package"],
            "instance": {
                "id": item["instance"].id,
                "object_id": item["instance"].object_id,
                "status": item["instance"].status,
                "workflow": {"id": item["instance"].workflow.id, "name": item["instance"].workflow.name},
            },
        }
        for item in tasks
    ]
    return results


@tk.side_effect_free
def workflow_user_notification_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List notifications for the logged in user."""
    tk.check_access("workflow_user_notification_list", context, data_dict)

    stmt = (
        sa.select(WorkflowNotification)
        .where(WorkflowNotification.user_name == context["user"], WorkflowNotification.read == sa.false())
        .order_by(WorkflowNotification.created_at.desc())
    )

    return [n.dictize() for n in context["session"].scalars(stmt)]


def workflow_user_notification_mark_read(context: types.Context, data_dict: dict[str, Any]) -> bool:
    """Mark all notifications as read for the logged in user."""
    tk.check_access("workflow_user_notification_mark_read", context, data_dict)
    stmt = (
        sa.update(WorkflowNotification)
        .where(WorkflowNotification.user_name == tk.current_user.name, WorkflowNotification.read == False)
        .values({WorkflowNotification.read: True})
    )
    model.Session.execute(stmt)
    model.Session.commit()

    return True


@tk.validate_action_data(schema.workflow_task_complete)
def workflow_task_complete(context: types.Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Approve, reject, or complete a workflow step task.

    :param id: Workflow instance UUID
    :param sequence: Task sequence number
    :param action_type: Action type ('approve', 'reject', 'complete')
    :param comment: Optional comment/notes
    """
    tk.check_access("workflow_task_complete", context, data_dict)

    success, msg = complete_task(
        instance_id=data_dict["id"],
        sequence=data_dict["sequence"],
        action_type=data_dict["action_type"],
        comment=data_dict.get("comment"),
        user_name=context["user"],
    )
    return {"success": success, "message": msg}


@tk.validate_action_data(schema.workflow_instance_cancel)
def workflow_instance_cancel(context: types.Context, data_dict: dict[str, Any]) -> dict[str, Any]:
    """Cancel a running workflow instance.

    :param id: Workflow instance UUID
    """
    tk.check_access("workflow_instance_cancel", context, data_dict)

    stmt = sa.select(WorkflowInstance).where(WorkflowInstance.id == data_dict["id"])
    instance = context["session"].scalar(stmt)
    if not instance or instance.status not in ["active", "overdue"]:
        return {"success": False, "message": "Instance is not active"}

    instance.status = "cancelled"
    instance.updated_at = datetime.datetime.now(datetime.timezone.utc)
    model.Session.commit()
    rebuild(instance.object_id)

    notify_owner(instance.object_id, f"Workflow was cancelled by {context['user']}.")

    return {"success": True, "message": "Workflow cancelled"}
