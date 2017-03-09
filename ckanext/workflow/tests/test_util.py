import nose.tools as nt
import ckanext.workflow.util as util


class TestBaseWorkflow:
    def setup(self):
        self.wf = util.BaseWorkflow()

    def test_stages_order(self):
        first = self.wf.start
        nt.assert_equal(str(first), 'unpublished')
        second = first.approve()
        nt.assert_equal(str(second), 'pending')
        third = second.approve()
        nt.assert_equal(str(third), 'published')

    def test_rejection_of_pending(self):
        pending = self.wf.start.approve()
        rejected = pending.reject()
        nt.assert_equal(rejected, self.wf.start)

    def test_rejection_of_published(self):
        published = self.wf.start.approve().approve()
        rejected = published.reject()
        nt.assert_equal(rejected, self.wf.start)
