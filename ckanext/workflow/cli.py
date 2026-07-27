from __future__ import annotations

import click

__all__ = ["workflow"]


@click.group(short_help="Workflow management")
def workflow():
    """Workflow management commands."""
