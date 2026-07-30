from __future__ import annotations

import pytest

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.tests import factories, helpers

from ckanext.workflow.model import WorkflowDefinition, WorkflowInstance, WorkflowStep


@pytest.mark.usefixtures("clean_db")
class TestWorkflowDefinitionActions:

    def test_workflow_definition_create(self):
        sysadmin = factories.Sysadmin()

        steps = [
            {
                "name": "Step 1",
                "assigned_role": "editor",
                "step_type": "approval",
                "instructions": "Verify data",
                "post_actions": {"on_approve": []}
            },
            {
                "name": "Step 2",
                "assigned_role": "admin",
                "step_type": "manual_task",
                "instructions": "Publish data",
                "post_actions": {"on_complete": []}
            }
        ]

        context = {"user": sysadmin["name"]}
        data_dict = {
            "name": "Test Workflow",
            "description": "My test workflow description",
            "enabled": True,
            "trigger_type": "dataset_create",
            "dataset_type": "all",
            "steps": steps
        }

        result = helpers.call_action("workflow_definition_create", context, **data_dict)
        assert result["name"] == "Test Workflow"
        assert result["enabled"] is True
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "Step 1"

    def test_workflow_definition_update(self):
        sysadmin = factories.Sysadmin()

        wf = WorkflowDefinition(
            name="Old Name",
            description="Old Desc",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all"
        )
        model.Session.add(wf)
        model.Session.flush()

        step = WorkflowStep(
            workflow_id=wf.id,
            sequence=0,
            name="Old Step",
            assigned_role="editor",
            step_type="approval",
            post_actions={}
        )
        model.Session.add(step)
        model.Session.commit()

        context = {"user": sysadmin["name"]}
        data_dict = {
            "id": wf.id,
            "name": "New Name",
            "description": "New Desc",
            "enabled": False,
            "trigger_type": "dataset_create",
            "dataset_type": "all",
            "steps": [
                {
                    "name": "New Step 1",
                    "assigned_role": "admin",
                    "step_type": "manual_task",
                    "instructions": "Do something",
                    "post_actions": {}
                }
            ]
        }

        result = helpers.call_action("workflow_definition_update", context, **data_dict)
        assert result["name"] == "New Name"
        assert result["enabled"] is False
        assert len(result["steps"]) == 1
        assert result["steps"][0]["name"] == "New Step 1"

    def test_workflow_definition_show(self):
        sysadmin = factories.Sysadmin()
        wf = WorkflowDefinition(
            name="Show Workflow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all"
        )
        model.Session.add(wf)
        model.Session.commit()

        context = {"user": sysadmin["name"]}
        result = helpers.call_action("workflow_definition_show", context, id=wf.id)
        assert result["name"] == "Show Workflow"

    def test_workflow_definition_delete(self):
        sysadmin = factories.Sysadmin()
        wf = WorkflowDefinition(
            name="Delete Workflow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all"
        )
        model.Session.add(wf)
        model.Session.commit()

        context = {"user": sysadmin["name"]}
        helpers.call_action("workflow_definition_delete", context, id=wf.id)

        deleted_wf = model.Session.get(WorkflowDefinition, wf.id)
        assert deleted_wf is None


@pytest.mark.usefixtures("clean_db")
class TestWorkflowExecution:

    def test_workflow_start_and_progression(self):
        org = factories.Organization()
        admin_user = factories.User()
        editor_user = factories.User()
        member_user = factories.User()

        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=admin_user["name"],
            role="admin"
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

        sysadmin = factories.Sysadmin()
        helpers.call_action(
            "workflow_definition_create",
            {"user": sysadmin["name"]},
            name="Publication Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "Editor Approval",
                    "assigned_role": "editor",
                    "step_type": "approval",
                    "instructions": "Please approve content",
                    "post_actions": {}
                },
                {
                    "name": "Admin Manual Task",
                    "assigned_role": "admin",
                    "step_type": "manual_task",
                    "instructions": "Do final publication check",
                    "post_actions": {"on_complete": [{"type": "change_field", "field": "notes", "value": "Approved!"}]}
                }
            ]
        )

        dataset = factories.Dataset(owner_org=org["id"], state="active")

        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None
        assert instance.status == "active"
        assert instance.current_step_index == 0

        updated_dataset = helpers.call_action("package_show", id=dataset["id"])
        assert updated_dataset["state"] == "draft"

        context = {"user": member_user["name"]}
        with pytest.raises(tk.ValidationError) as excinfo:
            helpers.call_action(
                "workflow_task_complete",
                context,
                id=instance.id,
                sequence=0,
                action_type="approve",
                comment="Looks good to me"
            )
        assert "Unauthorized to complete this step" in str(excinfo.value)

        context = {"user": editor_user["name"]}
        res = helpers.call_action(
            "workflow_task_complete",
            context,
            id=instance.id,
            sequence=0,
            action_type="approve",
            comment="Approved by Editor"
        )
        assert res["success"] is True

        model.Session.refresh(instance)
        assert instance.current_step_index == 1

        context = {"user": admin_user["name"]}
        res = helpers.call_action(
            "workflow_task_complete",
            context,
            id=instance.id,
            sequence=1,
            action_type="complete",
            comment="Completed by Admin"
        )
        assert res["success"] is True

        model.Session.refresh(instance)
        assert instance.status == "completed"

        published_dataset = helpers.call_action("package_show", id=dataset["id"])
        assert published_dataset["state"] == "active"
        assert published_dataset["notes"] == "Approved!"

    def test_workflow_cancel_and_user_assignment(self):
        org = factories.Organization()
        sysadmin = factories.Sysadmin()
        user1 = factories.User()
        user2 = factories.User()

        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=user1["name"],
            role="member"
        )
        helpers.call_action(
            "organization_member_create",
            id=org["id"],
            username=user2["name"],
            role="member"
        )

        helpers.call_action(
            "workflow_definition_create",
            {"user": sysadmin["name"]},
            name="Confidential Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "User 1 Review",
                    "assigned_role": f"user:{user1['name']}",
                    "step_type": "approval",
                    "instructions": "Private review",
                    "post_actions": {}
                }
            ]
        )

        dataset = factories.Dataset(owner_org=org["id"])
        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None

        with pytest.raises(tk.ValidationError) as excinfo:
            helpers.call_action(
                "workflow_task_complete",
                {"user": user2["name"]},
                id=instance.id,
                sequence=0,
                action_type="approve"
            )
        assert "Unauthorized to complete this step" in str(excinfo.value)

        res = helpers.call_action(
            "workflow_instance_cancel",
            {"user": user1["name"]},
            id=instance.id
        )
        assert res["success"] is True

        model.Session.refresh(instance)
        assert instance.status == "cancelled"
