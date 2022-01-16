
import os
import time
import shutil
import blinker
import unittest
import tempfile
from contextlib import contextmanager
from threading import Timer
from rez.config import config, _create_locked_config
from rez.package_repository import package_repository_manager as prm
from rezplugins.package_repository.memory import MemoryPackageRepository


class TestBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tempdir = None
        cls.settings = dict()

    def setUp(self):
        self.setup_config()

    def tearDown(self):
        self.teardown_config()
        self.teardown_tempdir()

    def setup_config(self):
        self._config = _create_locked_config(dict(self.settings))
        config._swap(self._config)

    def teardown_config(self):
        config._swap(self._config)
        self._config = None

    def teardown_tempdir(self):
        if not self._tempdir:
            return
        # cleanup tempdir
        retries = 5
        if os.path.exists(self._tempdir):
            for i in range(retries):
                try:
                    shutil.rmtree(self._tempdir)
                    break
                except Exception:
                    if i < (retries - 1):
                        time.sleep(0.2)

    def make_tempdir(self):
        self._tempdir = tempfile.mkdtemp(prefix="sweet_test_")
        return self._tempdir

    @contextmanager
    def wait_signals(self, signals, exact=True, timeout=3.0):
        """Wait for signals in specific interval or test failed.

        :param signals: A list of signals that expected to receive in context.
        :param exact: Check received signals in same order and exact amount if
            True, or just checking with sets.
        :param timeout: The interval for receiving signals.
        :type signals: list[blinker.NamedSignal]
        :type exact: bool
        :type timeout: float
        :return: None
        """
        received = []
        receivers = []

        for sig in signals:
            receivers.append(lambda s, _n=sig.name, **kw: received.append(_n))
            sig.connect(receivers[-1])

        timer = Timer(timeout, print, ["Timeout."])
        timer.start()

        try:
            yield
        finally:
            while len(received) != len(signals) and timer.is_alive():
                continue

            if not timer.is_alive():
                missed = [s.name for s in signals if s.name not in received]
                self.fail(
                    "Timeout, not all signals received in %.02f seconds : %s" %
                    (timeout, ", ".join(missed))
                )

            timer.cancel()
            receivers.clear()

            if exact:
                self.assertListEqual(received, [s.name for s in signals])
            else:
                self.assertSetEqual(set(received), {s.name for s in signals})


class MemPkgRepo(object):

    def __init__(self, path):
        assert path.startswith("memory@")
        self._repo = prm.get_repository(path)  # type: MemoryPackageRepository
        self._path = path

    @property
    def path(self):
        return self._path

    def add(self, name, **kwargs):
        version = str(kwargs.get("version", "_NO_VERSION"))
        if name not in self._repo.data:
            self._repo.data[name] = dict()
        self._repo.data[name].update({
            version: dict(name=name, **kwargs)
        })

    def flush(self):
        self._repo.data.clear()
        self._repo.clear_caches()
