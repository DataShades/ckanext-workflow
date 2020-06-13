# -*- coding: utf-8 -*-
import ckantoolkit as tk


def get_actions():
    return {
        "workflow_state_change": workflow_state_change,
    }


def workflow_state_change(context, data_dict):
    """Update state of the dataset.

    The only mandatory key in `data_dict` is `id`, which represents
    updated package. Rest of items will be passed to the
    `State.change` method.

    :param id: id of updated package.
    :type id: str

    """
    id = tk.get_or_bust(data_dict, "id")
    tk.check_access("workflow_state_change", context, data_dict)
    pkg = tk.get_action("package_show")(context.copy(), {"id": id})
    state = tk.h.workflow_get_state(pkg)
    state = state.change(data_dict)
    return state.save(context.copy())
