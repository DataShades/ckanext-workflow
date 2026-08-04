from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from typing_extensions import override

import ckan.lib.plugins as lib_plugins
import ckan.plugins as p
import ckan.plugins.toolkit as tk
from ckan import model, types
from ckan.common import CKANConfig

from ckanext.theming.plugin import themed_plugin

from ckanext.workflow.model import WorkflowInstance, WorkflowTask
from ckanext.workflow.service import start_workflow


@themed_plugin
@tk.blanket.cli
@tk.blanket.helpers
@tk.blanket.actions
@tk.blanket.auth_functions
@tk.blanket.blueprints
@tk.blanket.config_declarations
class WorkflowPlugin(
    p.IPackageController,
    p.IConfigurer,
    lib_plugins.DefaultPermissionLabels,
    p.SingletonPlugin,
):
    p.implements(p.IPermissionLabels)

    # IConfigurer
    @override
    def update_config(self, config: CKANConfig) -> None:
        tk.add_template_directory(config, "templates")
        tk.add_resource("assets", "workflow")

    # IPackageController
    @override
    def after_dataset_create(self, context: types.Context, pkg_dict: dict[str, Any]) -> None:
        if context.get("ignore_workflow"):
            return

        start_workflow(pkg_dict)

    @override
    def after_dataset_update(self, context: types.Context, pkg_dict: dict[str, Any]) -> None:
        if context.get("ignore_workflow"):
            return

    # IPermissionLabels
    @override
    def get_dataset_labels(self, dataset_obj: model.Package) -> list[str]:
        custom_labels = _get_dataset_labels(dataset_obj)
        if custom_labels is not None:
            return custom_labels
        return super().get_dataset_labels(dataset_obj)

    @override
    def get_user_dataset_labels(self, user_obj: model.User) -> list[str]:
        labels = list(super().get_user_dataset_labels(user_obj))
        if not user_obj or user_obj.is_anonymous:
            return labels

        # Add direct username label
        labels.append(f"user:{user_obj.name}")

        # Add organization role labels with hierarchy
        stmt = sa.select(model.Member).where(
            model.Member.table_id == user_obj.id, model.Member.table_name == "user", model.Member.state == "active"
        )

        for member in model.Session.scalars(stmt):
            role = member.capacity
            org_id = member.group_id
            labels.append(f"workflow-role:{org_id}:member")

            if role == "admin":
                labels.extend([f"workflow-role:{org_id}:admin", f"workflow-role:{org_id}:editor"])

            elif role == "editor":
                labels.append(f"workflow-role:{org_id}:editor")

        return list(set(labels))


def _get_dataset_labels(dataset_obj: model.Package) -> list[str] | None:
    """Retrieves custom permission labels for a dataset under active workflow."""
    instance = model.Session.scalar(
        sa.select(WorkflowInstance).where(
            WorkflowInstance.object_id == dataset_obj.id, WorkflowInstance.status.in_(["active", "overdue"])
        )
    )
    if not instance:
        return None

    labels = []

    # dataset creator must always be allowed to see the dataset
    if dataset_obj.creator_user_id:
        creator = model.Session.get(model.User, dataset_obj.creator_user_id)
        if creator:
            labels.append(f"user:{creator.name}")

    # get the current active task/step
    task = model.Session.scalar(
        sa.select(WorkflowTask).where(
            WorkflowTask.instance_id == instance.id, WorkflowTask.sequence == instance.current_step_index
        )
    )
    if task:
        if task.assigned_role.startswith("user:"):
            target_user = task.assigned_role[5:]
            labels.append(f"user:{target_user}")
        else:
            org_id = dataset_obj.owner_org
            if org_id:
                role = task.assigned_role
                if role == "member":
                    labels.extend(
                        [
                            f"workflow-role:{org_id}:member",
                            f"workflow-role:{org_id}:editor",
                            f"workflow-role:{org_id}:admin",
                        ]
                    )
                elif role == "editor":
                    labels.extend([f"workflow-role:{org_id}:editor", f"workflow-role:{org_id}:admin"])
                elif role == "admin":
                    labels.append(f"workflow-role:{org_id}:admin")

    return list(set(labels))
