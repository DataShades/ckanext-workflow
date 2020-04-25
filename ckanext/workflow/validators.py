# -*- coding: utf-8 -*-

from ckan.logic.validators import Invalid, missing
from ckanext.workflow.util import Workflow
import ckanext.workflow.helpers as h


def get_validators():
    return dict(
        workflow_type_validator=workflow_type_validator,
        workflow_stage_validator=workflow_stage_validator,
        revision_field_validator=revision_field_validator
    )


def revision_field_validator(key, data, errors, context):
    pkg = context.get('package')

    if pkg:
        data[key] = pkg.extras.get(h._revision_field())

    value = data[key]
    if value is missing:
        data[key] = None


def workflow_type_validator(key, data, errors, context):
    value = data[key]
    if value is missing or not value:
        data[key] = 'base'
        return
    try:
        Workflow.get_workflow(value)
    except KeyError:
        raise Invalid('Unsupported workflow type')


def workflow_stage_validator(key, data, errors, context):
    stage = data[key]
    type = data.get((h._workflow_type_field(),), missing)

    if type is missing or not type:
        type = 'base'
    wf = Workflow.get_workflow(type)
    first_stage = str(wf.start)

    pkg = context.get('package')

    if stage is missing or not stage:
        if pkg:
            first_stage = pkg.extras.get(
                h._workflow_stage_field()) or first_stage
        data[key] = first_stage
        return
    if pkg is None and stage != first_stage:
        raise Invalid('You cannot skip fist stage')
    current_stage = pkg.extras.get(key[0]) if pkg else first_stage

    if current_stage == stage:
        return

    try:
        wf.get_stage(stage)
    except KeyError:
        raise Invalid('Unsupported workflow stage')
    user = context['auth_user_obj']
    if user and (user.sysadmin or h.is_site_admin(user)):
        return
    if stage == wf.finish:
        raise Invalid('Only site admin can set this stage')
    if not user or user.id != pkg.creator_user_id:
        raise Invalid('Only dataset creator can change stage')
