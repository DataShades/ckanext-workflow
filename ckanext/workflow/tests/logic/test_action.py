import pytest

import ckan.tests.helpers as helpers
import ckan.tests.factories as factories


@pytest.mark.usefixtures("clean_db", "app")
@pytest.mark.ckan_config("ckan.plugins", "workflow native_workflow")
def test_state_chage(app):
    org = factories.Organization()
    dataset = factories.Dataset(private=True, owner_org=org["id"])
    assert dataset["private"]

    helpers.call_action(
        "workflow_state_change", id=dataset["id"], private=False
    )
    dataset = helpers.call_action("package_show", id=dataset["id"])
    assert not dataset["private"]

    helpers.call_action(
        "workflow_state_change", id=dataset["id"], private=True
    )

    dataset = helpers.call_action("package_show", id=dataset["id"])
    assert dataset["private"]
