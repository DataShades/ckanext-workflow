# -*- coding: utf-8 -*-

import ckantoolkit as tk

import ckan.plugins as p

import ckanext.workflow.interface as interface


def get_helpers():
    return {
        "workflow_state_field": workflow_state_field,
        "workflow_get_state": workflow_get_state,
    }


def workflow_state_field():
    return tk.config.get("workflow.state_field", "workflow_state")


def workflow_get_state(pkg_dict):
    """Return current state of the package.

    >>> workflow_get_state({}).name
    'private'
    >>> workflow_get_state({'private': False}).name
    'public'
    """
    for impl in p.PluginImplementations(interface.IWorkflow):
        state = impl.get_state_for_package(pkg_dict)
        if state:
            return state
