from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from flask import Blueprint, request
from flask.views import MethodView

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.lib.navl.dictization_functions import unflatten
from ckan.logic import parse_params, tuplize_dict

from ckanext.workflow.model import WorkflowInstance
from ckanext.workflow.service import start_workflow, user_has_role

blueprint = Blueprint("workflow", __name__, template_folder="templates")


@blueprint.errorhandler(tk.ObjectNotFound)
def not_found_handler(error: tk.ObjectNotFound) -> tuple[str, int]:
    """Generic handler for ObjectNotFound exception."""
    return (
        tk.render(
            "error_document_template.html",
            {
                "code": 404,
                "content": f"Object not found: {error.message}",
                "name": "Not found",
            },
        ),
        404,
    )


@blueprint.errorhandler(tk.NotAuthorized)
def not_authorized_handler(error: tk.NotAuthorized) -> tuple[str, int]:
    """Generic handler for NotAuthorized exception."""
    return (
        tk.render(
            "error_document_template.html",
            {
                "code": 403,
                "content": error.message or "Not authorized to view this page",
                "name": "Not authorized",
            },
        ),
        403,
    )


@blueprint.route("/ckan-admin/workflows")
def list_definitions():
    workflows = tk.get_action("workflow_definition_list")({}, {})
    return tk.render("workflow/admin/list.html", {"workflows": workflows})


class CreateDefinition(MethodView):
    def get(self):
        tk.check_access("workflow_definition_create", {})
        return tk.render("workflow/admin/edit.html", {"workflow": None, "has_active_instances": False})

    def post(self):
        workflow = unflatten(tuplize_dict(parse_params(request.form)))

        try:
            tk.get_action("workflow_definition_create")(
                {},
                workflow,
            )
        except tk.ValidationError as err:
            extra_vars = {
                "error_summary": err.error_summary,
                "workflow": workflow,
                "has_active_instances": False,
            }

            return tk.render("workflow/admin/edit.html", extra_vars)

        return tk.redirect_to(tk.url_for("workflow.list_definitions"))


blueprint.add_url_rule("/ckan-admin/workflow/new", view_func=CreateDefinition.as_view("create_definition"))


class EditDefinition(MethodView):
    def _has_instances(self, workflow_id: int) -> bool:
        stmt = sa.exists().where(
            WorkflowInstance.workflow_id == workflow_id, WorkflowInstance.status.in_(["active", "overdue"])
        )

        return model.Session.scalar(sa.select(stmt)) or False

    def post(self, workflow_id: int):
        data_dict = unflatten(tuplize_dict(parse_params(request.form)))

        try:
            tk.get_action("workflow_definition_update")(
                {},
                dict(data_dict, id=workflow_id),
            )
        except tk.ValidationError as err:
            extra_vars = {
                "error_summary": err.error_summary,
                "workflow": tk.get_action("workflow_definition_show")({}, {"id": workflow_id}),
                "has_active_instances": self._has_instances(workflow_id),
            }
            return tk.render("workflow/admin/edit.html", extra_vars)

        return tk.redirect_to(tk.url_for("workflow.list_definitions"))

    def get(self, workflow_id: int):
        tk.check_access("workflow_definition_update", {})

        extra_vars = {
            "workflow": tk.get_action("workflow_definition_show")({}, {"id": workflow_id}),
            "has_active_instances": self._has_instances(workflow_id),
        }

        return tk.render("workflow/admin/edit.html", extra_vars)


blueprint.add_url_rule(
    "/ckan-admin/workflow/<int:workflow_id>/edit", view_func=EditDefinition.as_view("edit_definition")
)


@blueprint.route("/ckan-admin/workflow/<int:workflow_id>/delete", methods=["POST"])
def delete_definition(workflow_id: int):
    tk.get_action("workflow_definition_delete")({}, {"id": workflow_id})
    return tk.redirect_to(tk.url_for("workflow.list_definitions"))


@blueprint.route("/ckan-admin/workflows/dashboard")
def admin_dashboard():
    instances = tk.get_action("workflow_instance_list")({}, {})

    # Resolve package details for display
    resolved_instances = []
    for inst in instances:
        try:
            pkg = tk.get_action("package_show")({}, {"id": inst["object_id"]})
        except tk.ObjectNotFound:
            pkg = {"title": inst["object_id"], "name": inst["object_id"]}

        current_task = None
        if inst["status"] in ["active", "overdue"]:
            for t in inst["tasks"]:
                if t["sequence"] == inst["current_step_index"]:
                    current_task = t
                    break

        resolved_instances.append({"instance": inst, "package": pkg, "current_task": current_task})

    return tk.render("workflow/admin/dashboard.html", extra_vars={"instances": resolved_instances})


@blueprint.route("/workflows/my-tasks")
def user_dashboard():
    tasks = tk.get_action("workflow_user_task_list")({}, {})
    notifications = tk.get_action("workflow_user_notification_list")({}, {})
    return tk.render("workflow/dashboard.html", extra_vars={"tasks": tasks, "notifications": notifications})


def get_node_for_transition(transition_str: str | None, current_index: int, steps_list: list[dict[str, Any]]) -> str:
    if not transition_str:
        # Default is to go to the next step
        next_idx = current_index + 1
        if next_idx >= len(steps_list):
            return "Published([Published])"
        return f"Step{next_idx}"

    if transition_str == "next":
        next_idx = current_index + 1
        if next_idx >= len(steps_list):
            return "Published([Published])"
        return f"Step{next_idx}"

    if transition_str == "reject":
        return "Rejected([Rejected])"

    if transition_str.startswith("step:"):
        try:
            target_idx = int(transition_str[5:])
            if target_idx < len(steps_list):
                return f"Step{target_idx}"
        except ValueError:
            pass

    return "Rejected([Rejected])"


def generate_mermaid_chart(workflow: dict[str, Any], active_step_index: int | None = None, instance_status: str | None = None):
    lines = ["graph TD", "    Start([Start: Dataset Created])"]

    steps = workflow.get("steps", [])

    if not steps:
        return "graph TD\n    NoSteps[No steps configured]"

    # 1. Define all step nodes
    for i, step in enumerate(steps):
        name = step.get("name") or "Unnamed Step"
        stype = step.get("step_type") or "manual_task"
        role = step.get("assigned_role")

        # Node text
        text = f"Step {i + 1}: {name}<br/>({stype.upper()})"
        if stype != "automated_task" and role:
            text += f"<br/>Role: {role}"

        if stype == "branching":
            lines.append(f'    Step{i}{{"{text}"}}')
        else:
            lines.append(f'    Step{i}["{text}"]')

    # 2. Add start transition
    lines.append("    Start --> Step0")

    # 3. Add transitions
    for i, step in enumerate(steps):
        stype = step.get("step_type") or "manual_task"
        config = step.get("config") or {}

        if stype == "approval":
            # Success path
            success_node = get_node_for_transition("next", i, steps)
            lines.append(f"    Step{i} -->|Approve| {success_node}")

            # Rejection path
            reject_transition = config.get("on_reject_transition") or "reject"
            reject_node = get_node_for_transition(reject_transition, i, steps)
            lines.append(f"    Step{i} -->|Reject| {reject_node}")

        elif stype == "automated_task":
            # Success path
            success_node = get_node_for_transition("next", i, steps)
            lines.append(f"    Step{i} -->|Success| {success_node}")

            # Failure path
            failure_transition = config.get("on_failure_transition") or "reject"
            failure_node = get_node_for_transition(failure_transition, i, steps)
            lines.append(f"    Step{i} -->|Failure| {failure_node}")

        elif stype == "branching":
            # Option A path
            label_a = config.get("branch_a_label") or "Option A"
            transition_a = config.get("branch_a_transition") or "next"
            node_a = get_node_for_transition(transition_a, i, steps)
            lines.append(f"    Step{i} -->|{label_a}| {node_a}")

            # Option B path
            label_b = config.get("branch_b_label") or "Option B"
            transition_b = config.get("branch_b_transition") or "next"
            node_b = get_node_for_transition(transition_b, i, steps)
            lines.append(f"    Step{i} -->|{label_b}| {node_b}")

        else:  # manual_task
            # Completion path
            success_node = get_node_for_transition("next", i, steps)
            lines.append(f"    Step{i} -->|Complete| {success_node}")

    if active_step_index is not None and active_step_index < len(steps):
        lines.append(f"    style Step{active_step_index} fill:#cce5ff,stroke:#007bff,stroke-width:3px;")

    if instance_status == "completed":
        lines.append("    style Published fill:#d4edda,stroke:#28a745,stroke-width:3px;")
    elif instance_status == "rejected":
        lines.append("    style Rejected fill:#f8d7da,stroke:#dc3545,stroke-width:3px;")

    return "\n".join(lines)


@blueprint.route("/<object_type>/<object_id>/workflow/initiate")
def initiate_workflow(object_type: str, object_id: str):
    tk.check_access("sysadmin", {})
    pkg = tk.get_action("package_show")({}, {"id": object_id})

    if start_workflow(pkg, trigger="manual"):
        tk.h.flash_success("Workflow has been initiated")

    return tk.redirect_to(tk.url_for("dataset.read", id=object_id))


@blueprint.route("/workflow/instance/<string:instance_id>")
def instance_detail(instance_id: str):
    inst = tk.get_action("workflow_instance_show")({}, {"id": instance_id})

    try:
        pkg = tk.get_action("package_show")({}, {"id": inst["object_id"]})
    except tk.ObjectNotFound:
        pkg = {"title": inst["object_id"], "name": inst["object_id"]}

    can_act = False
    current_task = None
    if inst["status"] in ["active", "overdue"]:
        for t in inst["tasks"]:
            if t["sequence"] == inst["current_step_index"]:
                current_task = t
                break
        if current_task and pkg.get("owner_org"):
            can_act = user_has_role(tk.c.user, pkg["owner_org"], current_task["assigned_role"])

    chart_code = ""
    try:
        # standard users can view definition chart for this instance
        wf = tk.get_action("workflow_definition_show")({"ignore_auth": True}, {"id": inst["workflow_id"]})
        if wf:
            active_idx = inst["current_step_index"] if inst["status"] in ["active", "overdue"] else None
            chart_code = generate_mermaid_chart(wf, active_step_index=active_idx, instance_status=inst["status"])
    except tk.ObjectNotFound:
        pass

    return tk.render(
        "workflow/instance_detail.html",
        extra_vars={
            "instance": inst,
            "package": pkg,
            "current_task": current_task,
            "can_act": can_act,
            "chart_code": chart_code,
        },
    )


@blueprint.route("/workflow/task/<string:instance_id>/<int:sequence>/action", methods=["POST"])
def task_action(instance_id: str, sequence: int):
    action_type = request.form.get("action_type")
    comment = request.form.get("comment", "")

    data_dict = {"id": instance_id, "sequence": sequence, "action_type": action_type, "comment": comment}
    try:
        result = tk.get_action("workflow_task_complete")({}, data_dict)

    except (tk.ObjectNotFound, tk.ValidationError) as e:
        tk.h.flash_error(f"Failed to complete task action: {e.message or e}")

    else:
        msg = result.get("message")
        tk.h.flash_success(f"Task action completed: {msg}")

    return tk.redirect_to(tk.url_for("workflow.user_dashboard"))


@blueprint.route("/workflow/instance/<string:instance_id>/cancel", methods=["POST"])
def cancel_workflow(instance_id: str):
    data_dict = {"id": instance_id}
    try:
        result = tk.get_action("workflow_instance_cancel")({}, data_dict)
    except tk.ObjectNotFound as e:
        tk.h.flash_error(f"Failded to cancel task action: {e}")
    else:
        msg = result.get("message")
        tk.h.flash_success(msg)

    return tk.redirect_to(tk.url_for("workflow.user_dashboard"))


@blueprint.route("/workflows/notifications/read", methods=["POST"])
def mark_read():
    tk.get_action("workflow_user_notification_mark_read")({}, {})
    return tk.redirect_to(tk.url_for("workflow.user_dashboard"))


@blueprint.route("/ckan-admin/workflow/<int:workflow_id>/visualize")
def visualize_definition(workflow_id: int):
    wf = tk.get_action("workflow_definition_show")({}, {"id": workflow_id})

    chart_code = generate_mermaid_chart(wf)
    return tk.render("workflow/admin/visualize.html", extra_vars={"workflow": wf, "chart_code": chart_code})
