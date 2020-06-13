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

    @classmethod
    def name(cls):
        """Machine readable name of state.
        """
        return cls.__name__

    @abc.abstractmethod
    def change(self, data_dict):
        """Transform ctx and return updated state for the new ctx.
        """
        return self

    def get_dataset_permission_labels(self, existing_labels):
        """Append/remove permission labels depending on current state.
        """
        return existing_labels

    def fix_ctx(self):
        """Change ctx making it suitable for the current state.
        """
        pass

    def save(self, context):
        """Persist all changes to current context.
        """
        tk.get_action("package_patch")(context, self.ctx)

    def with_weight(self, weight):
        return (weight, self)


class IWorkflow(interfaces.Interface):
    def get_state_for_package(self, pkg_dict):
        """Return possible state for package.

        Returned value is a tuple, containing weight(probability that
        state is correct) and state itself. From all the states
        returned by different implementations of IWorkflow, the one
        with highest weight wins. Use `ckanext.workflow.utils.Weight`
        enum options as weight values.

        :rtype: Tuple(workflow.utils.Weight, State|None)

        """
        return (0, None)

    def get_user_permission_labels(self, user_obj, labels):
        """Update user's permission labels.

        Every state has `get_dataset_permission_labels` method, that
        can add extra labels to dataset in particualr state. Depending
        on extra labels, add appropriate labels to user as
        well. General logic - user will see dataset only if he has at
        least one label that matches dataset's labels.

        :rtype: list

        """
        return labels
