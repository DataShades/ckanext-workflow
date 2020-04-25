# -*- coding: utf-8 -*-


from ckanext.workflow.interface import State


class PrivateState(State):

    name = 'private'

    def prev(self, **kwargs):
        return self

    def next(self, **kwargs):
        self.ctx['private'] = False
        return PublicState(self.ctx)


class PublicState(State):

    name = 'public'

    def prev(self, **kwargs):
        self.ctx['private'] = True
        return PrivateState(self.ctx)

    def next(self, **kwargs):
        return self
