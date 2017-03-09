
import ckan.model as model

import ckanext.workflow.helpers as workflow_helpers
from ckanext.workflow.util import roles


def get_auth():
    return dict(
        move_to_next_stage=move_to_next_stage,
        move_to_previous_stage=move_to_previous_stage,
        reset_to_initial_stage=reset_to_initial_stage
    )


def _success(success=True, msg=''):
    return dict(
        success=success,
        msg=msg
    )


def move_to_next_stage(context, data_dict):
    pkg = context['package']
    wf, _ = workflow_helpers.get_workflow_from_package(pkg)
    stage = wf.get_stage(pkg[workflow_helpers._workflow_stage_field()])
    if roles.creator in stage.who_can_approve and stage.approve() is not None:
        user = model.User.get(context['user'])
        if user is not None and user.id == pkg['creator_user_id']:
            return _success()
    return _success(False)


def move_to_previous_stage(context, data_dict):
    pkg = context['package']
    wf, _ = workflow_helpers.get_workflow_from_package(pkg)
    stage = wf.get_stage(pkg[workflow_helpers._workflow_stage_field()])
    if roles.creator in stage.who_can_reject and stage.reject() is not None:
        user = model.User.get(context['user'])
        if user is not None and user.id == pkg['creator_user_id']:
            return _success()
    return _success(False)


def reset_to_initial_stage(context, data_dict):
    return _success(False)
