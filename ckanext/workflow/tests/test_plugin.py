
import pytest

import ckantoolkit as tk

import ckanext.workflow.tests.states as states


@pytest.mark.ckan_config('ckan.plugins', 'workflow test_workflow test_workflow_override')
@pytest.mark.usefixtures('with_plugins')
def test_state_priority():
    dataset = {'state': 'draft'}
    assert isinstance(tk.h.workflow_get_state(dataset), states.DraftState)

    dataset = {'state': 'active', 'private': True}
    assert isinstance(tk.h.workflow_get_state(
        dataset), states.OverridenReviewState)

    dataset = {'state': 'active', 'private': False}
    assert isinstance(tk.h.workflow_get_state(dataset), states.PublishedState)


@pytest.mark.ckan_config('ckan.plugins', 'workflow test_workflow')
@pytest.mark.usefixtures('with_plugins', 'clean_db', 'clean_index')
def test_search_labels():
    assert False
