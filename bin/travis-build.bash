#!/bin/bash
set -e

echo "This is travis-build.bash..."

echo "Installing the packages that CKAN requires..."
sudo apt-get update -qq
sudo apt-get install postgresql-$PGVERSION solr-jetty libcommons-fileupload-java:amd64=1.2.2-1
echo "NO_START=0\nJETTY_HOST=127.0.0.1\nJETTY_PORT=8983\nJAVA_HOME=$JAVA_HOME" | sudo tee /etc/default/jetty


echo "Installing CKAN and its Python dependencies..."
git clone https://github.com/ckan/ckan
cd ckan
export latest_ckan_release_branch=`git branch --all | grep remotes/origin/release-v | sort -r | sed 's/remotes\/origin\///g' | head -n 1`
echo "CKAN branch: $latest_ckan_release_branch"
git checkout $latest_ckan_release_branch
python setup.py develop
pip install -r requirements.txt
pip install -r dev-requirements.txt
cd -
sudo cp ckan/ckan/config/solr/schema.xml /etc/solr/conf/schema.xml
sudo service jetty restart

git clone https://github.com/ckan/ckanext-scheming
cd ckanext-scheming
python setup.py develop
pip install ckanapi
pip install ckantoolkit
pip install pytz
additional_fields='{"field_name": "workflow_type", "label": "Workflow type", "form_snippet": null, "validators": "workflow_type_validator"}, {"field_name": "workflow_stage", "label": "Workflow state", "form_snippet": null, "validators": "workflow_stage_validator"},'
sed -i -e "s/dataset_fields\":.*/\0 $additional_fields/"  ckanext/scheming/ckan_dataset.json
cd -


echo "Creating the PostgreSQL user and database..."
sudo -u postgres psql -c "CREATE USER ckan_default WITH PASSWORD 'pass';"
sudo -u postgres psql -c 'CREATE DATABASE ckan_test WITH OWNER ckan_default;'

echo "Initialising the database..."
cd ckan
paster db init -c test-core.ini
cd -

echo "Installing ckanext-workflow and its requirements..."
python setup.py develop
pip install -r dev-requirements.txt

echo "Moving test.ini into a subdir..."
mkdir subdir
mv test.ini subdir

echo "travis-build.bash is done."
