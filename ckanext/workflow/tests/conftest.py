from __future__ import annotations

import pytest

from ckan import model

import ckanext.workflow.model as wf_model


@pytest.fixture(autouse=True)
def workflow_config(ckan_config):
    # Add workflow to the list of loaded plugins
    plugins = ckan_config.get("ckan.plugins", "")
    if "workflow" not in plugins:
        ckan_config["ckan.plugins"] = f"{plugins} workflow"
    return ckan_config


@pytest.fixture(autouse=True)
def setup_workflow_tables(clean_db):
    # Ensure all tables for our extension are created in the clean database
    wf_model.BaseModel.metadata.create_all(bind=model.meta.engine)
