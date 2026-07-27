import pytest
from ckanext.workflow.service import WorkflowService

def test_workflow_service_get_definitions():
    defs = WorkflowService.get_definitions()
    assert isinstance(defs, list)
