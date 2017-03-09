import mock
import ckan.tests.factories as factories
import ckan.tests.helpers as th
import nose.tools as nt
import ckan.plugins.toolkit as tk
import ckan.lib.search as search
import ckan.lib.helpers as ch

from ckan.tests.legacy.pylons_controller import PylonsTestCase

class TestWorkflow:

    def setup(self):
        th.reset_db()

    def test_creation(self):
        pkg = th.call_action('package_create', name='test-package')
        nt.assert_equal(pkg['workflow_type'], 'base')
        nt.assert_equal(pkg['workflow_stage'], 'unpublished')

    def test_update(self):
        pkg = th.call_action('package_create', name='test-package')
        pkg = th.call_action('package_update', id=pkg['id'], name='test-kage2')
        nt.assert_equal(pkg['workflow_type'], 'base')
        nt.assert_equal(pkg['workflow_stage'], 'unpublished')
        nt.assert_equal(pkg['name'], 'test-kage2')

    def test_patch(self):
        pkg = th.call_action('package_create', name='test-package')
        pkg = th.call_action('package_patch', id=pkg['id'], name='test-kage2')
        nt.assert_equal(pkg['workflow_type'], 'base')
        nt.assert_equal(pkg['workflow_stage'], 'unpublished')
        nt.assert_equal(pkg['name'], 'test-kage2')

    def test_error_when_trying_to_deceive_workflow(self):
        th.call_action(
            'package_create', name='test-package1', workflow_type='base')

        nt.assert_raises(
            tk.ValidationError, th.call_action,
            'package_create', name='test-package21',
            workflow_stage='pending')
        nt.assert_raises(
            tk.ValidationError, th.call_action,
            'package_create', name='test-package31', workflow_type='base',
            workflow_stage='pending')
        nt.assert_raises(
            tk.ValidationError, th.call_action,
            'package_create', name='test-package22',
            workflow_stage='published')
        nt.assert_raises(
            tk.ValidationError, th.call_action,
            'package_create', name='test-package32', workflow_type='base',
            workflow_stage='published')

    def test_disabled_update_to_next_stage(self):
        pkg = th.call_action('package_create', name='test-package1')
        nt.assert_raises(
            tk.ValidationError, th.call_action,
            'package_patch', id=pkg['id'], workflow_stage='pending')

    def test_move_to_pending_stage(self):
        pkg = factories.Dataset()
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        nt.assert_equal(data['workflow_stage'], 'pending')

    @th.change_config('workflow.site_admin.email', 'example@example.com')
    def test_move_to_pending_stage_email(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)

        with mock.patch('ckan.lib.mailer.mail_recipient') as mock_mail:
            th.call_action(
                'move_to_next_stage',
                {'user': user['name']}, id=pkg['id'])
            nt.assert_true(mock_mail.called)
            args = mock_mail.call_args[0]
            text = args[3]
            nt.assert_in(pkg['title'], text)
            nt.assert_in(user['name'], text)

    @th.change_config('workflow.site_admin.email', 'example@example.com')
    def test_move_to_rejected_stage_email(self):
        user = factories.User()
        sysadmin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        reason = 'Test reason'

        with mock.patch('ckan.lib.mailer.mail_recipient') as mock_mail:
            th.call_action(
                'move_to_next_stage',
                {'user': user['name']}, id=pkg['id'])
            th.call_action(
                'move_to_previous_stage',
                {'user': sysadmin['name']}, id=pkg['id'], reason=reason)
            nt.assert_true(mock_mail.called)
            args = mock_mail.call_args[0]
            text = args[3]
            nt.assert_in(pkg['title'], text)
            nt.assert_in(sysadmin['name'], text)
            nt.assert_in(reason, text)

    @th.change_config('workflow.site_admin.email', 'example@example.com')
    def test_move_to_published_stage_email(self):
        user = factories.User()
        sysadmin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)

        with mock.patch('ckan.lib.mailer.mail_recipient') as mock_mail:
            th.call_action(
                'move_to_next_stage',
                {'user': user['name']}, id=pkg['id'])
            th.call_action(
                'move_to_next_stage',
                {'user': sysadmin['name']}, id=pkg['id'])
            nt.assert_true(mock_mail.called)
            args = mock_mail.call_args[0]
            text = args[3]
            nt.assert_in(pkg['title'], text)
            nt.assert_in(sysadmin['name'], text)

    def test_move_to_published_stage(self):
        pkg = factories.Dataset()
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        nt.assert_equal(data['workflow_stage'], 'published')

    def test_move_to_unpublished_stage_from_pending(self):
        pkg = factories.Dataset()
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_previous_stage', id=pkg['id'])
        nt.assert_equal(data['workflow_stage'], 'unpublished')

    def test_move_to_unpublished_stage_from_published(self):
        pkg = factories.Dataset()
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_previous_stage', id=pkg['id'])
        nt.assert_equal(data['workflow_stage'], 'unpublished')


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
