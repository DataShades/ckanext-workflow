# -*- coding: utf-8 -*-

import os
import paste.script

import ckan.model as model
from ckan.lib.cli import CkanCommand


class WorkflowCommand(CkanCommand):
    """
    Usage::
    paster workflow [command]

    Commands::
    ...

    """

    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option(
        '-c',
        '--config',
        dest='config',
        default=os.getenv('CKAN_INI') or 'development.ini',
        help='Config file to use.'
    )

    def command(self):
        self._load_config()
        model.Session.commit()

        cmd_name = (self.args[0] if self.args else '').replace('-', '_')
        cmd = getattr(self, cmd_name, None)
        if cmd is None:
            return self.usage

        return cmd()
