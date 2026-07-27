from __future__ import annotations


import sqlalchemy as sa
from typing import Any
import ckan.plugins.toolkit as tk
from ckan import types, model

from ckanext.workflow.model import WorkflowInstance, WorkflowDefinition, WorkflowStep
from ckanext.workflow.service import WorkflowService
from . import schema


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

    # Delete old steps
    model.Session.execute(sa.delete(WorkflowStep).where(WorkflowStep.workflow_id == wf.id))

    # Add new steps
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


def workflow_definition_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List all workflow definitions."""
    tk.check_access("workflow_definition_list", context, data_dict)
    stmt = sa.select(WorkflowDefinition)
    items = model.Session.scalars(stmt)

    return [wf.dictize() for wf in items]


def workflow_instance_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List all workflow instances."""
    tk.check_access("workflow_instance_list", context, data_dict)
    WorkflowService.check_and_update_overdue_tasks()
    instances = WorkflowService.get_all_instances()
    return [inst.dictize() for inst in instances]


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


def workflow_user_task_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List pending tasks for the logged in user."""
    tk.check_access("workflow_user_task_list", context, data_dict)
    user = context["user"]
    tasks = WorkflowService.get_user_tasks(user)

    results = []
    for item in tasks:
        results.append(
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
                    "package_id": item["instance"].package_id,
                    "status": item["instance"].status,
                    "workflow": {"id": item["instance"].workflow.id, "name": item["instance"].workflow.name},
                },
            }
        )
    return results


def workflow_user_notification_list(context: types.Context, data_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """List notifications for the logged in user."""
    tk.check_access("workflow_user_notification_list", context, data_dict)
    user = context["user"]
    notifications = WorkflowService.get_notifications(user)
    return [n.dictize() for n in notifications]


def workflow_user_notification_mark_read(context: types.Context, data_dict: dict[str, Any]) -> bool:
    """Mark all notifications as read for the logged in user."""
    tk.check_access("workflow_user_notification_mark_read", context, data_dict)
    user = context["user"]
    WorkflowService.mark_notifications_read(user)
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

    success, msg = WorkflowService.complete_task(
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
    success, msg = WorkflowService.cancel_workflow(instance_id=data_dict["id"], user_name=context["user"])
    return {"success": success, "message": msg}
