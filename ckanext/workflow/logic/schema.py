from __future__ import annotations

import ckan.plugins.toolkit as tk
from ckan import types


@tk.validator_args
def workflow_definition_create(
    not_empty: types.Validator,
    unicode_safe: types.Validator,
    boolean_validator: types.Validator,
    ignore_missing: types.Validator,
    default: types.ValidatorFactory,
) -> types.Schema:
    return {
        "name": [not_empty, unicode_safe],
        "description": [ignore_missing, unicode_safe],
        "enabled": [default(True), boolean_validator],
        "trigger_type": [default("dataset_create"), unicode_safe],
        "dataset_type": [default("all"), unicode_safe],
        "steps": workflow_step(),
    }


@tk.validator_args
def workflow_step(
    not_empty: types.Validator,
    unicode_safe: types.Validator,
    ignore_empty: types.Validator,
    convert_to_json_if_string: types.Validator,
    default: types.ValidatorFactory,
) -> types.Schema:
    return {
        "name": [not_empty, unicode_safe],
        "assigned_role": [not_empty, unicode_safe],
        "step_type": [not_empty, unicode_safe],
        "instructions": [ignore_empty, unicode_safe],
        "post_actions": [default("{}"), convert_to_json_if_string],
    }


@tk.validator_args
def workflow_definition_update(  # noqa: PLR0913
    not_empty: types.Validator,
    unicode_safe: types.Validator,
    boolean_validator: types.Validator,
    ignore_missing: types.Validator,
    default: types.ValidatorFactory,
    int_validator: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, int_validator],
        "name": [not_empty, unicode_safe],
        "description": [ignore_missing, unicode_safe],
        "enabled": [default(True), boolean_validator],
        "trigger_type": [default("dataset_create"), unicode_safe],
        "dataset_type": [default("all"), unicode_safe],
        "steps": workflow_step(),
    }


@tk.validator_args
def workflow_definition_show(
    not_empty: types.Validator,
    int_validator: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, int_validator],
    }


@tk.validator_args
def workflow_definition_delete(
    not_empty: types.Validator,
    int_validator: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, int_validator],
    }


@tk.validator_args
def workflow_task_complete(
    not_empty: types.Validator,
    unicode_safe: types.Validator,
    int_validator: types.Validator,
    ignore_missing: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, unicode_safe],
        "sequence": [not_empty, int_validator],
        "action_type": [not_empty, unicode_safe],
        "comment": [ignore_missing, unicode_safe],
    }


@tk.validator_args
def workflow_instance_cancel(
    not_empty: types.Validator,
    unicode_safe: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, unicode_safe],
    }


@tk.validator_args
def workflow_instance_show(
    not_empty: types.Validator,
    unicode_safe: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, unicode_safe],
    }
