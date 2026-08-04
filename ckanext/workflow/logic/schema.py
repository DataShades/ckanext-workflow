from __future__ import annotations

import re

import ckan.plugins.toolkit as tk
from ckan import types


def duration_string_to_seconds(s: str) -> int:
    s = s.strip().lower()
    if not s:
        return 0
    pattern = re.compile(r"(\d+)\s*(days?|d|hours?|h|minutes?|min|m|seconds?|sec|s)")
    matches = pattern.findall(s)
    if not matches:
        raise ValueError("Invalid duration format. Use e.g. '1d 4h', '2 days', '1 minute'")
    seconds = 0
    for val_str, unit in matches:
        val = int(val_str)
        if unit.startswith("d"):
            seconds += val * 86400
        elif unit.startswith("h"):
            seconds += val * 3600
        elif unit.startswith("m"):
            seconds += val * 60
        elif unit.startswith("s"):
            seconds += val
    return seconds


def parse_duration_to_seconds(key, data, errors, context):
    value = data.get(key)
    if not value:
        data[key] = 0
        return
    if isinstance(value, int):
        return
    if isinstance(value, str):
        val = value.strip()
        if not val:
            data[key] = 0
            return
        if val.isdigit():
            data[key] = int(val)
            return
        try:
            data[key] = duration_string_to_seconds(val)
        except ValueError as e:
            errors[key].append(str(e))
            return
    else:
        errors[key].append("Invalid duration format")


def clean_trigger_type(key, data, errors, context):
    value = data.get(key)
    if not value:
        data[key] = "create"
        return
    if isinstance(value, list):
        data[key] = ",".join(value)
        return
    if isinstance(value, str):
        return
    errors[key].append("Invalid trigger type")


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
        "enabled": [boolean_validator],
        "trigger_type": [clean_trigger_type, unicode_safe],
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
    ignore_missing: types.Validator,
) -> types.Schema:
    return {
        "name": [not_empty, unicode_safe],
        "assigned_role": [not_empty, unicode_safe],
        "step_type": [not_empty, unicode_safe],
        "instructions": [ignore_empty, unicode_safe],
        "timeout_duration": [ignore_missing, parse_duration_to_seconds],
        "config": [default("{}"), convert_to_json_if_string],
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
        "enabled": [boolean_validator],
        "trigger_type": [clean_trigger_type, unicode_safe],
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
def workflow_start(
    not_empty: types.Validator,
    unicode_safe: types.Validator,
) -> types.Schema:
    return {
        "id": [not_empty, unicode_safe],
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
