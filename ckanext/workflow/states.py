# -*- coding: utf-8 -*-


from ckanext.workflow.interface import State


class PrivateState(State):

    name = 'private'

    def prev(self, **kwargs):
        return self

    def next(self, **kwargs):
        self.ctx['private'] = False
        return PublicState(self.ctx)

    def fix_ctx(self):
        self.ctx['private'] = True


class PublicState(State):

    name = 'public'

    def prev(self, **kwargs):
        self.ctx['private'] = True
        return PrivateState(self.ctx)

    def next(self, **kwargs):
        return self

    def fix_ctx(self):
        self.ctx['private'] = False
