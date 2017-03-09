import ckan.plugins as plugins
from ckan.plugins.interfaces import IDomainObjectModification

import ckan.plugins.toolkit as tk
import ckan.model as model
import ckanext.workflow.helpers as workflow_helpers


def get_actions():
    return dict(
        move_to_next_stage=move_to_next_stage,
        move_to_previous_stage=move_to_previous_stage,
        reset_to_initial_stage=reset_to_initial_stage
    )


def _prepare_workflow_action(context, data_dict, auth_name):
    pkg_dict = tk.get_action('package_show')(context, data_dict)
    tk.check_access(auth_name, context, pkg_dict)

    wf, _ = workflow_helpers.get_workflow_from_package(context['package'])
    stage = wf.get_stage(pkg_dict[workflow_helpers._workflow_stage_field()])
    return pkg_dict, stage, wf


def _update_workflow_stage(field, value, context):
    pkg = context['package']
    model.Session.query(model.PackageExtra).filter_by(
        package_id=pkg.id,
        key=field
    ).update({
        'value': value
    })
    model.Session.commit()

    for plugin in plugins.PluginImplementations(IDomainObjectModification):
        plugin.notify(pkg, 'changed')


def move_to_next_stage(context, data_dict):
    pkg_dict, stage, wf = _prepare_workflow_action(
        context, data_dict, 'move_to_next_stage')
    next_stage = stage.approve()
    field_name = workflow_helpers._workflow_stage_field()

    _update_workflow_stage(field_name, str(next_stage), context)

    if callable(stage.approval_effect):
        stage.approval_effect(context, pkg_dict)

    return {field_name: str(next_stage)}


def move_to_previous_stage(context, data_dict):
    pkg_dict, stage, wf = _prepare_workflow_action(
        context, data_dict, 'move_to_previous_stage')
    next_stage = stage.reject()
    field_name = workflow_helpers._workflow_stage_field()
    _update_workflow_stage(field_name, str(next_stage), context)

    if callable(stage.rejection_effect):
        stage.rejection_effect(context, pkg_dict, data_dict)

    return {field_name: str(next_stage)}


def reset_to_initial_stage(context, data_dict):
    pkg_dict, stage, wf = _prepare_workflow_action(
        context, data_dict, 'reset_to_initial_stage')
    next_stage = wf.start
    field_name = workflow_helpers._workflow_stage_field()
    _update_workflow_stage(field_name, str(next_stage), context)

    return {field_name: str(next_stage)}
