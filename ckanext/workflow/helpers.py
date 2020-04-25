# -*- coding: utf-8 -*-

import ckantoolkit as tk

import ckan.plugins as p

import ckanext.workflow.interface as interface


def get_helpers():
    return {}


def workflow_state_field():
    return tk.config.get('workflow.state_field', 'workflow_state')


def workflow_get_state(pkg_dict):
    """Return current state of the package.

    >>> workflow_get_state({}).name
    'private'
    >>> workflow_get_state({'private': False}).name
    'public'
    """
    states = [
        impl.get_state_for_package(pkg_dict)
        for impl in p.PluginImplementations(interface.IWorkflow)
    ]
    _, state = sorted(filter(None, states))[-1]

    return state
