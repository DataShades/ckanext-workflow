import ckanext.workflow.interface as interface


class DraftState(interface.State):
    name = 'draft'

    def get_dataset_permission_labels(self, labels):
        return ['draft']

    def next(self):
        self.ctx['state'] = 'active'
        self.ctx['private'] = True
        return ReviewState(self.ctx)

    def prev(self):
        pass


class ReviewState(interface.State):
    name = 'review'

    def get_dataset_permission_labels(self, labels):
        return ['review']

    def next(self):
        self.ctx['private'] = False
        return PublishedState(self.ctx)

    def prev(self):
        self.ctx['state'] = 'draft'
        return DraftState(self.ctx)


class PublishedState(interface.State):
    name = 'published'

    def get_dataset_permission_labels(self, labels):
        return ['published']

    def next(self):
        pass

    def prev(self):
        self.ctx['private'] = True
        return ReviewState(self.ctx)


class OverridenDraftState(interface.State):
    name = 'overriden-draft'

    def next(self):
        self.ctx['state'] = 'active'
        self.ctx['private'] = True
        return OverridenReviewState(self.ctx)

    def prev(self):
        pass


class OverridenReviewState(interface.State):
    name = 'overriden-review'

    def next(self):
        self.ctx['private'] = False
        return PublishedState(self.ctx)

    def prev(self):
        self.ctx['state'] = 'draft'
        return OverridenDraftState(self.ctx)
