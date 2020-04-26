
.. image:: https://travis-ci.org/DataShades/ckanext-workflow.svg?branch=master
    :target: https://travis-ci.org/DataShades/ckanext-workflow

.. image:: https://codecov.io/gh/DataShades/ckanext-workflow/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/DataShades/ckanext-workflow

================
ckanext-workflow
================

.. Put a description of your extension here:
   What does it do? What features does it have?
   Consider including some screenshots or embedding a video!


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
