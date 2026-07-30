from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan.tests import factories, helpers


@pytest.mark.usefixtures("clean_db")
class TestWorkflowAuth:

    def test_workflow_definition_create_auth(self):
        user = factories.User()

        # Non-sysadmin user trying to create a workflow definition should fail
        with pytest.raises(tk.NotAuthorized):
            helpers.call_action(
                "workflow_definition_create",
                {"user": user["name"]},
                name="Test Workflow",
                steps=[]
            )
