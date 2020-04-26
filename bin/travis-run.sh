#!/bin/bash
set -e

pytest --ckan-ini=subdir/test.ini --cov=ckanext.workflow ckanext/workflow/tests
