from __future__ import annotations

from typing import Any

from flask import Blueprint, request
from flask.views import MethodView

import ckan.plugins.toolkit as tk
from ckan.lib.navl.dictization_functions import unflatten
from ckan.logic import parse_params, tuplize_dict

from ckanext.workflow.service import user_has_role

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
        return tk.render("workflow/admin/edit.html", {"workflow": None})

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
            }

            return tk.render("workflow/admin/edit.html", extra_vars)

        return tk.redirect_to(tk.url_for("workflow.list_definitions"))


blueprint.add_url_rule("/ckan-admin/workflow/new", view_func=CreateDefinition.as_view("create_definition"))


class EditDefinition(MethodView):
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
            }
            return tk.render("workflow/admin/edit.html", extra_vars)

        return tk.redirect_to(tk.url_for("workflow.list_definitions"))

    def get(self, workflow_id: int):
        tk.check_access("workflow_definition_update", {})
        extra_vars = {"workflow": tk.get_action("workflow_definition_show")({}, {"id": workflow_id})}

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


def generate_mermaid_chart(workflow: dict[str, Any], active_step_index: int | None = None):
    lines = ["graph TD", "    Start([Start: Dataset Created])"]

    steps = workflow["steps"]

    if not steps:
        return "graph TD\n    NoSteps[No steps configured]"

    first_step = steps[0]
    first_name = first_step.get("name")
    first_type = first_step.get("step_type", "")
    first_role = first_step.get("assigned_role")

    lines.append(f'    Start --> Step0["Step 1: {first_name}<br/>({first_type.upper()})<br/>Role: {first_role}"]')

    for i, step in enumerate(steps):
        is_last = i == len(steps) - 1
        step_type = step.get("step_type", "")

        if is_last:
            next_node = "Published([Published: Active State])"
        else:
            next_step = steps[i + 1]

            next_node = (
                f'Step{i + 1}["Step {i + 2}: {next_step.get("name")}<br/>'
                f'({(next_step.get("step_type")).upper()})<br/>Role: {next_step.get("assigned_role")}"]'
            )

        if step_type == "approval":
            lines.append(f"    Step{i} -->|Approve| {next_node}")
            lines.append(f"    Step{i} -->|Reject| Rejected([Rejected: Draft State])")
        elif step_type == "manual_task":
            lines.append(f"    Step{i} -->|Complete| {next_node}")
        elif step_type == "automated_task":
            lines.append(f"    Step{i} -->|Success| {next_node}")
            lines.append(f"    Step{i} -->|Failure| Rejected([Rejected: Draft State])")

    if active_step_index is not None and active_step_index < len(steps):
        lines.append(f"    style Step{active_step_index} fill:#cce5ff,stroke:#007bff,stroke-width:3px;")

    return "\n".join(lines)


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

    # Generate visual workflow chart
    chart_code = ""
    try:
        # standard users can view definition chart for this instance
        wf = tk.get_action("workflow_definition_show")({"ignore_auth": True}, {"id": inst["workflow_id"]})
        if wf:
            active_idx = inst["current_step_index"] if inst["status"] in ["active", "overdue"] else None
            chart_code = generate_mermaid_chart(wf, active_step_index=active_idx)
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
