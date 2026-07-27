from __future__ import annotations

import ckan.plugins.toolkit as tk

SHOW_ADMIN_TAB = "ckanext.workflow.ui.show_admin_tab"


def show_admin_tab() -> bool:
    """Display the tab for workflows in the CKAN Admin UI."""
    return tk.config[SHOW_ADMIN_TAB]
