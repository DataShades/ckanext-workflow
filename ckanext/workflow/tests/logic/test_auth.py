
import pytest
import ckantoolkit as tk

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
import ckan.model as model


def test_workflow_change_state_anon(app):
    context = {'model': model, 'user': ''}

    with pytest.raises(tk.NotAuthorized):
        helpers.call_auth('workflow_state_change', context)


@pytest.mark.usefixtures('clean_db')
def test_workflow_state_change(app):
    user = factories.User()
    another_user = factories.User()
    org = factories.Organization(user=user)

    dataset = factories.Dataset(user=user, owner_org=org['id'])

    context = {'model': model, 'user': another_user['name']}
    with pytest.raises(tk.NotAuthorized):
        helpers.call_auth('workflow_state_change', context, id=dataset['id'])

    context = {'model': model, 'user': user['name']}
    helpers.call_auth('workflow_state_change', context, id=dataset['id'])
