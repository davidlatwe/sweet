
import unittest
from rez.config import config, _create_locked_config
from rez.package_repository import package_repository_manager as prm
from rezplugins.package_repository.memory import MemoryPackageRepository


class TestBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.settings = dict()

    def setUp(self):
        self.setup_config()

    def tearDown(self):
        self.teardown_config()

    def setup_config(self):
        self._config = _create_locked_config(dict(self.settings))
        config._swap(self._config)

    def teardown_config(self):
        config._swap(self._config)
        self._config = None


class MemPkgRepo(object):

    def __init__(self, path):
        assert path.startswith("memory@")
        self._repo = prm.get_repository(path)  # type: MemoryPackageRepository
        self._path = path

    @property
    def path(self):
        return self._path

    def add(self, name, **kwargs):
        version = kwargs.get("version", "_NO_VERSION")
        if name not in self._repo.data:
            self._repo.data[name] = dict()
        self._repo.data[name].update({
            version: dict(name=name, **kwargs)
        })

    def flush(self):
        self._repo.data.clear()
        self._repo.clear_caches()
