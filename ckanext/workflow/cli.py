# -*- coding: utf-8 -*-

import click


def get_commands():
    return [workflow]


@click.group()
def workflow():
    pass
