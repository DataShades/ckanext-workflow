# -*- coding: utf-8 -*-
import logging

import pylons.config as config
import ckan.model as model
from ckanext.workflow.util import Workflow

log = logging.getLogger(__name__)


def get_helpers():
    return dict(
        get_workflow_from_package=get_workflow_from_package,
        get_stage_from_package=get_stage_from_package,
        get_dataset_revision=get_dataset_revision,
        is_revision=is_revision
    )


def is_revision(package):
    return get_original_dataset_id_from_package(package)


def get_dataset_revision(id):
    return get_dataset_revision_query(id).first()


def get_dataset_revision_query(id):
    return model.Session.query(model.Package).join(
        model.PackageExtra
    ).filter_by(
            key=_revision_field(),
            value=id
    )


def get_site_admin_email():
    return config.get('workflow.site_admin.email')


def _revision_field():
    return config.get(
        'workflow.revision_field_name', 'original_id_of_revision')


def _workflow_type_field():
    return config.get('workflow.type_field_name', 'workflow_type')


def _workflow_stage_field():
    return config.get('workflow.stage_field_name', 'workflow_stage')


def get_workflow_from_package(pkg):
    """FIXME! briefly describe function

    :param pkg:
    :returns:
    :rtype:

    """
    if isinstance(pkg, model.Package):
        data = pkg.extras
    else:
        data = pkg

    wf_name = data.get(_workflow_type_field()) or 'base'
    try:
        return Workflow.get_workflow(wf_name), wf_name
    except KeyError:
        log.debug('[workflow] Unable to find workflow `{0}`'.format(wf_name))
        return None, None


def get_stage_from_package(pkg):
    wf, _ = get_workflow_from_package(pkg)
    if wf is None:
        return None

    if isinstance(pkg, model.Package):
        data = pkg.extras
    else:
        data = pkg

    stage = data.get(_workflow_stage_field())
    if stage:
        try:
            return wf.get_stage(stage)
        except KeyError:
            log.debug('[workflow] Unable to find stage `{0}`'.format(stage))
            return None


def get_original_dataset_id_from_package(pkg):

    if isinstance(pkg, model.Package):
        data = pkg.extras
    else:
        data = pkg

    id = data.get(_revision_field())
    return id


def is_site_admin(user):
    return user.sysadmin
    # ids = [g.id for g in model.Group.get_top_level_groups('organization')]
    # return authz._has_user_permission_for_groups(
    #     user.id, 'admin', ids
    # )
