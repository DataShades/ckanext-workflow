import mock
import ckan.model as model
import ckan.plugins.toolkit as tk
import ckan.tests.helpers as th
import nose.tools as nt
import ckan.tests.factories as factories
from ckan.tests.legacy.pylons_controller import PylonsTestCase


class TestRevision(PylonsTestCase):

    def setup(self):
        th.reset_db()

    def test_revision_is_the_same_as_original(self):
        pkg = factories.Dataset()
        revision = th.call_action('create_dataset_revision', id=pkg['id'])
        nt.assert_equal(pkg['id'], revision['original_id_of_revision'])
        nt.assert_not_equal(pkg['id'], revision['id'])

    def test_revision_in_unpublished_state(self):
        pkg = factories.Dataset()
        th.call_action('move_to_next_stage', id=pkg['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])
        revision = th.call_action('create_dataset_revision', id=pkg['id'])
        nt.assert_equal(revision['workflow_stage'], 'unpublished')

    def test_revision_merge_purges_revision(self):
        pkg = factories.Dataset()
        revision = th.call_action('create_dataset_revision', id=pkg['id'])
        th.call_action('merge_dataset_revision', id=revision['id'])

        nt.assert_raises(
            tk.ObjectNotFound,
            th.call_action,
            'package_show',
            id=revision['id']
        )

    def test_revision_merge_updates_original(self):
        pkg = factories.Dataset()
        revision = th.call_action('move_to_next_stage', id=pkg['id'])
        revision = th.call_action('move_to_next_stage', id=pkg['id'])

        revision = th.call_action('create_dataset_revision', id=pkg['id'])
        new_data = dict(
            title='Updated title',
            notes='xxx...'
        )
        new_data['id'] = revision['id']
        th.call_action('package_patch', **new_data)

        updated = th.call_action('merge_dataset_revision', id=revision['id'])
        nt.assert_equal(updated['title'], new_data['title'])
        nt.assert_equal(updated['notes'], new_data['notes'])
        nt.assert_equal(updated['workflow_stage'], 'published')
        nt.assert_not_equal(updated['id'], new_data['id'])

    @th.change_config('workflow.site_admin.email', 'example@example.com')
    def test_move_to_pending_stage_email(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)
        revision = th.call_action('create_dataset_revision', id=pkg['id'])
        with mock.patch('ckan.lib.mailer.mail_recipient') as mock_mail:
            th.call_action(
                'move_to_next_stage',
                {'user': user['name']}, id=revision['id'])
            nt.assert_true(mock_mail.called)
            args = mock_mail.call_args[0]
            text = args[3]
            nt.assert_in(pkg['title'], text)
            nt.assert_in('new revision', text)
            nt.assert_in(user['name'], text)

    def test_only_org_member_can_create_revision(self):
        user = factories.User()
        simple_user = factories.User()
        org = factories.Organization(users=[
            {'name': user['name'], 'capacity': 'editor'}
        ])
        self.user = user
        self.simple_user = simple_user
        self.org = org

        pkg = factories.Dataset(owner_org=org['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        pkg.update(data)

        th.call_auth('create_dataset_revision',
                     {'model': model, 'user': user['name']}, **pkg)
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth, 'create_dataset_revision',
            {'model': model, 'user': simple_user['name']}, **pkg
        )

    def test_only_org_member_can_view_revision(self):
        user = factories.User()
        simple_user = factories.User()
        org = factories.Organization(users=[
            {'name': user['name'], 'capacity': 'editor'}
        ])
        self.user = user
        self.simple_user = simple_user
        self.org = org

        pkg = factories.Dataset(owner_org=org['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])
        data = th.call_action('move_to_next_stage', id=pkg['id'])
        pkg.update(data)
        revision = th.call_action(
            'create_dataset_revision',
            {'user': user['name']},
            id=pkg['id'])

        th.call_auth(
            'read_dataset_revision',
            {'model': model, 'user': user['name']},
            **revision
        )
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth, 'read_dataset_revision',
            {'model': model, 'user': simple_user['name']},
            **revision
        )
        th.call_action('move_to_next_stage', id=revision['id'])

        th.call_auth(
            'read_dataset_revision',
            {'model': model, 'user': user['name']},
            **revision
        )
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth, 'read_dataset_revision',
            {'model': model, 'user': simple_user['name']},
            **revision
        )

    @th.change_config('workflow.site_admin.email', 'example@example.com')
    def test_move_to_rejected_stage_email(self):
        user = factories.User()
        sysadmin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        reason = 'Test reason'
        revision = th.call_action(
            'create_dataset_revision', {'user': user['name']}, id=pkg['id'])

        with mock.patch('ckan.lib.mailer.mail_recipient') as mock_mail:
            th.call_action(
                'move_to_next_stage',
                {'user': user['name']}, id=revision['id'])
            th.call_action(
                'move_to_previous_stage',
                {'user': sysadmin['name']}, id=revision['id'], reason=reason)
            nt.assert_true(mock_mail.called)
            args = mock_mail.call_args[0]
            subject = args[2]
            nt.assert_in('rejection', subject)
            text = args[3]
            nt.assert_in('revision', text)
            nt.assert_in(revision['title'], text)
            nt.assert_in(revision['id'], text)
            nt.assert_in(sysadmin['name'], text)
            nt.assert_in(reason, text)

    @th.change_config('workflow.site_admin.email', 'example@example.com')
    def test_move_to_published_stage_email(self):
        user = factories.User()
        sysadmin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)

        revision = th.call_action(
            'create_dataset_revision', {'user': user['name']}, id=pkg['id'])
        with mock.patch('ckan.lib.mailer.mail_recipient') as mock_mail:
            th.call_action(
                'move_to_next_stage',
                {'user': user['name']}, id=revision['id'])
            th.call_action(
                'move_to_next_stage',
                {'user': sysadmin['name']}, id=revision['id'])
            nt.assert_true(mock_mail.called)
            args = mock_mail.call_args[0]
            subject = args[2]
            nt.assert_in('approval', subject)
            text = args[3]
            nt.assert_in(revision['title'], text)
            nt.assert_in('revision', text)

            nt.assert_in(pkg['id'], text)
            nt.assert_in(sysadmin['name'], text)

    def test_revision_can_be_purged_by_org_editor(self):
        user = factories.User()
        other_user = factories.User()
        simple_user = factories.User()
        org = factories.Organization(users=[
            {'name': user['name'], 'capacity': 'editor'},
            {'name': other_user['name'], 'capacity': 'editor'}
        ])
        self.user = user
        self.simple_user = simple_user
        self.org = org

        pkg = factories.Dataset(owner_org=org['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])

        revision = th.call_action(
            'create_dataset_revision',
            {'user': user['name']},
            id=pkg['id'])

        th.call_auth('purge_unpublished_dataset',
                     {'model': model, 'user': user['name']}, **revision)
        th.call_auth('purge_unpublished_dataset',
                     {'model': model, 'user': other_user['name']}, **revision)
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth, 'purge_unpublished_dataset',
            {'model': model, 'user': simple_user['name']}, **revision)
