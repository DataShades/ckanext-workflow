# -*- coding: utf-8 -*-

import ckantoolkit as tk

import ckan.plugins as p

import ckanext.workflow.interface as interface


def get_helpers():
    return {
        'workflow_state_field': workflow_state_field,
        'workflow_get_state': workflow_get_state,
    }


def workflow_state_field():
    return tk.config.get('workflow.state_field', 'workflow_state')


def workflow_get_state(pkg_dict):
    """Return current state of the package.

    >>> workflow_get_state({}).name
    'private'
    >>> workflow_get_state({'private': False}).name
    'public'
    """
    states_with_weight = sorted(filter(None, [
        impl.get_state_for_package(pkg_dict)
        for impl in p.PluginImplementations(interface.IWorkflow)
    ]))
    states = [
        state for (weight, state) in states_with_weight
        if weight > 0
    ]

    return states[-1] if states else None
