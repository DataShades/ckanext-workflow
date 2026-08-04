from __future__ import annotations

import pytest

from ckan.plugins.toolkit import NotAuthorized
from ckan.tests import factories, helpers
from ckan.tests.helpers import call_auth

# Parametrize similar sysadmin-only actions
SYSADMIN_ONLY_ACTIONS = [
    "workflow_definition_create",
    "workflow_definition_update",
    "workflow_definition_delete",
    "workflow_definition_show",
    "workflow_definition_list",
    "workflow_instance_list",
]

@pytest.mark.ckan_config("ckan.plugins", "workflow")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestWorkflowAuth:

    @pytest.mark.parametrize("action_name", SYSADMIN_ONLY_ACTIONS)
    def test_sysadmin_only_actions_allowed_for_sysadmin(self, action_name):
        sysadmin = factories.Sysadmin()
        assert call_auth(action_name, {"user": sysadmin["name"]})

    @pytest.mark.parametrize("action_name", SYSADMIN_ONLY_ACTIONS)
    def test_sysadmin_only_actions_denied_for_normal_user(self, action_name):
        user = factories.User()
        with pytest.raises(NotAuthorized):
            call_auth(action_name, {"user": user["name"]})

    def test_workflow_task_complete_auth_by_role(self):
        org = factories.Organization()
        editor = factories.User()
        member = factories.User()

        # Add members to org
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=editor["name"],
            role="editor"
        )
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=member["name"],
            role="member"
        )

        # Mock package, instance, and task
        dataset = factories.Dataset(owner_org=org["id"])

        from ckan import model

        from ckanext.workflow.model import WorkflowDefinition, WorkflowInstance, WorkflowTask

        wf_def = WorkflowDefinition(name="Test", trigger_type="dataset_create", dataset_type="all")
        model.Session.add(wf_def)
        model.Session.flush()

        wf_inst = WorkflowInstance(
            id="auth-inst-uuid",
            object_id=dataset["id"],
            workflow_id=wf_def.id,
            current_step_index=0,
            status="active"
        )
        model.Session.add(wf_inst)

        task = WorkflowTask(
            instance_id=wf_inst.id,
            sequence=0,
            name="Mock Task",
            step_type="approval",
            status="pending",
            assigned_role="editor"
        )
        model.Session.add(task)
        model.Session.commit()

        # Editor should be allowed
        assert call_auth(
            "workflow_task_complete",
            {"user": editor["name"]},
            id=wf_inst.id,
            sequence=0
        )

        # Member should be denied
        with pytest.raises(NotAuthorized):
            call_auth(
                "workflow_task_complete",
                {"user": member["name"]},
                id=wf_inst.id,
                sequence=0
            )

    def test_workflow_instance_cancel_auth(self):
        org = factories.Organization()
        editor = factories.User()
        member = factories.User()

        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=editor["name"],
            role="editor"
        )
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=member["name"],
            role="member"
        )

        dataset = factories.Dataset(owner_org=org["id"])

        from ckan import model

        from ckanext.workflow.model import WorkflowDefinition, WorkflowInstance

        wf_def = WorkflowDefinition(name="Test", trigger_type="dataset_create", dataset_type="all")
        model.Session.add(wf_def)
        model.Session.flush()

        wf_inst = WorkflowInstance(
            id="cancel-inst-uuid",
            object_id=dataset["id"],
            workflow_id=wf_def.id,
            current_step_index=0,
            status="active"
        )
        model.Session.add(wf_inst)
        model.Session.commit()

        # Editor (has update access to package) should be allowed to cancel
        assert call_auth(
            "workflow_instance_cancel",
            {"user": editor["name"]},
            id=wf_inst.id
        )

        # Member (no update access to package) should be denied
        with pytest.raises(NotAuthorized):
            call_auth(
                "workflow_instance_cancel",
                {"user": member["name"]},
                id=wf_inst.id
            )
