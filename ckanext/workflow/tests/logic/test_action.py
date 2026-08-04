# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from ckan import model
from ckan.tests import factories, helpers
from ckanext.workflow.model import WorkflowDefinition, WorkflowInstance, WorkflowTask, WorkflowStep

@pytest.mark.ckan_config("ckan.plugins", "workflow")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestWorkflowDefinitionActions:

    def test_workflow_definition_create(self):
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
        
        data_dict = {
            "name": "Test Workflow",
            "description": "My test workflow description",
            "enabled": True,
            "trigger_type": "dataset_create",
            "dataset_type": "all",
            "steps": steps
        }
        
        result = helpers.call_action("workflow_definition_create", **data_dict)
        assert result["name"] == "Test Workflow"
        assert result["enabled"] is True
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "Step 1"

    def test_workflow_definition_update(self):
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
        
        result = helpers.call_action("workflow_definition_update", **data_dict)
        assert result["name"] == "New Name"
        assert result["enabled"] is False
        assert len(result["steps"]) == 1
        assert result["steps"][0]["name"] == "New Step 1"

    def test_workflow_definition_show(self):
        wf = WorkflowDefinition(
            name="Show Workflow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all"
        )
        model.Session.add(wf)
        model.Session.commit()
        
        result = helpers.call_action("workflow_definition_show", id=wf.id)
        assert result["name"] == "Show Workflow"

    def test_workflow_definition_delete(self):
        wf = WorkflowDefinition(
            name="Delete Workflow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all"
        )
        model.Session.add(wf)
        model.Session.commit()
        
        helpers.call_action("workflow_definition_delete", id=wf.id)
        
        deleted_wf = model.Session.get(WorkflowDefinition, wf.id)
        assert deleted_wf is None


@pytest.mark.ckan_config("ckan.plugins", "workflow")
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestWorkflowExecution:

    def test_workflow_start_and_progression(self):
        org = factories.Organization()
        admin_user = factories.User()
        editor_user = factories.User()
        
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
        
        # Create workflow definition
        helpers.call_action(
            "workflow_definition_create",
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
        
        # Create dataset (triggers after_dataset_create)
        dataset = helpers.call_action(
            "package_create",
            name="publication-dataset",
            owner_org=org["id"]
        )
        
        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None
        assert instance.status == "active"
        assert instance.current_step_index == 0
        
        # Complete step 0 as editor
        res = helpers.call_action(
            "workflow_task_complete",
            {"user": editor_user["name"]},
            id=instance.id,
            sequence=0,
            action_type="approve",
            comment="Approved by Editor"
        )
        assert res["success"] is True
        
        model.Session.refresh(instance)
        assert instance.current_step_index == 1
        
        # Complete step 1 as admin
        res = helpers.call_action(
            "workflow_task_complete",
            {"user": admin_user["name"]},
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

    def test_workflow_cancel(self):
        org = factories.Organization()
        
        helpers.call_action(
            "workflow_definition_create",
            name="Confidential Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "User 1 Review",
                    "assigned_role": "editor",
                    "step_type": "approval",
                    "instructions": "Private review",
                    "post_actions": {}
                }
            ]
        )
        
        dataset = helpers.call_action(
            "package_create",
            name="confidential-dataset",
            owner_org=org["id"]
        )
        
        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None
        
        res = helpers.call_action(
            "workflow_instance_cancel",
            id=instance.id
        )
        assert res["success"] is True
        
        model.Session.refresh(instance)
        assert instance.status == "cancelled"
