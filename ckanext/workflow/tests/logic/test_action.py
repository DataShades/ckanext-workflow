import pytest

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories


@pytest.mark.usefixtures('clean_db')
def test_state_chage(app):
    org = factories.Organization()
    dataset = factories.Dataset(private=True, owner_org=org['id'])
    assert dataset['private']

    helpers.call_action('workflow_state_change', id=dataset['id'])
    dataset = helpers.call_action('package_show', id=dataset['id'])
    assert not dataset['private']

    helpers.call_action('workflow_state_change', id=dataset['id'], back=True)

    dataset = helpers.call_action('package_show', id=dataset['id'])
    assert dataset['private']
