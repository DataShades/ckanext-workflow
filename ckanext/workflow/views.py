from builtins import str
import ckan.plugins.toolkit as tk
import ckan.lib.base as base
import ckan.lib.helpers as h
import ckan.model as model
from ckan.common import c, request, _
import ckanext.workflow.helpers as wh
from flask import Blueprint, make_response

workflow = Blueprint('workflow', __name__)
abort = base.abort
render = base.render

def approve(id):
    """Approve common dataset.

    If package just've got its last stage and it looks like
    revision - redirects to merge_revision route
    """
    context = {
        'user': c.user,
        'model': model
    }
    endpoint = request.referrer or '/'

    pkg = tk.get_action('package_show')(context, {'id': id})
    wf, _ = wh.get_workflow_from_package(pkg)

    next = str(wh.get_stage_from_package(pkg).approve())
    if next == str(wf.finish) and wh.is_revision(pkg):
        endpoint = h.url_for('workflow.merge_dataset_revision', id=id)
    tk.get_action('move_to_next_stage')(context, {'id': id})

    return tk.redirect_to(endpoint)

def reject(id):
    context = {
        'user': c.user,
        'model': model
    }
    reason = request.form.get('reason')
    tk.get_action('move_to_previous_stage')(context, {
        'id': id,
        'reason': reason
    })
    endpoint = request.referrer or '/'
    return tk.redirect_to(endpoint)

def rescind(id):
    context = {
        'user': c.user,
        'model': model
    }
    tk.get_action('workflow_rescind_dataset')(context, {'id': id})
    return tk.redirect_to(h.url_for('dataset.read', id=id))

def create_revision(id):
    context = {
        'user': c.user,
        'model': model
    }

    pkg = tk.get_action('create_dataset_revision')(context, {'id': id,})
    return tk.redirect_to(h.url_for('dataset.read', id=pkg['id']))

def merge_revision(id):
    context = {
        'user': c.user,
        'model': model
    }

    pkg = tk.get_action('merge_dataset_revision')(context, {'id': id})
    return tk.redirect_to(h.url_for('dataset.read', id=pkg['id']))

def pending_list():
    context = {'model': model,
                'user': c.user, 'auth_user_obj': c.userobj}
    try:
        tk.check_access('sysadmin', context, {})
    except tk.NotAuthorized:
        abort(401, _('Need to be system administrator to administer'))

    extra_vars = {
        'datasets': model.Session.query(model.Package).join(
            model.PackageExtra
        )
        .filter(
                model.PackageExtra.key == wh._workflow_stage_field(),
                model.PackageExtra.value.in_(['pending']),
                model.Package.state == 'active'
        )
    }

    return render('workflow/pending_list.html', extra_vars=extra_vars)

def purge(id):
    context = {'model': model,
                'user': c.user, 'auth_user_obj': c.userobj}

    try:
        pkg = tk.get_action('package_show')(context, {'id': id})
        del context['package']
        tk.check_access('purge_unpublished_dataset', context, pkg)
    except tk.NotAuthorized:
        abort(401, _('Not authorized to see this page'))

    context['ignore_auth'] = True
    tk.get_action('dataset_purge')(context, {'id': id})
    return tk.redirect_to(h.url_for('dataset.search'))

workflow.add_url_rule(u'/workflow/dataset/<id>/approve', 'workflow_approve', view_func=approve)
workflow.add_url_rule(u'/workflow/dataset/<id>/reject', 'workflow_reject', view_func=reject, methods=(u'POST', ))
workflow.add_url_rule(u'/workflow/dataset/<id>/rescind', 'workflow_rescind', view_func=rescind)
workflow.add_url_rule(u'/workflow/approvals', endpoint='workflow_pending_list', view_func=pending_list)
workflow.add_url_rule(u'/workflow/dataset/<id>/merge_revision', 'merge_dataset_revision', view_func=merge_revision)
workflow.add_url_rule(u'/workflow/dataset/<id>/create_revision', 'create_dataset_revision', view_func=create_revision)
workflow.add_url_rule(u'/workflow/dataset/<id>/purge', 'purge_unpublished_dataset', view_func=purge)


def get_blueprints():
    return [workflow]
