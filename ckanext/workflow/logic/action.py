# -*- coding: utf-8 -*-
import ckantoolkit as tk


def get_actions():
    return {
        'workflow_state_change': workflow_state_change,
    }


def workflow_state_change(context, data_dict):
    id = tk.get_or_bust(data_dict, 'id')
    tk.check_access('workflow_state_change', context, data_dict)
    pkg = tk.get_action('package_show')(context, {'id': id})
    state = tk.h.workflow_get_state(pkg)
    if data_dict.get('back'):
        state = state.prev()
    else:
        state = state.next()
    return state.save(context)
