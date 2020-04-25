# -*- coding: utf-8 -*-

import enum


class StateWeight(enum.IntEnum):
    fallback = 0
    default = 10
    handler = 30
    override = 50
