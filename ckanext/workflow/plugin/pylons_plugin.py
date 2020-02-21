# -*- coding: utf-8 -*-

import ckan.plugins as p


class MixinPlugin(p.SingletonPlugin):
    p.implements(p.IRoutes, inherit=True)

        # IRoutes

    def before_map(self, map):
        ctrl = 'ckanext.workflow.controller:WorkflowController'

        map.connect('workflow.workflow_approve',
                    '/workflow/dataset/{id}/approve',
                    controller=ctrl,
                    action='approve')
        map.connect('workflow.workflow_reject',
                    '/workflow/dataset/{id}/reject',
                    controller=ctrl,
                    action='reject')
        map.connect('workflow.workflow_rescind',
                    '/workflow/dataset/{id}/rescind',
                    controller=ctrl,
                    action='rescind')
        map.connect('workflow.workflow_pending_list',
                    '/workflow/approvals',
                    controller=ctrl,
                    action='pending_list')
        map.connect('workflow.merge_dataset_revision',
                    '/workflow/dataset/{id}/merge_revision',
                    controller=ctrl,
                    action='merge_revision')
        map.connect('workflow.create_dataset_revision',
                    '/workflow/dataset/{id}/create_revision',
                    controller=ctrl,
                    action='create_revision')
        map.connect('workflow.purge_unpublished_dataset',
                    '/workflow/dataset/{id}/purge',
                    controller=ctrl,
                    action='purge')

        return map
