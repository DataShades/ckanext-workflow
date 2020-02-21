
import click
import ckan.model as model
from ckanext.workflow.helpers import (
    _workflow_stage_field,
    _workflow_type_field
)

wf_field = _workflow_type_field()
stage_field = _workflow_stage_field()
WORKFLOW = 'base'
PUBLISHED = 'published'
UNPUBLISHED = 'unpublished'


@click.group()
def workflow():
    """Workflow management commands.
    """
    pass


@workflow.command()
@click.argument('id', required=False)
def migrate(id):
    if not id:
        _migrate_all()
    else:
        _migrate_one(id)
    click.secho("Migrate: success", fg='green')


def _migrate_one(id):
    pkg = model.Package.get(id)
    if pkg is None:
        click.secho(f'Package {id} not found', fg='red')
        return False
    wf = pkg.extras.get(wf_field)
    stage = pkg.extras.get(stage_field)
    if None not in (wf, stage):
        click.secho(f'Package {id} currently in state({wf}, {stage})')
        return False
    else:
        extras = pkg.extras
        extras.update({wf_field: WORKFLOW})
        if pkg.state == model.State.ACTIVE and not pkg.private:
            extras.update({stage_field: PUBLISHED})
            click.secho(f'{id} publish', fg='green')
        else:
            extras.update({stage_field: UNPUBLISHED})
            click.secho(f'{id} publish', fg='red')
        pkg.extras = extras

        model.Session.commit()


def _migrate_all():
    for pkg in model.Session.query(model.Package.id):
        _migrate_one(pkg.id)


def get_commands():
    return [workflow]