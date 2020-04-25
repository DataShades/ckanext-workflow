# -*- coding: utf-8 -*-

import ckan.plugins as p

import ckanext.workflow.helpers as helpers
import ckanext.workflow.logic.action as action
import ckanext.workflow.logic.auth as auth


class WorkflowPlugin(p.SingletonPlugin):
    p.implements(p.ITemplateHelpers)
    p.implements(p.IAuthFunctions)
    p.implements(p.IActions)

    # ITemplateHelpers

    def get_helpers(self):
        return helpers.get_helpers()

    # IAuthFunctions

    def get_auth_functions(self):
        return auth.get_auth_functions()

    # IActions

    def get_actions(self):
        return action.get_actions()
