
from __future__ import annotations

import pytest

from ckan import model
from ckan.plugins import toolkit as tk
from ckan.tests import factories, helpers

from ckanext.workflow.model import WorkflowDefinition, WorkflowInstance, WorkflowStep


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
                "config": {"on_approve": []},
            },
            {
                "name": "Step 2",
                "assigned_role": "admin",
                "step_type": "manual_task",
                "instructions": "Publish data",
                "config": {"on_complete": []},
            },
        ]

        data_dict = {
            "name": "Test Workflow",
            "description": "My test workflow description",
            "enabled": True,
            "trigger_type": "dataset_create",
            "dataset_type": "all",
            "steps": steps,
        }

        result = helpers.call_action("workflow_definition_create", **data_dict)
        assert result["name"] == "Test Workflow"
        assert result["enabled"] is True
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "Step 1"

    def test_workflow_definition_update(self):
        wf = WorkflowDefinition(
            name="Old Name", description="Old Desc", enabled=True, trigger_type="dataset_create", dataset_type="all"
        )
        model.Session.add(wf)
        model.Session.flush()

        step = WorkflowStep(
            workflow_id=wf.id, sequence=0, name="Old Step", assigned_role="editor", step_type="approval", config={}
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
                    "config": {},
                }
            ],
        }

        result = helpers.call_action("workflow_definition_update", **data_dict)
        assert result["name"] == "New Name"
        assert result["enabled"] is False
        assert len(result["steps"]) == 1
        assert result["steps"][0]["name"] == "New Step 1"

    def test_workflow_definition_show(self):
        wf = WorkflowDefinition(name="Show Workflow", enabled=True, trigger_type="dataset_create", dataset_type="all")
        model.Session.add(wf)
        model.Session.commit()

        result = helpers.call_action("workflow_definition_show", id=wf.id)
        assert result["name"] == "Show Workflow"

    def test_workflow_definition_delete(self):
        wf = WorkflowDefinition(name="Delete Workflow", enabled=True, trigger_type="dataset_create", dataset_type="all")
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

        helpers.call_action("organization_member_create", id=org["id"], username=admin_user["name"], role="admin")
        helpers.call_action("organization_member_create", id=org["id"], username=editor_user["name"], role="editor")

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
                    "config": {},
                },
                {
                    "name": "Admin Manual Task",
                    "assigned_role": "admin",
                    "step_type": "manual_task",
                    "instructions": "Do final publication check",
                    "config": {"on_complete": [{"type": "change_field", "field": "notes", "value": "Approved!"}]},
                },
            ],
        )

        # Create dataset (triggers after_dataset_create)
        dataset = helpers.call_action("package_create", name="publication-dataset", owner_org=org["id"])

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
            comment="Approved by Editor",
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
            comment="Completed by Admin",
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
                    "config": {},
                }
            ],
        )

        dataset = helpers.call_action("package_create", name="confidential-dataset", owner_org=org["id"])

        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None

        res = helpers.call_action("workflow_instance_cancel", id=instance.id)
        assert res["success"] is True

        model.Session.refresh(instance)
        assert instance.status == "cancelled"

    def test_workflow_timeout_duration_validation(self):
        steps = [
            {
                "name": "Step 1",
                "assigned_role": "editor",
                "step_type": "approval",
                "instructions": "Verify data",
                "timeout_duration": "1d 4h",
                "config": {},
            }
        ]

        result = helpers.call_action(
            "workflow_definition_create",
            name="Timeout Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=steps,
        )

        # Verify the returned value has formatted timeout duration
        assert result["steps"][0]["timeout_duration"] == "1d 4h"

        # Verify that show action also formats it correctly
        show_result = helpers.call_action("workflow_definition_show", id=result["id"])
        assert show_result["steps"][0]["timeout_duration"] == "1d 4h"

        # Verify the database stores the value as integer of seconds (100800)
        from ckanext.workflow.model import WorkflowStep

        db_step = model.Session.query(WorkflowStep).filter(WorkflowStep.workflow_id == result["id"]).first()
        assert db_step.timeout_duration == 100800

    def test_workflow_multiple_triggers(self):
        org = factories.Organization()

        # Workflow triggered on UPDATE or MANUAL
        helpers.call_action(
            "workflow_definition_create",
            name="Update Flow",
            enabled=True,
            trigger_type=["update", "manual"],
            dataset_type="all",
            steps=[
                {
                    "name": "Step 1",
                    "assigned_role": "editor",
                    "step_type": "approval",
                    "instructions": "Update review",
                    "config": {},
                }
            ],
        )

        # Create dataset (should NOT trigger workflow because "create" trigger is not configured)
        dataset = helpers.call_action("package_create", name="no-trigger-dataset", owner_org=org["id"])

        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is None

        # Update dataset (should trigger workflow since "update" is configured)
        helpers.call_action(
            "package_update", id=dataset["id"], name="no-trigger-dataset", title="Updated Title", owner_org=org["id"]
        )

        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None
        assert instance.status == "active"

    def test_workflow_non_linear_rejection_flow(self):
        org = factories.Organization()
        admin_user = factories.User()

        helpers.call_action("organization_member_create", id=org["id"], username=admin_user["name"], role="admin")

        # Define workflow with custom rejection transition to Step 0 (sequence=0)
        helpers.call_action(
            "workflow_definition_create",
            name="Rejection Loop Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "Initial Manual Task",
                    "assigned_role": "admin",
                    "step_type": "manual_task",
                    "instructions": "Upload proper files",
                    "config": {},
                },
                {
                    "name": "Approval Task",
                    "assigned_role": "admin",
                    "step_type": "approval",
                    "instructions": "Verify files",
                    "config": {"on_reject_transition": "step:0"},
                },
            ],
        )

        dataset = helpers.call_action("package_create", name="loop-dataset", owner_org=org["id"])

        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None
        assert instance.current_step_index == 0

        # Complete step 0
        helpers.call_action(
            "workflow_task_complete", {"user": admin_user["name"]}, id=instance.id, sequence=0, action_type="complete"
        )

        model.Session.refresh(instance)
        assert instance.current_step_index == 1

        # Reject step 1. Should transition back to step 0 and reset task status to pending.
        helpers.call_action(
            "workflow_task_complete",
            {"user": admin_user["name"]},
            id=instance.id,
            sequence=1,
            action_type="reject",
            comment="Wrong files uploaded",
        )

        model.Session.refresh(instance)
        assert instance.current_step_index == 0
        assert instance.status == "active"

        # Check task statuses
        task0 = next(t for t in instance.tasks if t.sequence == 0)
        task1 = next(t for t in instance.tasks if t.sequence == 1)
        assert task0.status == "pending"
        assert task1.status == "pending"

    def test_workflow_branching_step(self):
        org = factories.Organization()
        admin_user = factories.User()

        helpers.call_action("organization_member_create", id=org["id"], username=admin_user["name"], role="admin")

        # Define branching workflow
        # Step 0: Branching Decision
        # Step 1: Path B
        # Step 2: Path A
        helpers.call_action(
            "workflow_definition_create",
            name="Branching Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "Decision Step",
                    "assigned_role": "admin",
                    "step_type": "branching",
                    "config": {
                        "branch_a_label": "Go To Path A",
                        "branch_a_transition": "step:2",
                        "branch_b_label": "Go To Path B",
                        "branch_b_transition": "step:1",
                    },
                },
                {"name": "Path B Step", "assigned_role": "admin", "step_type": "manual_task", "config": {}},
                {"name": "Path A Step", "assigned_role": "admin", "step_type": "manual_task", "config": {}},
            ],
        )

        dataset = helpers.call_action("package_create", name="branching-dataset", owner_org=org["id"])

        instance = model.Session.query(WorkflowInstance).filter(WorkflowInstance.object_id == dataset["id"]).first()
        assert instance is not None

        # Execute Option A (branch_a). Should skip step 1 and jump directly to step 2.
        helpers.call_action(
            "workflow_task_complete", {"user": admin_user["name"]}, id=instance.id, sequence=0, action_type="branch_a"
        )

        model.Session.refresh(instance)
        assert instance.current_step_index == 2
        assert instance.status == "active"

        task0 = next(t for t in instance.tasks if t.sequence == 0)
        task1 = next(t for t in instance.tasks if t.sequence == 1)
        task2 = next(t for t in instance.tasks if t.sequence == 2)

        assert task0.status == "completed"
        assert "Selected option: Go To Path A" in task0.comments
        assert task1.status == "skipped"
        assert task2.status == "pending"

    def test_workflow_definition_update_constraints_with_active_instances(self):
        org = factories.Organization()

        # 1. Create a workflow definition
        wf = helpers.call_action(
            "workflow_definition_create",
            name="Constraint Flow",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "Step 1",
                    "assigned_role": "editor",
                    "step_type": "approval",
                    "instructions": "Private review",
                    "config": {},
                },
                {
                    "name": "Step 2",
                    "assigned_role": "editor",
                    "step_type": "manual_task",
                    "instructions": "Upload documentation",
                    "config": {},
                },
            ],
        )

        # 2. Spawn an active instance by creating a dataset
        helpers.call_action("package_create", name="constraint-dataset", owner_org=org["id"])

        # 3. Try to update by removing a step (should fail)
        import pytest

        with pytest.raises(tk.ValidationError) as excinfo:
            helpers.call_action(
                "workflow_definition_update",
                id=wf["id"],
                name="Constraint Flow",
                enabled=True,
                trigger_type="dataset_create",
                dataset_type="all",
                steps=[
                    {
                        "name": "Step 1",
                        "assigned_role": "editor",
                        "step_type": "approval",
                        "instructions": "Private review",
                        "config": {},
                    }
                ],
            )
        assert "Cannot remove steps when there are incomplete workflow instances" in str(excinfo.value)

        # 4. Try to update by changing a step type (should fail)
        with pytest.raises(tk.ValidationError) as excinfo:
            helpers.call_action(
                "workflow_definition_update",
                id=wf["id"],
                name="Constraint Flow",
                enabled=True,
                trigger_type="dataset_create",
                dataset_type="all",
                steps=[
                    {
                        "name": "Step 1",
                        "assigned_role": "editor",
                        "step_type": "manual_task",  # Changed from approval
                        "instructions": "Private review",
                        "config": {},
                    },
                    {
                        "name": "Step 2",
                        "assigned_role": "editor",
                        "step_type": "manual_task",
                        "instructions": "Upload documentation",
                        "config": {},
                    },
                ],
            )
        assert "Cannot change step type or swap step" in str(excinfo.value)

        # 5. Try to update by modifying non-restricted fields or adding steps (should succeed)
        updated = helpers.call_action(
            "workflow_definition_update",
            id=wf["id"],
            name="Constraint Flow Updated",
            enabled=True,
            trigger_type="dataset_create",
            dataset_type="all",
            steps=[
                {
                    "name": "Step 1 Renamed",  # Renamed name is ok
                    "assigned_role": "editor",
                    "step_type": "approval",  # Kept type same
                    "instructions": "Private review updated",
                    "config": {},
                },
                {
                    "name": "Step 2",
                    "assigned_role": "admin",  # Changed role is ok
                    "step_type": "manual_task",  # Kept type same
                    "instructions": "Upload documentation",
                    "config": {},
                },
                {
                    "name": "Step 3 Added",  # Addition is ok
                    "assigned_role": "editor",
                    "step_type": "manual_task",
                    "instructions": "Final touch",
                    "config": {},
                },
            ],
        )
        assert updated["name"] == "Constraint Flow Updated"
        assert len(updated["steps"]) == 3

    def test_workflow_mermaid_chart_generation(self):
        from ckanext.workflow.views import generate_mermaid_chart

        wf = {
            "steps": [
                {"name": "Step 1", "step_type": "manual_task", "assigned_role": "editor", "config": {}},
                {
                    "name": "Step 2",
                    "step_type": "approval",
                    "assigned_role": "admin",
                    "config": {"on_reject_transition": "step:0"},
                },
                {
                    "name": "Step 3 Decision",
                    "step_type": "branching",
                    "assigned_role": "admin",
                    "config": {
                        "branch_a_label": "Jump to 5",
                        "branch_a_transition": "step:4",
                        "branch_b_label": "Go to 4",
                        "branch_b_transition": "step:3",
                    },
                },
                {"name": "Step 4", "step_type": "manual_task", "assigned_role": "editor", "config": {}},
                {
                    "name": "Step 5",
                    "step_type": "automated_task",
                    "instructions": "validation_task",
                    "config": {"on_failure_transition": "step:1"},
                },
            ]
        }

        chart = generate_mermaid_chart(wf)

        # Verify definitions
        assert 'Step0["Step 1: Step 1<br/>(MANUAL_TASK)<br/>Role: editor"]' in chart
        assert 'Step1["Step 2: Step 2<br/>(APPROVAL)<br/>Role: admin"]' in chart
        assert 'Step2{"Step 3: Step 3 Decision<br/>(BRANCHING)<br/>Role: admin"}' in chart
        assert 'Step3["Step 4: Step 4<br/>(MANUAL_TASK)<br/>Role: editor"]' in chart
        assert 'Step4["Step 5: Step 5<br/>(AUTOMATED_TASK)"]' in chart

        # Verify connections
        assert "Start --> Step0" in chart
        assert "Step0 -->|Complete| Step1" in chart
        assert "Step1 -->|Approve| Step2" in chart
        assert "Step1 -->|Reject| Step0" in chart
        assert "Step2 -->|Jump to 5| Step4" in chart
        assert "Step2 -->|Go to 4| Step3" in chart
        assert "Step3 -->|Complete| Step4" in chart
        assert "Step4 -->|Success| Published([Published])" in chart
        assert "Step4 -->|Failure| Step1" in chart

        # Verify outcome highlights
        completed_chart = generate_mermaid_chart(wf, instance_status="completed")
        assert "style Published fill:#d4edda,stroke:#28a745,stroke-width:3px;" in completed_chart

        rejected_chart = generate_mermaid_chart(wf, instance_status="rejected")
        assert "style Rejected fill:#f8d7da,stroke:#dc3545,stroke-width:3px;" in rejected_chart
