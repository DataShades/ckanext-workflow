import ckan.plugins as plugins
from ckan.plugins.interfaces import IDomainObjectModification

import ckan.plugins.toolkit as tk
import ckan.model as model
import ckanext.workflow.helpers as workflow_helpers


ignored_fields = (
    'id',
    workflow_helpers._workflow_stage_field(),
    'resources',
    'creator_user_id'
)


def get_actions():
    return dict(
        move_to_next_stage=move_to_next_stage,
        move_to_previous_stage=move_to_previous_stage,
        create_dataset_revision=create_dataset_revision,
        merge_dataset_revision=merge_dataset_revision
    )


def _prepare_workflow_action(context, data_dict, auth_name):
    """Check access and get workflow info from package.

    :param context: api context
    :param data_dict: data for `package_show`
    :param auth_name: name of auth function for performing action

    :returns: tuple with pkg_dict, stage and workflow objects
    :rtype: typle(dict, Stage, Workflow)

    """
    pkg_dict = tk.get_action('package_show')(context, data_dict)
    tk.check_access(auth_name, context, pkg_dict)

    wf, _ = workflow_helpers.get_workflow_from_package(pkg_dict)
    stage = wf.get_stage(pkg_dict[workflow_helpers._workflow_stage_field()])
    return pkg_dict, stage, wf


def _update_workflow_stage(field, value, pkg):
    """Update workflow stage directly in db, avoiding new revision.

    :param field: workflow stage's field name
    :param value: next workflow stage
    :param pkg: model.Package object

    :returns: nothing
    :rtype: None

    """
    model.Session.query(model.PackageExtra).filter_by(
        package_id=pkg.id,
        key=field
    ).update({
        'value': value
    })
    model.Session.commit()

    for plugin in plugins.PluginImplementations(IDomainObjectModification):
        plugin.notify(pkg, 'changed')


def create_dataset_revision(context, data_dict):
    """Create new revision from existing package.

    :param id: id or name of source for revision
    :returns: newly created dataset
    :rtype: dict

    """
    pkg_dict = tk.get_action('package_show')(context, data_dict)
    tk.check_access('create_dataset_revision', context, pkg_dict)

    pkg_dict['name'] = pkg_dict['id'] + '-revision'
    pkg_dict[workflow_helpers._revision_field()] = pkg_dict['id']
    for field in ignored_fields:
        del pkg_dict[field]

    del context['package']
    revision = tk.get_action('package_create')(context, pkg_dict)

    return revision


def merge_dataset_revision(context, data_dict):
    """Merge revision into its origin.

    :param id: id or name of revision to merge
    :returns: updated origin
    :rtype: dict

    """
    pkg_dict = tk.get_action('package_show')(context, data_dict)
    tk.check_access('merge_dataset_revision', context, pkg_dict)
    revision_field = workflow_helpers._revision_field()
    revision_id = pkg_dict['id']
    original_id = pkg_dict[revision_field]

    for field in ignored_fields + ('name', revision_field):
        del pkg_dict[field]

    pkg_dict['id'] = original_id

    tk.get_action('dataset_purge')(context, {'id': revision_id})
    del context['package']
    updated_pkg = tk.get_action('package_patch')(context, pkg_dict)

    return updated_pkg


def move_to_next_stage(context, data_dict):
    """Move package to next stage in its workflow.

    :param id: id or name of package
    :returns:  dict with name of new stage
    :rtype: dict

    """
    pkg_dict, stage, wf = _prepare_workflow_action(
        context, data_dict, 'move_to_next_stage')
    next_stage = stage.approve()
    field_name = workflow_helpers._workflow_stage_field()

    _update_workflow_stage(field_name, str(next_stage), context['package'])

    if callable(stage.approval_effect):
        stage.approval_effect(context, pkg_dict)

    return {field_name: str(next_stage)}


def move_to_previous_stage(context, data_dict):
    """Move package to previous stage in its workflow.

    :param id: id or name of package
    :returns:  dict with name of new stage
    :rtype: dict

    """

    pkg_dict, stage, wf = _prepare_workflow_action(
        context, data_dict, 'move_to_previous_stage')
    next_stage = stage.reject()
    field_name = workflow_helpers._workflow_stage_field()
    _update_workflow_stage(field_name, str(next_stage), context['package'])

    if callable(stage.rejection_effect):
        stage.rejection_effect(context, pkg_dict, data_dict)

    return {field_name: str(next_stage)}
