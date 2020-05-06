import ckan.plugins as p

import ckanext.workflow.interface as interface
import ckanext.workflow.utils as utils
import ckanext.workflow.tests.states as states


class TestWorkflowPlugin(p.SingletonPlugin):
    p.implements(interface.IWorkflow)

    def get_state_for_package(self, pkg_dict):
        if pkg_dict['state'] == 'draft':
            State = states.DraftState
        elif pkg_dict['private']:
            State = states.ReviewState
        else:
            State = states.PublishedState
        return State(pkg_dict).with_weight(utils.Weight.handler)

    def get_user_permission_labels(self, user_obj, labels):
        if user_obj:
            labels.extend(['draft', 'review', 'published'])
        return labels


class TestWorkflowOverridePlugin(p.SingletonPlugin):
    p.implements(interface.IWorkflow, inherit=True)

    def get_state_for_package(self, pkg_dict):
        if pkg_dict['state'] == 'draft':
            return states.OverridenDraftState(pkg_dict).with_weight(utils.Weight.default)
        elif pkg_dict['private']:
            return states.OverridenReviewState(pkg_dict).with_weight(utils.Weight.override)
        return (0, None)
