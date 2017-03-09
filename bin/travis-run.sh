#!/bin/sh -e

nosetests --nologcapture --with-pylons=subdir/test.ini --with-coverage --cover-package=ckanext.workflow --cover-inclusive --cover-erase --cover-tests
