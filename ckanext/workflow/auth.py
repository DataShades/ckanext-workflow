import ckan.authz as authz
import ckan.model as model
import ckan.plugins.toolkit as tk
import ckanext.workflow.helpers as workflow_helpers
from ckanext.workflow.util import roles


def get_auth():
    return dict(
        move_to_next_stage=move_to_next_stage,
        move_to_previous_stage=move_to_previous_stage,
        create_dataset_revision=create_dataset_revision,
        read_dataset_revision=read_dataset_revision,
        merge_dataset_revision=merge_dataset_revision
    )


def _success(success=True, msg=''):
    return dict(
        success=success,
        msg=msg
    )


def move_to_next_stage(context, data_dict):
    wf, _ = workflow_helpers.get_workflow_from_package(data_dict)

    stage = workflow_helpers.get_stage_from_package(data_dict)
    if roles.creator in stage.who_can_approve and stage.approve() is not None:
        user = model.User.get(context['user'])
        if user is not None and user.id == data_dict['creator_user_id']:
            return _success()
    return _success(False)


def move_to_previous_stage(context, data_dict):
    wf, _ = workflow_helpers.get_workflow_from_package(data_dict)
    stage = workflow_helpers.get_stage_from_package(data_dict)
    if roles.creator in stage.who_can_reject and stage.reject() is not None:
        user = model.User.get(context['user'])
        if user is not None and user.id == data_dict['creator_user_id']:
            return _success()
    return _success(False)


@tk.auth_sysadmins_check
def create_dataset_revision(context, data_dict):
    workflow, _ = workflow_helpers.get_workflow_from_package(data_dict)
    stage = workflow_helpers.get_stage_from_package(data_dict)

    if stage != workflow.finish:
        return _success(False, 'Dataset must be published')
    if workflow_helpers.get_original_dataset_id_from_package(data_dict):
        return _success(False, 'Cannot create revision of revision')
    if workflow_helpers.get_dataset_revision_query(data_dict['id']).count():
        return _success(False, 'Dataset already has revision')
    return authz.is_authorized('package_create', context, data_dict)


def read_dataset_revision(context, data_dict):

    authz.has_user_permission_for_group_or_org(
        data_dict.get('owner_org'), context['user'], 'create_dataset')
    return authz.is_authorized('package_create', context, data_dict)


def merge_dataset_revision(context, data_dict):
    return _success(workflow_helpers.is_site_admin())
