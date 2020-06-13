# -*- coding: utf-8 -*-

import logging
from ckanext.workflow.interface import State

log = logging.getLogger(__name__)


class PrivateState(State):

    name = "private"

    def change(self, data_dict):
        if "private" in data_dict:
            private = data_dict["private"]
        else:
            log.warning("NativeWorkflow expects `private` key")
            if "private" not in self.ctx:
                self.fix_ctx()
            private = self.ctx["private"]

        if private:
            return self
        self.ctx["private"] = False
        return PublicState(self.ctx)

    def fix_ctx(self):
        self.ctx["private"] = True


class PublicState(State):

    name = "public"

    def change(self, data_dict):
        if "private" in data_dict:
            private = data_dict["private"]
        else:
            log.warning("NativeWorkflow expects `private` key")
            if "private" not in self.ctx:
                self.fix_ctx()
            private = self.ctx["private"]

        if not private:
            return self
        self.ctx["private"] = True
        return PublicState(self.ctx)

    def fix_ctx(self):
        self.ctx["private"] = False
