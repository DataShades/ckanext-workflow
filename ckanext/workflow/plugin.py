# -*- coding: utf-8 -*-

import ckantoolkit as tk

import ckan.plugins as p

from ckan.lib.plugins import DefaultPermissionLabels


import ckanext.workflow.helpers as helpers
import ckanext.workflow.logic.action as action
import ckanext.workflow.logic.auth as auth
import ckanext.workflow.interface as interface
import ckanext.workflow.states as states
import ckanext.workflow.utils as utils


class WorkflowPlugin(p.SingletonPlugin, DefaultPermissionLabels):
    p.implements(p.ITemplateHelpers)
    p.implements(p.IAuthFunctions)
    p.implements(p.IActions)
    p.implements(p.IPermissionLabels, inherit=True)
    p.implements(interface.IWorkflow)

    # ITemplateHelpers

    def get_helpers(self):
        return helpers.get_helpers()

    # IAuthFunctions

    def get_auth_functions(self):
        return auth.get_auth_functions()

    # IActions

    def get_actions(self):
        return action.get_actions()

    # IPermissionLabels

    def get_dataset_labels(self, dataset_obj):
        state = tk.h.workflow_get_state(dataset_obj.as_dict())
        labels = state.get_dataset_labels()
        if labels:
            return labels
        return super(WorkflowPlugin, self).get_dataset_labels(dataset_obj)

    # IWorkflow

    def get_state_for_package(self, pkg_dict):
        private = pkg_dict.get('private', True)
        State = states.PrivateState if private else states.PublicState
        return State(pkg_dict).with_weight(utils.StateWeight.fallback)
