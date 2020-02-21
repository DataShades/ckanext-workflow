# -*- coding: utf-8 -*-
import re
import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
import ckan.model as model
from ckan.common import c
import ckan.lib.helpers as helpers
import ckan.lib.mailer as mailer
from ckan.lib.plugins import DefaultPermissionLabels

from ckanext.workflow.util import Workflow, BaseWorkflow
from ckanext.workflow.interfaces import IWorkflow

import ckanext.workflow.helpers as workflow_helpers
import ckanext.workflow.validators as validators
import ckanext.workflow.auth as auth
import ckanext.workflow.action as action

org_re = re.compile('owner_org:(?P<id>[^\s]+)')
log = logging.getLogger(__name__)

if tk.check_ckan_version("2.9"):
    from ckanext.workflow.plugin.flask_plugin import MixinPlugin
else:
    from ckanext.workflow.plugin.pylons_plugin import MixinPlugin


def submit_for_approval(context, pkg):
    site_admin_emails = workflow_helpers.get_site_admin_email()
    dataset_type = 'SEED dataset'
    if workflow_helpers.get_original_dataset_id_from_package(pkg):
        dataset_type = 'revision for SEED dataset'
    if site_admin_emails:
        try:
            message = ('A new {type} {title} ({dataset_url}) has'
                       ' been submitted for publication approval by {creator}.'
                       ).format(type=dataset_type,
                                title=pkg['title'],
                                dataset_url=helpers.url_for('dataset_read',
                                                            id=pkg['id'],
                                                            qualified=True),
                                creator=context['user'])
            for email in site_admin_emails:

                mailer.mail_recipient('Admin', email,
                                      'Submission for approval', message)
        except Exception as e:
            log.error('[workflow email] {0}'.format(e))


def _approval_preparation(context, pkg, message, data={}):
    reason = data.get('reason', 'Not defined')
    subject = data.get('subject', '')
    author = model.User.get(pkg['creator_user_id'])
    type = 'SEED dataset'
    if workflow_helpers.get_original_dataset_id_from_package(pkg):
        type = 'revision for SEED dataset'
    if 'dataset_url' not in data:
        dataset_url = helpers.url_for('dataset_read',
                                      id=pkg['id'],
                                      qualified=True)
    else:
        dataset_url = data['dataset_url']

    try:
        if author is None:
            raise Exception('User <{0}> not found'.format(
                pkg['creator_user_id']))
        if not author.email:
            raise Exception('User <{0}> has no email'.format(author.name))

        mailer.mail_recipient(
            author.fullname or author.name, author.email, subject,
            message.format(type=type,
                           title=pkg['title'],
                           dataset_url=dataset_url,
                           admin=context['user'],
                           reason=reason))
    except Exception as e:
        log.error('[workflow email] {0}'.format(e))


def reject_approval(context, pkg, data):
    message = ('Your {type} {title} ({dataset_url}) was'
               ' rejected for publication by {admin}.\n'
               'Reason:\n'
               '{reason}')
    data['subject'] = 'SEED dataset rejection'
    return _approval_preparation(context, pkg, message, data)


def approve_approval(context, pkg, data={}):
    message = ('Your {type} {title} ({dataset_url}) was'
               ' approved for publication by {admin}.')
    data['subject'] = 'SEED dataset approval'
    original_id = workflow_helpers.get_original_dataset_id_from_package(pkg)
    if original_id:
        data['dataset_url'] = helpers.url_for('dataset_read',
                                              id=original_id,
                                              qualified=True)

    return _approval_preparation(context, pkg, message, data)


def unpublish_dataset(context, pkg, data={}):
    reason = data.get('reason', 'Not defined')
    subject = 'SEED dataset was unpublished'
    author = model.User.get(pkg['creator_user_id'])
    message = ("The SEED dataset {title} ({dataset_url})"
               " has been unpublished by {admin}.\n"
               "Reason:\n"
               "{reason}")
    try:
        if author is None:
            raise Exception('User <{0}> not found'.format(
                pkg['creator_user_id']))
        if not author.email:
            raise Exception('User <{0}> has no email'.format(author.name))

        mailer.mail_recipient(
            author.fullname or author.name, author.email, subject,
            message.format(title=pkg['title'],
                           dataset_url=helpers.url_for('dataset_read',
                                                       id=pkg['id'],
                                                       qualified=True),
                           admin=context['user'],
                           reason=reason))
    except Exception as e:
        log.error('[workflow email] {0}'.format(e))


class WorkflowPlugin(MixinPlugin, plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(IWorkflow)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IPermissionLabels)

    # IConfigurer

    def update_config(self, config_):
        tk.add_template_directory(config_, '../templates')
        tk.add_public_directory(config_, '../public')
        tk.add_resource('../fanstatic', 'workflow')
        Workflow.configure()

        Workflow.get_workflow(
            'base').start.approval_effect = submit_for_approval

        second_stage = Workflow.get_workflow('base').start.approve()
        second_stage.rejection_effect = reject_approval
        second_stage.approval_effect = approve_approval
        last_stage = Workflow.get_workflow('base').finish
        last_stage.rejection_effect = unpublish_dataset

    # IWorkflow

    def register_workflows(self):
        return dict(base=BaseWorkflow())

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


    # IPermissionLabels

    def get_dataset_labels(self, dataset_obj):
        field = workflow_helpers._workflow_stage_field()
        stage = getattr(dataset_obj, field,
                        None) or dataset_obj.extras.get(field)

        if not stage or stage in Workflow.get_all_finish_stages():
            return DefaultPermissionLabels().get_dataset_labels(dataset_obj)

        return [
            u'stage_{}_{}'.format(
                stage, dataset_obj.owner_org or dataset_obj.creator_user_id)
        ]

    def get_user_dataset_labels(self, user_obj):
        labels = DefaultPermissionLabels().get_user_dataset_labels(user_obj)
        if user_obj:
            orgs = tk.get_action(u'organization_list_for_user')(
                {
                    u'user': user_obj.id
                }, {
                    u'permission': u'admin'
                })

            labels.extend(u'stage_{}_{}'.format(s, o[u'id']) for o in orgs
                          for s in Workflow.get_all_stages())
        return labels

    # IPackageController

    def before_search(self, search_params):
        # workflow_helpers._workflow_stage_field(), ' OR '.join(Workflow.get_all_finish_stages())
        search_params['include_drafts'] = True
        return search_params

