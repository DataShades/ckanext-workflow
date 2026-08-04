# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from ckan import model
import ckan.plugins.toolkit as tk
import ckanext.workflow.model as wf_model  # noqa: F401


@pytest.fixture(autouse=True)
def setup_workflow_tables(clean_db):
    # Ensure all tables for our extension are created in the clean database
    tk.BaseModel.metadata.create_all(bind=model.meta.engine)
