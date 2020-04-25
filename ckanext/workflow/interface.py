import abc


class State(metaclass=abc.ABCMeta):

    @abc.abstractproperty
    def context(self):
        pass

    @abc.abstractproperty
    def name(self):
        pass

    @abc.abstractmethod
    def next(self, **kwargs):
        pass

    @abc.abstractmethod
    def prev(self, **kwargs):
        pass
