import ckanext.workflow.interface as interface


class DraftState(interface.State):
    name = 'draft'

    def next(self):
        self.ctx['state'] = 'active'
        self.ctx['private'] = True

    def prev(self):
        pass


class ReviewState(interface.State):
    name = 'review'

    def next(self):
        self.ctx['private'] = False

    def prev(self):
        self.ctx['state'] = 'draft'


class PublishedState(interface.State):
    name = 'published'

    def next(self):
        pass

    def prev(self):
        self.ctx['private'] = True


class OverridenDraftState(interface.State):
    name = 'overriden-draft'

    def next(self):
        self.ctx['state'] = 'active'
        self.ctx['private'] = True

    def prev(self):
        pass


class OverridenReviewState(interface.State):
    name = 'overriden-review'

    def next(self):
        self.ctx['private'] = False

    def prev(self):
        self.ctx['state'] = 'draft'
