from builtins import str
from builtins import object
import nose.tools as nt
import ckan.tests.helpers as th
import ckan.tests.factories as factories
import ckan.plugins.toolkit as tk
import ckan.model as model


def _context(user, **kwargs):
    return dict(
        user=str(user['name']),
        model=model,
        **kwargs
    )


class TestAuth(object):
    def setup(self):
        th.reset_db()

    def test_author_can_make_pending(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)

        th.call_auth('move_to_next_stage', _context(user), **pkg)

    def test_author_cannot_make_published(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth,
            'move_to_next_stage',
            _context(user),
            **pkg
        )

    def test_author_cannot_reject(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth,
            'move_to_previous_stage',
            _context(user),
            **pkg
        )

    def test_author_cannot_unpublish(self):
        user = factories.User()
        site_admin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        data = th.call_action(
            'move_to_next_stage', _context(site_admin), id=pkg['id'])
        pkg.update(data)
        nt.assert_raises(
            tk.NotAuthorized,
            th.call_auth,
            'move_to_previous_stage',
            _context(user),
            **pkg
        )

    def test_admin_can_unpublish(self):
        user = factories.User()
        site_admin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        data = th.call_action(
            'move_to_next_stage', _context(site_admin), id=pkg['id'])
        pkg.update(data)
        th.call_auth(
            'move_to_previous_stage', _context(site_admin), **pkg)

    def test_site_admin_can_approve(self):
        user = factories.User()
        site_admin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        th.call_auth('move_to_next_stage', _context(site_admin), **pkg)

    def test_site_admin_can_reject(self):
        user = factories.User()
        site_admin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        th.call_auth(
            'move_to_previous_stage', _context(site_admin), **pkg)

    def test_revision_available_only_in_published_stage(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)

        nt.assert_raises(
            tk.NotAuthorized, th.call_auth,
            'create_dataset_revision', _context(user), **pkg
        )

        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        nt.assert_raises(
            tk.NotAuthorized, th.call_auth,
            'create_dataset_revision', _context(user), **pkg

        )

        data = th.call_action('move_to_next_stage', id=pkg['id'])
        pkg.update(data)
        th.call_auth('create_dataset_revision', _context(user), **pkg)

    def test_revision_cannot_be_created_from_revision(self):
        user = factories.User()
        pkg = factories.Dataset()
        th.call_action('move_to_next_stage', id=pkg['id'])
        th.call_action('move_to_next_stage', id=pkg['id'])

        revision = th.call_action(
            'create_dataset_revision', _context(user), id=pkg['id'])
        nt.assert_not_equal(pkg['id'], revision['id'])
        th.call_action('move_to_next_stage', id=revision['id'])

        data = th.call_action('move_to_next_stage', id=revision['id'])
        revision.update(data)

        nt.assert_raises(
            tk.NotAuthorized, th.call_auth,
            'create_dataset_revision', _context(user), **revision
        )

    def test_pending_dataset_can_be_rescind(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)
        nt.assert_raises(
            tk.NotAuthorized, th.call_auth,
            'workflow_rescind_dataset', _context(user), **pkg
        )

        data = th.call_action('move_to_next_stage', id=pkg['id'])
        pkg.update(data)
        th.call_auth('workflow_rescind_dataset', _context(user), **pkg)

        data = th.call_action('move_to_next_stage', id=pkg['id'])
        pkg.update(data)
        nt.assert_raises(
            tk.NotAuthorized, th.call_auth,
            'workflow_rescind_dataset', _context(user), **pkg
        )
