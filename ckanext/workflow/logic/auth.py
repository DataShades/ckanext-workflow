# -*- coding: utf-8 -*-

import ckantoolkit as tk


def get_auth_functions():
    return {
        'workflow_state_change': workflow_state_change,
    }


def workflow_state_change(context, data_dict):
    tk.check_access('package_update', context, data_dict)
    return {'success': True}
