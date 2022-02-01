import pytest

import ckantoolkit as tk

import ckan.model as model
import ckan.lib.search as search
import ckan.tests.helpers as helpers
import ckan.tests.factories as factories
import ckanext.workflow.tests.states as states


@pytest.mark.ckan_config("ckan.plugins", "workflow test_workflow")
@pytest.mark.usefixtures("with_plugins", "clean_db", "clean_index")
def test_search_labels():
    user = factories.User()
    org = factories.Organization(user=user)
    dataset = factories.Dataset(
        private=True, state="draft", owner_org=org["id"], user=user
    )

    context = {"user": user["name"]}

    search_dict = {"include_drafts": True, "include_private": True}
    query = search.query_for(model.Package)
    result = query.run({"fq": "+state:*"}, permission_labels=["draft"])
    assert result["count"] == 1
    result = query.run({"fq": "+state:*"}, permission_labels=["review"])
    assert result["count"] == 0
    result = query.run({"fq": "+state:*"}, permission_labels=["published"])
    assert result["count"] == 0
    result = tk.get_action("package_search")(context, search_dict)
    assert result["count"] == 1

    helpers.call_action("workflow_state_change", id=dataset["id"], review=True)
    search_dict = {"include_drafts": True, "include_private": True}
    query = search.query_for(model.Package)
    result = query.run({"fq": "+state:*"}, permission_labels=["draft"])
    assert result["count"] == 0
    result = query.run({"fq": "+state:*"}, permission_labels=["review"])
    assert result["count"] == 1
    result = query.run({"fq": "+state:*"}, permission_labels=["published"])
    assert result["count"] == 0
    result = tk.get_action("package_search")(context, search_dict)
    assert result["count"] == 1

    helpers.call_action(
        "workflow_state_change", id=dataset["id"], publish=True
    )
    search_dict = {"include_drafts": True, "include_private": True}
    query = search.query_for(model.Package)
    result = query.run({"fq": "+state:*"}, permission_labels=["draft"])
    assert result["count"] == 0
    result = query.run({"fq": "+state:*"}, permission_labels=["review"])
    assert result["count"] == 0
    result = query.run({"fq": "+state:*"}, permission_labels=["published"])
    assert result["count"] == 1
    result = tk.get_action("package_search")(context, search_dict)
    assert result["count"] == 1

    result = tk.get_action("package_search")(None, search_dict)
    assert result["count"] == 0
