from __future__ import annotations

import json
from flask import Blueprint, request
from flask.views import MethodView
import ckan.plugins.toolkit as tk
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
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_definition_list", context)
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")

    workflows = tk.get_action("workflow_definition_list")(context, {})
    return tk.render("workflow/admin/list.html", {"workflows": workflows})


def _parse_steps_from_form() -> list[dict[str, Any]]:
    names = request.form.getlist("step_name[]")
    roles = request.form.getlist("step_role[]")
    types = request.form.getlist("step_type[]")
    instructions = request.form.getlist("step_instructions[]")

    # Post Actions Form Arrays
    approve_field = request.form.getlist("step_approve_field[]")
    approve_val = request.form.getlist("step_approve_val[]")
    approve_notif_target = request.form.getlist("step_approve_notif_target[]")
    approve_notif_msg = request.form.getlist("step_approve_notif_msg[]")

    reject_field = request.form.getlist("step_reject_field[]")
    reject_val = request.form.getlist("step_reject_val[]")
    reject_notif_target = request.form.getlist("step_reject_notif_target[]")
    reject_notif_msg = request.form.getlist("step_reject_notif_msg[]")

    complete_field = request.form.getlist("step_complete_field[]")
    complete_val = request.form.getlist("step_complete_val[]")
    complete_notif_target = request.form.getlist("step_complete_notif_target[]")
    complete_notif_msg = request.form.getlist("step_complete_notif_msg[]")

    success_field = request.form.getlist("step_success_field[]")
    success_val = request.form.getlist("step_success_val[]")
    success_notif_target = request.form.getlist("step_success_notif_target[]")
    success_notif_msg = request.form.getlist("step_success_notif_msg[]")

    failure_field = request.form.getlist("step_failure_field[]")
    failure_val = request.form.getlist("step_failure_val[]")
    failure_notif_target = request.form.getlist("step_failure_notif_target[]")
    failure_notif_msg = request.form.getlist("step_failure_notif_msg[]")

    steps_data = []
    for i in range(len(names)):
        if not names[i].strip():
            continue

        p_actions = {}
        step_type = types[i]

        if step_type == "approval":
            on_approve = []
            if i < len(approve_field) and approve_field[i].strip():
                on_approve.append({"type": "change_field", "field": approve_field[i], "value": approve_val[i]})
            if i < len(approve_notif_target) and approve_notif_target[i].strip() and approve_notif_msg[i].strip():
                on_approve.append(
                    {
                        "type": "send_notification",
                        "recipient": approve_notif_target[i],
                        "message": approve_notif_msg[i],
                    }
                )
            if on_approve:
                p_actions["on_approve"] = on_approve

            on_reject = []
            if i < len(reject_field) and reject_field[i].strip():
                on_reject.append({"type": "change_field", "field": reject_field[i], "value": reject_val[i]})
            if i < len(reject_notif_target) and reject_notif_target[i].strip() and reject_notif_msg[i].strip():
                on_reject.append(
                    {
                        "type": "send_notification",
                        "recipient": reject_notif_target[i],
                        "message": reject_notif_msg[i],
                    }
                )
            if on_reject:
                p_actions["on_reject"] = on_reject

        elif step_type == "manual_task":
            on_complete = []
            if i < len(complete_field) and complete_field[i].strip():
                on_complete.append({"type": "change_field", "field": complete_field[i], "value": complete_val[i]})
            if (
                i < len(complete_notif_target)
                and complete_notif_target[i].strip()
                and complete_notif_msg[i].strip()
            ):
                on_complete.append(
                    {
                        "type": "send_notification",
                        "recipient": complete_notif_target[i],
                        "message": complete_notif_msg[i],
                    }
                )
            if on_complete:
                p_actions["on_complete"] = on_complete

        elif step_type == "automated_task":
            on_success = []
            if i < len(success_field) and success_field[i].strip():
                on_success.append({"type": "change_field", "field": success_field[i], "value": success_val[i]})
            if i < len(success_notif_target) and success_notif_target[i].strip() and success_notif_msg[i].strip():
                on_success.append(
                    {
                        "type": "send_notification",
                        "recipient": success_notif_target[i],
                        "message": success_notif_msg[i],
                    }
                )
            if on_success:
                p_actions["on_success"] = on_success

            on_failure = []
            if i < len(failure_field) and failure_field[i].strip():
                on_failure.append({"type": "change_field", "field": failure_field[i], "value": failure_val[i]})
            if i < len(failure_notif_target) and failure_notif_target[i].strip() and failure_notif_msg[i].strip():
                on_failure.append(
                    {
                        "type": "send_notification",
                        "recipient": failure_notif_target[i],
                        "message": failure_notif_msg[i],
                    }
                )
            if on_failure:
                p_actions["on_failure"] = on_failure

        steps_data.append(
            {
                "name": names[i],
                "assigned_role": roles[i],
                "step_type": step_type,
                "instructions": instructions[i],
                "post_actions": json.dumps(p_actions),
            }
        )
    return steps_data


class CreateDefinition(MethodView):
    def get(self):
        context = {"user": tk.c.user or ""}
        try:
            tk.check_access("workflow_definition_create", context)
        except tk.NotAuthorized:
            tk.abort(403, "Not authorized")
        return tk.render("workflow/admin/edit.html", {"workflow": None})

    def post(self):
        context = {"user": tk.c.user or ""}
        try:
            tk.check_access("workflow_definition_create", context)
        except tk.NotAuthorized:
            tk.abort(403, "Not authorized")

        name = request.form.get("name")
        description = request.form.get("description")
        enabled = "enabled" in request.form
        trigger_type = request.form.get("trigger_type", "dataset_create")
        dataset_type = request.form.get("dataset_type", "all")

        steps_data = _parse_steps_from_form()

        tk.get_action("workflow_definition_create")(
            context,
            {
                "name": name,
                "description": description,
                "enabled": enabled,
                "trigger_type": trigger_type,
                "dataset_type": dataset_type,
                "steps": steps_data,
            }
        )
        return tk.redirect_to(tk.url_for("workflow.list_definitions"))


blueprint.add_url_rule("/ckan-admin/workflow/new", view_func=CreateDefinition.as_view("create_definition"))


@blueprint.route("/ckan-admin/workflow/<int:workflow_id>/edit", methods=["GET", "POST"])
def edit_definition(workflow_id):
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_definition_update", context)
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        enabled = "enabled" in request.form
        trigger_type = request.form.get("trigger_type", "dataset_create")
        dataset_type = request.form.get("dataset_type", "all")

        steps_data = _parse_steps_from_form()

        tk.get_action("workflow_definition_update")(
            context,
            {
                "id": workflow_id,
                "name": name,
                "description": description,
                "enabled": enabled,
                "trigger_type": trigger_type,
                "dataset_type": dataset_type,
                "steps": steps_data,
            }
        )
        return tk.redirect_to(tk.url_for("workflow.list_definitions"))

    # GET method
    try:
        wf = tk.get_action("workflow_definition_show")(context, {"id": workflow_id})
    except tk.ObjectNotFound:
        tk.abort(404, "Workflow not found")

    # Parse JSON actions on steps before rendering edit page
    for step in wf.get("steps", []):
        step["parsed_actions"] = {}
        post_actions = step.get("post_actions")
        if post_actions:
            try:
                step["parsed_actions"] = json.loads(post_actions)
            except Exception:
                pass

    return tk.render("workflow/admin/edit.html", extra_vars={"workflow": wf})


@blueprint.route("/ckan-admin/workflow/<int:workflow_id>/delete", methods=["POST"])
def delete_definition(workflow_id):
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_definition_delete", context)
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")

    tk.get_action("workflow_definition_delete")(context, {"id": workflow_id})
    return tk.redirect_to(tk.url_for("workflow.list_definitions"))


@blueprint.route("/ckan-admin/workflows/dashboard")
def admin_dashboard():
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_instance_list", context)
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")

    instances = tk.get_action("workflow_instance_list")(context, {})

    # Resolve package details for display
    resolved_instances = []
    for inst in instances:
        try:
            pkg = tk.get_action("package_show")(context, {"id": inst["package_id"]})
        except Exception:
            pkg = {"title": inst["package_id"], "name": inst["package_id"]}

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
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_user_task_list", context)
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")

    tasks = tk.get_action("workflow_user_task_list")(context, {})
    notifications = tk.get_action("workflow_user_notification_list")(context, {})
    return tk.render("workflow/dashboard.html", extra_vars={"tasks": tasks, "notifications": notifications})


def generate_mermaid_chart(workflow, active_step_index=None):
    lines = ["graph TD", "    Start([Start: Dataset Created])"]

    if isinstance(workflow, dict):
        steps = workflow.get("steps", [])
    else:
        steps = workflow.steps

    if not steps:
        return "graph TD\n    NoSteps[No steps configured]"

    first_step = steps[0]
    first_name = first_step.get("name") if isinstance(first_step, dict) else first_step.name
    first_type = first_step.get("step_type", "") if isinstance(first_step, dict) else first_step.step_type
    first_role = first_step.get("assigned_role") if isinstance(first_step, dict) else first_step.assigned_role

    lines.append(
        f'    Start --> Step0["Step 1: {first_name}<br/>({first_type.upper()})<br/>Role: {first_role}"]'
    )

    for i, step in enumerate(steps):
        is_last = i == len(steps) - 1

        if isinstance(step, dict):
            step_name = step.get("name")
            step_type = step.get("step_type", "")
            assigned_role = step.get("assigned_role")
        else:
            step_name = step.name
            step_type = step.step_type
            assigned_role = step.assigned_role

        next_node = (
            "Published([Published: Active State])"
            if is_last
            else f'Step{i + 1}["Step {i + 2}: {steps[i + 1].get("name") if isinstance(steps[i + 1], dict) else steps[i + 1].name}<br/>({(steps[i + 1].get("step_type") if isinstance(steps[i + 1], dict) else steps[i + 1].step_type).upper()})<br/>Role: {steps[i + 1].get("assigned_role") if isinstance(steps[i + 1], dict) else steps[i + 1].assigned_role}"]'
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
def instance_detail(instance_id):
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_instance_show", context, {"id": instance_id})
        inst = tk.get_action("workflow_instance_show")(context, {"id": instance_id})
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")
    except tk.ObjectNotFound:
        tk.abort(404, "Workflow instance not found")

    try:
        pkg = tk.get_action("package_show")(context, {"id": inst["package_id"]})
    except Exception:
        pkg = {"title": inst["package_id"], "name": inst["package_id"]}

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
        sys_context = tk.fresh_context(context)
        sys_context["ignore_auth"] = True
        wf = tk.get_action("workflow_definition_show")(sys_context, {"id": inst["workflow_id"]})
        if wf:
            active_idx = inst["current_step_index"] if inst["status"] in ["active", "overdue"] else None
            chart_code = generate_mermaid_chart(wf, active_step_index=active_idx)
    except Exception:
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
def task_action(instance_id, sequence):
    context = {"user": tk.c.user or ""}
    action_type = request.form.get("action_type")
    comment = request.form.get("comment", "")

    data_dict = {
        "id": instance_id,
        "sequence": sequence,
        "action_type": action_type,
        "comment": comment
    }
    try:
        tk.check_access("workflow_task_complete", context, data_dict)
        result = tk.get_action("workflow_task_complete")(context, data_dict)
        success = result.get("success")
        msg = result.get("message")
    except Exception as e:
        success = False
        msg = str(e)

    if success:
        tk.h.flash_success(f"Task action completed: {msg}")
    else:
        tk.h.flash_error(f"Failed to complete task action: {msg}")

    return tk.redirect_to(tk.url_for("workflow.user_dashboard"))


@blueprint.route("/workflow/instance/<string:instance_id>/cancel", methods=["POST"])
def cancel_workflow(instance_id):
    context = {"user": tk.c.user or ""}
    data_dict = {"id": instance_id}
    try:
        tk.check_access("workflow_instance_cancel", context, data_dict)
        result = tk.get_action("workflow_instance_cancel")(context, data_dict)
        success = result.get("success")
        msg = result.get("message")
    except Exception as e:
        success = False
        msg = str(e)

    if success:
        tk.h.flash_success(msg)
    else:
        tk.h.flash_error(msg)

    return tk.redirect_to(tk.url_for("workflow.user_dashboard"))


@blueprint.route("/workflows/notifications/read", methods=["POST"])
def mark_read():
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_user_notification_mark_read", context)
        tk.get_action("workflow_user_notification_mark_read")(context, {})
    except Exception:
        pass
    return tk.redirect_to(tk.url_for("workflow.user_dashboard"))


@blueprint.route("/ckan-admin/workflow/<int:workflow_id>/visualize")
def visualize_definition(workflow_id):
    context = {"user": tk.c.user or ""}
    try:
        tk.check_access("workflow_definition_show", context, {"id": workflow_id})
        wf = tk.get_action("workflow_definition_show")(context, {"id": workflow_id})
    except tk.NotAuthorized:
        tk.abort(403, "Not authorized")
    except tk.ObjectNotFound:
        tk.abort(404, "Workflow not found")

    chart_code = generate_mermaid_chart(wf)
    return tk.render("workflow/admin/visualize.html", extra_vars={"workflow": wf, "chart_code": chart_code})
