import pytest

import ckantoolkit as tk

import ckanext.workflow.states as states
import ckanext.workflow.tests.states as test_states


@pytest.mark.usefixtures('app')
def test_state_field_default():
    assert tk.h.workflow_state_field() == 'workflow_state'


@pytest.mark.ckan_config('workflow.state_field', 'state')
@pytest.mark.usefixtures('app')
def test_state_field_customized():
    assert tk.h.workflow_state_field() == 'state'


@pytest.mark.parametrize('private,state', [
    (True, states.PrivateState),
    (False, states.PublicState),
])
@pytest.mark.usefixtures('app')
def test_get_state_default(private, state):
    dataset = {'private': private}
    assert isinstance(tk.h.workflow_get_state(dataset), state)


@pytest.mark.ckan_config('ckan.plugins', 'workflow test_workflow')
@pytest.mark.usefixtures('with_plugins', 'app')
def test_get_state_custom():

    dataset = {'private': True, 'state': 'draft'}
    assert isinstance(tk.h.workflow_get_state(dataset), test_states.DraftState)

    dataset = {'private': True, 'state': 'active'}
    assert isinstance(tk.h.workflow_get_state(
        dataset), test_states.ReviewState)

    dataset = {'private': False, 'state': 'active'}
    assert isinstance(tk.h.workflow_get_state(
        dataset), test_states.PublishedState)
