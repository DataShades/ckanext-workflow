
.. image:: https://travis-ci.org/DataShades/ckanext-workflow.svg?branch=master
    :target: https://travis-ci.org/DataShades/ckanext-workflow

.. image:: https://codecov.io/gh/DataShades/ckanext-workflow/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/DataShades/ckanext-workflow

.. image:: https://api.codeclimate.com/v1/badges/a6fef8087372d2f4f3c8/maintainability
   :target: https://codeclimate.com/github/DataShades/ckanext-workflow/maintainability
   :alt: Maintainability

================
ckanext-workflow
================

Add a bit of workflow into dataset management lifecycle.

This extension provides basically just a basis for creation of custom
workfrows. Using few abstractions, it simplifies switching between
different states and provides handles for common access management
tasks(for example, do not show dataset with particular state in search
results).


Using existing workflows
------------------------

In order to enable custom workflow, one need to enable plugin with
`IWorkflow` implementation. For example, `native_workflow` provided by
current extension enables management of original CKAN's state
(private/public) using `ckanext-workflow` toolset.

After adding extension with workflow implementation to the list of
enabled plugin, make a call to `workflow_state_change` API action,
passing id of updated package, alongside with any additional data
required for defining following state of the package. There is no any
mandatory key in provided data(except for id), so reffer to the docs
of particalar workflow, you are using.

If you need more low-level control, follow pattern bellow::

  # obtain current state of package
  state = toolkit.h.workflow_get_state(pkg_dict)

  # if there is no state, either you forgot to enable plugin,
  # implementing the forkflow, or none of plugins can handle current
  # package.
  if state is None:
      return

  # make all required changes in package and return new state, based
  # on provided `data_dict`
  new_state = state.change(data_dict)

  # Commit all che chages to the package
  new_state.save()


Create custom workflow
----------------------

.. TBD

Built-in workflows
------------------

Installation
------------

To install ckanext-workflow:

1. Activate your CKAN virtual environment, for example::

     . /usr/lib/ckan/default/bin/activate

2. Install the ckanext-workflow Python package into your virtual environment::

     pip install ckanext-workflow

3. Add ``workflow`` to the ``ckan.plugins`` setting in your CKAN
   config file (by default the config file is located at
   ``/etc/ckan/default/production.ini``).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu::

     sudo service apache2 reload


Development Installation
------------------------

To install ckanext-workflow for development, activate your CKAN virtualenv and
do::

    git clone https://github.com/DataShades/ckanext-workflow.git
    cd ckanext-workflow
    python setup.py develop
    pip install -r dev-requirements.txt

-----------------
Running the Tests
-----------------

To run the tests, do::

  pytest --ckan-ini test.ini
