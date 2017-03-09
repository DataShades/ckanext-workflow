import ckan.plugins.toolkit as tk
import ckan.lib.base as base
import ckan.model as model
from ckan.common import c, request, _
import ckanext.workflow.helpers as wh


class WorkflowController(base.BaseController):
    def approve(self, id=123):
        context = {
            'user': c.user,
            'model': model
        }
        tk.get_action('move_to_next_stage')(context, {'id': id})
        endpoint = request.referrer or '/'
        return base.redirect(endpoint)

    def reject(self, id):
        context = {
            'user': c.user,
            'model': model
        }
        reason = request.POST.get('reason')
        tk.get_action('move_to_previous_stage')(context, {
            'id': id,
            'reason': reason
        })
        endpoint = request.referrer or '/'
        return base.redirect(endpoint)

    def pending_list(self):
        context = {'model': model,
                   'user': c.user, 'auth_user_obj': c.userobj}
        try:
            tk.check_access('sysadmin', context, {})
        except tk.NotAuthorized:
            base.abort(401, _('Need to be system administrator to administer'))

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

        return base.render('workflow/pending_list.html', extra_vars=extra_vars)
