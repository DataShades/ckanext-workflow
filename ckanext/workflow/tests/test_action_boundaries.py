from unittest import mock

from ckanext.workflow import action


class BoundaryStage:
    approval_effect = None
    rejection_effect = None

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def approve(self):
        return None

    def reject(self):
        return None


def test_move_to_next_stage_is_idempotent_at_final_stage():
    stage = BoundaryStage("published")
    stage.approval_effect = mock.Mock()
    context = {"package": object()}

    with mock.patch.object(
        action,
        "_prepare_workflow_action",
        return_value=({}, stage, object()),
    ), mock.patch.object(
        action.workflow_helpers,
        "_workflow_stage_field",
        return_value="workflow_stage",
    ), mock.patch.object(action, "_update_workflow_stage") as update_stage:
        result = action.move_to_next_stage(context, {})

    assert result == {"workflow_stage": "published"}
    update_stage.assert_not_called()
    stage.approval_effect.assert_not_called()


def test_move_to_previous_stage_is_idempotent_at_initial_stage():
    stage = BoundaryStage("unpublished")
    stage.rejection_effect = mock.Mock()
    context = {"package": object()}

    with mock.patch.object(
        action,
        "_prepare_workflow_action",
        return_value=({}, stage, object()),
    ), mock.patch.object(
        action.workflow_helpers,
        "_workflow_stage_field",
        return_value="workflow_stage",
    ), mock.patch.object(action, "_update_workflow_stage") as update_stage:
        result = action.move_to_previous_stage(context, {})

    assert result == {"workflow_stage": "unpublished"}
    update_stage.assert_not_called()
    stage.rejection_effect.assert_not_called()
