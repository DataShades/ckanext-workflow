import ckanext.workflow.interface as interface


class DraftState(interface.State):
    name = "draft"

    def get_dataset_permission_labels(self, labels):
        return ["draft"]

    def change(self, data_dict):
        if data_dict.get("review"):
            self.ctx["state"] = "active"
            self.ctx["private"] = True
            return ReviewState(self.ctx)
        return self


class ReviewState(interface.State):
    name = "review"

    def get_dataset_permission_labels(self, labels):
        return ["review"]

    def change(self, data_dict):
        if data_dict.get("publish"):
            self.ctx["private"] = False
            return PublishedState(self.ctx)
        elif data_dict.get("rework"):
            self.ctx["state"] = "draft"
            return DraftState(self.ctx)
        return self


class PublishedState(interface.State):
    name = "published"

    def get_dataset_permission_labels(self, labels):
        return ["published"]

    def change(self, data_dict):
        if data_dict.get("review"):
            self.ctx["private"] = True
            return ReviewState(self.ctx)
        return self
