from __future__ import annotations

import pytest

from ckan import model
from ckan.tests import factories, helpers

from ckanext.workflow.model import WorkflowInstance, WorkflowTask
from ckanext.workflow.plugin import WorkflowPlugin


@pytest.mark.usefixtures("clean_db")
class TestWorkflowPermissionLabels:

    def test_permission_labels_restricted_by_role(self):
        # Setup org and users
        org = factories.Organization()
        creator_user = factories.User()
        editor_user = factories.User()
        member_user = factories.User()

        # Add users to org using standard action
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=creator_user["name"],
            role="member"
        )
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=editor_user["name"],
            role="editor"
        )
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=member_user["name"],
            role="member"
        )

        # Create dataset
        dataset = factories.Dataset(owner_org=org["id"], creator_user_id=creator_user["id"])

        # Instantiate plugin
        plugin = WorkflowPlugin()

        # Initially, there is no active workflow instance. The labels should be default CKAN labels
        default_labels = plugin.get_dataset_labels(model.Package.get(dataset["id"]))
        assert "public" in default_labels or f"owner_org:{org['id']}" in default_labels

        # Create workflow instance and active task for 'editor' role
        wf_inst = WorkflowInstance(
            id="test-instance-uuid",
            object_id=dataset["id"],
            workflow_id=1,  # Mock ID
            current_step_index=0,
            status="active"
        )
        model.Session.add(wf_inst)

        task = WorkflowTask(
            instance_id=wf_inst.id,
            sequence=0,
            status="pending",
            assigned_role="editor"  # Only editors or admins can see/complete
        )
        model.Session.add(task)
        model.Session.commit()

        # Re-query package to ensure relations are clear
        pkg_obj = model.Package.get(dataset["id"])

        # Retrieve dataset permission labels
        labels = plugin.get_dataset_labels(pkg_obj)

        # Verify that 'public' is NOT in the labels
        assert "public" not in labels

        # Verify that creator can see the dataset
        assert f"user:{creator_user['name']}" in labels

        # Verify that org editors and admins can see the dataset
        assert f"workflow-role:{org['id']}:editor" in labels
        assert f"workflow-role:{org['id']}:admin" in labels

        # Verify that members cannot see it (member label is missing)
        assert f"workflow-role:{org['id']}:member" not in labels

        # Test user dataset labels
        editor_obj = model.User.get(editor_user["id"])
        member_obj = model.User.get(member_user["id"])

        editor_labels = plugin.get_user_dataset_labels(editor_obj)
        member_labels = plugin.get_user_dataset_labels(member_obj)

        # Editor should have editor and member role labels
        assert f"workflow-role:{org['id']}:editor" in editor_labels
        assert f"workflow-role:{org['id']}:member" in editor_labels

        # Member should have member label, but not editor
        assert f"workflow-role:{org['id']}:member" in member_labels
        assert f"workflow-role:{org['id']}:editor" not in member_labels
