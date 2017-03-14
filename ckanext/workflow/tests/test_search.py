import ckan.tests.factories as factories
import ckan.tests.helpers as th
import nose.tools as nt

import ckan.lib.search as search
import ckan.lib.helpers as ch

from ckan.tests.legacy.pylons_controller import PylonsTestCase


class TestSearch(PylonsTestCase):
    def setup(self):
        th.reset_db()
        search.clear_all()
        user = factories.User()
        other_user = factories.User()
        simple_user = factories.User()
        org = factories.Organization(users=[
            {'name': user['name'], 'capacity': 'editor'},
            {'name': other_user['name'], 'capacity': 'editor'}
        ])
        self.user = user
        self.other_user = other_user
        self.simple_user = simple_user
        self.org = org

        pkg = factories.Dataset(user=user, owner_org=org['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        nt.assert_equal(data['workflow_stage'], 'published')
        pkg = factories.Dataset(user=user, owner_org=org['id'])
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        nt.assert_equal(data['workflow_stage'], 'pending')
        pkg = factories.Dataset(user=user, owner_org=org['id'])
        nt.assert_equal(pkg['workflow_stage'], 'unpublished')

    def test_simple_search_shows_only_published(self):
        result = th.call_action('package_search', q='*:*')
        nt.assert_equal(1, result['count'])
        result = th.call_action(
            'package_search', {'user': str(self.user['name'])},
            q='*:*')

        nt.assert_equal(1, result['count'])
        result = th.call_action(
            'package_search', {'user': str(self.other_user['name'])},
            q='*:*')
        nt.assert_equal(1, result['count'])

    def test_only_own_search_shows_all(self):
        app = th._get_test_app()
        url = ch.url_for(
            controller='api', action='action',
            logic_function='user_show', ver=3)
        result = app.get(
            url, {'id': self.user['id'], 'include_datasets': True},
            extra_environ={'REMOTE_USER': str(self.user['name'])}
        ).json['result']

        nt.assert_equal(3, len(result['datasets']))

        result = app.get(
            url, {'id': self.user['id'], 'include_datasets': True},
            extra_environ={'REMOTE_USER': str(self.other_user['name'])}
        ).json['result']

        nt.assert_equal(1, len(result['datasets']))

    def test_only_group_members_see_all_datasets_in_organization(self):
        app = th._get_test_app()
        url = ch.url_for(
            controller='api', action='action',
            logic_function='package_search', ver=3)
        result = app.get(
            url, {'q': 'owner_org:{0}'.format(self.org['id'])},
            extra_environ={'REMOTE_USER': str(self.user['name'])}
        ).json['result']
        nt.assert_equal(3, result['count'])

        result = app.get(
            url, {'q': 'owner_org:{0}'.format(self.org['id'])},
            extra_environ={'REMOTE_USER': str(self.other_user['name'])}
        ).json['result']
        nt.assert_equal(3, result['count'])

        result = app.get(
            url, {'q': 'owner_org:{0}'.format(self.org['id'])},
            extra_environ={'REMOTE_USER': str(self.simple_user['name'])}
        ).json['result']
        nt.assert_equal(1, result['count'])
