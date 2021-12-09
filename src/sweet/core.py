
from ._rezapi import SweetSuite, ResolvedContext


class SuiteOp(object):
    """Suite operator"""

    def __init__(self):
        self._name = ""
        self._desc = ""
        self._suite = None
        self._ctx_ops = dict()

        self.init_suite()

    def init_suite(self):
        """Initialise current working suite"""
        self._name = ""
        self._desc = ""
        self._suite = SweetSuite()
        self._ctx_ops.clear()

    def save_suite(self, storage):
        """Save current working suite"""
        storage.save(self)

    def load_suite(self, suite):
        """Load suite to replace current work"""
        self._suite = suite

    def set_name(self, value):
        """Set suite name"""
        self._name = value

    def set_description(self, value):
        """Set suite description"""
        self._desc = value

    def add_context(self, name="", requests=None):
        """Add an empty context"""
        ctx_op = ContextOp(name, requests)
        ctx_id = ctx_op.id()
        context = ctx_op.context()

        self._ctx_ops[ctx_id] = ctx_op
        self._suite.add_context(name=ctx_id, context=context)

    def drop_context(self, ctx_id):
        """Remove context from suite"""

    def find_context(self, ctx_id):
        """Find context from suite"""

    def iter_context(self):
        pass


class ContextOp(object):
    """Suite context operator"""

    def __init__(self, name="", requests=None):
        self._id = str(id(self))
        self._name = name
        self._context = None

        self.resolve(requests or [])

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._name)

    def __eq__(self, other):
        return isinstance(other, ContextOp) and self._id == other._id

    def id(self):
        """Returns context id"""
        return self._id

    def context(self):
        """Returns Rez resolved context"""
        return self._context

    def rename(self, name):
        """"""
        self._name = name

    def resolve(self, requests):
        """"""
        self._context = ResolvedContext(requests)

    def set_prefix(self):
        """"""

    def set_suffix(self):
        """"""


class ToolOp(object):
    """Context tool operator"""

    def set_hidden(self):
        """"""

    def set_alias(self):
        """"""


class Storage(object):
    """Suite storage"""
