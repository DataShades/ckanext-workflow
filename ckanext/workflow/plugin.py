from __future__ import annotations

from typing import Any

from typing_extensions import override

import ckan.plugins as p
import ckan.plugins.toolkit as tk
from ckan import types
from ckan.common import CKANConfig

from ckanext.theming.plugin import ThemingMixin

from ckanext.workflow.service import start_workflow


@tk.blanket.cli
@tk.blanket.helpers
@tk.blanket.actions
@tk.blanket.auth_functions
@tk.blanket.blueprints
@tk.blanket.config_declarations
class WorkflowPlugin(ThemingMixin, p.IPackageController, p.IConfigurer, p.SingletonPlugin):
    # IConfigurer
    @override
    def update_config(self, config: CKANConfig) -> None:
        super().update_config(config)
        tk.add_template_directory(config, "templates")
        tk.add_resource("assets", "workflow")

    # IPackageController
    @override
    def after_dataset_create(self, context: types.Context, pkg_dict: dict[str, Any]) -> None:
        if context.get("ignore_workflow") or context.get("ignore_auth"):
            return

        start_workflow(pkg_dict)

    @override
    def after_dataset_update(self, context: types.Context, pkg_dict: dict[str, Any]) -> None:
        if context.get("ignore_workflow") or context.get("ignore_auth"):
            return

        # # If there's an active workflow for this package, keep its state draft
        # inst = WorkflowService.get_instance_for_package(pkg_dict["id"])
        # user = tk.get_action("get_site_user")({"ignore_auth": True}, {})
        # if inst and pkg_dict.get("state") == "active":
        #     context_sys = types.Context(ignore_auth=True, user=user["name"])
        #     tk.get_action("package_patch")(context_sys, {"id": pkg_dict["id"], "state": "draft"})
