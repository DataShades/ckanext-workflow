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


class TestAuth:
    def setup(self):
        th.reset_db()

    def test_author_can_make_pending(self):
        user = factories.User()
        pkg = factories.Dataset(user=user)
        th.call_auth('move_to_next_stage', _context(user, package=pkg))

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
            _context(user, package=pkg)
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
            _context(user, package=pkg)
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
            _context(user, package=pkg)
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
            'move_to_previous_stage', _context(site_admin, package=pkg))

    def test_site_admin_can_approve(self):
        user = factories.User()
        site_admin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        th.call_auth('move_to_next_stage', _context(site_admin, package=pkg))

    def test_site_admin_can_reject(self):
        user = factories.User()
        site_admin = factories.Sysadmin()
        pkg = factories.Dataset(user=user)
        data = th.call_action(
            'move_to_next_stage', _context(user), id=pkg['id'])
        pkg.update(data)
        th.call_auth(
            'move_to_previous_stage', _context(site_admin, package=pkg))
