# -*- coding: utf-8 -*-
import re
import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import ckan.model as model
from ckan.common import c
import ckan.lib.helpers as helpers
import ckan.lib.mailer as mailer

from ckanext.workflow.util import Workflow, BaseWorkflow
from ckanext.workflow.interfaces import IWorkflow
import ckanext.workflow.helpers as workflow_helpers
import ckanext.workflow.validators as validators
import ckanext.workflow.auth as auth
import ckanext.workflow.action as action

org_re = re.compile('owner_org:(?P<id>[^\s]+)')
log = logging.getLogger(__name__)


def submit_for_approval(context, pkg):
    site_admin_email = workflow_helpers.get_site_admin_email()

    if site_admin_email:
        try:
            mailer.mail_recipient(
                'Admin', site_admin_email, 'Submission for approval',
                (
                    'A new SEED dataset {title} ({dataset_url}) has'
                    ' been submitted for publication approval by {creator}.'
                ).format(
                    title=pkg['title'],
                    dataset_url=helpers.url_for(
                        'dataset_read', id=pkg['id'], qualified=True),
                    creator=context['user']
                 )
            )
        except Exception as e:
            log.error('[workflow email] {0}'.format(e))


def reject_approval(context, pkg, data=None):
    reason = 'Not defined'
    if data and 'reason' in data:
        reason = data['reason']
    author = model.User.get(pkg['creator_user_id'])

    try:
        if author is None:
            raise Exception('User <{0}> not found'.format(
                pkg['creator_user_id']))
        if not author.email:
            raise Exception('User <{0}> has no email'.format(
                author.name))

        mailer.mail_recipient(
            author.fullname or author.name,
            author.email, 'SEED dataset rejection',
            (
                'A SEED dataset {title} ({dataset_url}) has'
                ' been rejected by {admin}.\n'
                'Reason:\n'
                '{reason}'
            ).format(
                title=pkg['title'],
                dataset_url=helpers.url_for(
                    'dataset_read', id=pkg['id'], qualified=True),
                admin=context['user'],
                reason=reason
             )
        )
    except Exception as e:
        log.error('[workflow email] {0}'.format(e))


class WorkflowPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(IWorkflow)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IRoutes, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'workflow')
        Workflow.configure()

        Workflow.get_workflow(
            'base').start.approval_effect = submit_for_approval

        Workflow.get_workflow(
            'base').start.approve().rejection_effect = reject_approval

    # IWorkflow

    def register_workflows(self):
        return dict(
            base=BaseWorkflow()
        )

    # IValidators

    def get_validators(self):
        return validators.get_validators()

    # IAuthFunctions

    def get_auth_functions(self):
        return auth.get_auth()

    # IActions

    def get_actions(self):
        return action.get_actions()

    # ITemplateHelpers

    def get_helpers(self):
        return workflow_helpers.get_helpers()

    # IRoutes

    def before_map(self, map):

        ctrl = 'ckanext.workflow.controller:WorkflowController'
        map.connect(
            'workflow_approve',
            '/dataset/workflow/{id}/approve',
            controller=ctrl, action='approve')
        map.connect(
            'workflow_reject',
            '/dataset/workflow/{id}/reject',
            controller=ctrl, action='reject')
        map.connect(
            'workflow_pending_list',
            '/dataset/workflow_approvals',
            controller=ctrl, action='pending_list')
        return map

    # IPackageController

    def before_search(self, search_params):
        fq = search_params.get('fq', '')
        q = search_params.get('q', '')
        is_member = False
        match = org_re.search(fq) or org_re.search(q)
        if match is not None:
            id = match.group('id').strip('\'"')
            is_member = helpers.user_in_org_or_group(id)

        if c.userobj and '+creator_user_id:{0}'.format(
                c.userobj.id) in fq or is_member:
            pass
        else:
            fq += ' +{0}:({1})'.format(
                workflow_helpers._workflow_stage_field(),
                ' OR '.join(Workflow.get_all_finish_stages())
            )
        search_params['fq'] = fq
        return search_params
