# -*- coding: utf-8 -*-


from ckanext.workflow.interface import State


class PrivateState(State):

    name = 'private'

    def prev(self, **kwargs):
        pass

    def next(self, **kwargs):
        self.ctx['private'] = False


class PublicState(State):

    name = 'public'

    def prev(self, **kwargs):
        self.ctx['private'] = True

    def next(self, **kwargs):
        pass
