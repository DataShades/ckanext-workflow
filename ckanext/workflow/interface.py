import abc

import ckantoolkit as tk

import ckan.plugins.interfaces as interfaces


class State(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, ctx):
        self._ctx = ctx

    @property
    def ctx(self):
        return self._ctx

    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractmethod
    def next(self, **kwargs):
        pass

    @abc.abstractmethod
    def prev(self, **kwargs):
        pass

    def get_dataset_labels(self):
        pass

    def fix_ctx(self):
        pass

    def save(self, context):
        """Persist all changes to current context.
        """
        tk.get_action('package_patch')(
            context, self.ctx)

    def with_weight(self, weight):
        """
        >>> class CustomState(State): name = next = prev = 'custom'
        >>> CustomState({}).with_weight(10)[0]
        10
        >>> CustomState({}).with_weight(10)[1].name
        'custom'
        """
        return (weight, self)


class IWorkflow(interfaces.Interface):
    def get_state_for_package(self, pkg_dict):
        pass
