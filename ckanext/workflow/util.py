# -*- coding: utf-8 -*-
import logging
from collections import namedtuple
import ckan.plugins as plugins

from ckanext.workflow.interfaces import IWorkflow

log = logging.getLogger(__name__)
Roles = namedtuple('Roles', 'creator,site_admin,editor')
roles = Roles('creator', 'site_admin', 'editor')


class WorkflowStage:
    """Representation of workflow step.
    """
    @classmethod
    def linearize_stages(cls, *stages):
        def linearizer(prev, next):
            prev.set_next([next])
            next.set_prev([prev])
            return next

        reduce(linearizer, stages)

    def __init__(self,
                 stage_name,
                 approval_msg=None,
                 reject_msg=None,
                 label=None,
                 approval_effect=None,
                 rejection_effect=None):
        self._next = []
        self._previous = []
        self._approver_roles = [roles.site_admin]
        self._rejecter_roles = [roles.site_admin]

        self.approval_effect = approval_effect
        self.rejection_effect = rejection_effect

        self.stage_name = stage_name
        self.approval_msg = approval_msg
        self.reject_msg = reject_msg
        if label is None:
            label = stage_name.capitalize()
        self.label = label

    def __str__(self):
        return self.stage_name

    def __json__(self):
        return str(self)

    def prev(self, route=0):
        try:
            return self._previous[route]
        except IndexError:
            return None

    def reject(self):
        return self.prev(0)

    def next(self, route=0):
        try:
            return self._next[route]
        except IndexError:
            return None

    def approve(self):
        return self.next(0)

    def set_prev(self, prev):
        self._previous = prev

    def set_next(self, next):
        self._next = next

    @property
    def who_can_approve(self):
        return self._approver_roles

    @who_can_approve.setter
    def who_can_approve(self, value):
        self._approver_roles = value

    @property
    def who_can_reject(self):
        return self._rejecter_roles

    @who_can_reject.setter
    def who_can_reject(self, value):
        self._rejecter_roles = value


class Workflow:

    _registry = {}
    start = None
    finish = None
    stages = {}

    @classmethod
    def get_workflow(cls, type):
        return cls._registry[type]

    @classmethod
    def configure(cls):
        for plugin in plugins.PluginImplementations(IWorkflow):
            cls._registry.update(plugin.register_workflows())

    @classmethod
    def get_all_stages(cls):
        stages = []
        for wf in cls._registry.values():
            stages.extend(wf.stages.keys())
        return stages

    @classmethod
    def get_all_finish_stages(cls):
        return [str(wf.finish) for wf in cls._registry.values()]

    def __init__(self):
        self.start = self.finish = None
        self.stages = {}

    def get_stage(self, stage_name):
        return self.stages[stage_name]


class BaseWorkflow(Workflow):
    def __init__(self):
        first = WorkflowStage('unpublished', 'Submit for approval')
        second = WorkflowStage('pending', 'Approve', 'Reject')
        third = WorkflowStage('published', reject_msg='Unpublish')
        WorkflowStage.linearize_stages(first, second, third)
        # unpublishing should make dataset unpublished, not pending
        third.set_prev([first])
        first.who_can_approve = [roles.creator]

        self.start = first
        self.finish = third

        self.stages = {
            str(first): first,
            str(second): second,
            str(third): third
        }
