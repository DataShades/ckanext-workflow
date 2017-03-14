# -*- coding: utf-8 -*-
from ckan.plugins import Interface


class IWorkflow(Interface):
    """Implement custom workflows.

    Each newly created workflow must extends base class
    `ckanext.workflow.util.Workflow`. Set `start` property of
    workflow to the initial stage and finish to the last one.
    Each stage itself must be inherior of `WorkflowStage`.

    """

    def register_workflows(self):
        """Return dictonary with additional workflows.

        :returns: name/Workflow dictonary
        :rtype: dict

        """

        return dict()
