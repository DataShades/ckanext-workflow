# -*- coding: utf-8 -*-

import ckantoolkit as tk


def get_helpers():
    return {

    }


def workflow_get_state(pkg_dict):
    """Return current state of the package.

    >>> workflow_get_state({})
    'unpublished'

    """
    return 'unpublished'
