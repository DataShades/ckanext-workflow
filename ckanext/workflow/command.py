from ckan.lib.cli import CkanCommand
import paste.script
import logging
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

log = logging.getLogger('ckanext.workflow')


def migrate_one(id):
    pkg = model.Package.get(id)
    if pkg is None:
        print('Package {0} not found'.format(id))
        return False
    wf = pkg.extras.get(wf_field)
    stage = pkg.extras.get(stage_field)
    if None not in (wf, stage):
        print('Package {0} currently in state({1}, {2})'.format(
            id, wf, stage
        ))
        return False
    else:
        model.repo.new_revision()
        extras = pkg.extras
        extras.update({wf_field: WORKFLOW})
        if pkg.state == model.State.ACTIVE and not pkg.private:
            extras.update({stage_field: PUBLISHED})
            print('{0} publish'.format(id))
        else:
            extras.update({stage_field: UNPUBLISHED})
            print('{0} unpublish'.format(id))
        pkg.extras = extras

        model.Session.commit()


def migrate_all():
    for pkg in model.Session.query(model.Package.id):
        migrate_one(pkg.id)


class WorkflowCommand(CkanCommand):
    """
    Workflow management commands.

    Usage::
        paster workflow [command]
    """

    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option('-c', '--config', dest='config',
                      default='development.ini',
                      help='Config file to use.')

    def command(self):
        self._load_config()
        action = self.args[0]

        if not len(self.args):
            print self.usage
        elif action == 'migrate':
            try:
                id = self.args[1]
            except IndexError:
                id = None
            self._migrate(id)
        else:
            print('There are no such action: {0}'.format(action))

    def _migrate(self, id):
        if id is None:
            migrate_all()
        else:
            migrate_one(id)
