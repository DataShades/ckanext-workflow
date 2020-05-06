import abc

import ckantoolkit as tk

import ckan.plugins.interfaces as interfaces


class State(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, ctx):
        self._ctx = ctx

    @property
    def ctx(self):
        """Related package dict.
        """
        return self._ctx

    @abc.abstractproperty
    def name(self):
        """Machine readable name of state.
        """
        pass

    @abc.abstractmethod
    def next(self, **kwargs):
        """Transform ctx and return following state for updated ctx.
        """
        return self

    @abc.abstractmethod
    def prev(self, **kwargs):
        """Transform ctx and return previous state for updated ctx.
        """
        return self

    def get_dataset_permission_labels(self, labels):
        return labels

    def fix_ctx(self):
        pass

    def save(self, context):
        """Persist all changes to current context.
        """
        tk.get_action('package_patch')(
            context, self.ctx)

    def with_weight(self, weight):
        return (weight, self)


class IWorkflow(interfaces.Interface):
    def get_state_for_package(self, pkg_dict):
        return (0, None)

    def get_user_permission_labels(self, user_obj, labels):
        return labels
