
from Qt5 import QtCore
from rez.packages_ import iter_package_families, iter_packages
from rez.config import config
import traceback

_threads = []


def scan(no_local=False):
    paths = None
    seen = dict()

    if no_local:
        paths = config.nonlocal_packages_path

    for family in iter_package_families(paths=paths):
        name = family.name
        path = family.resource.location

        for package in iter_packages(name, paths=[path]):
            qualified_name = package.qualified_name

            if qualified_name in seen:
                seen[qualified_name]["locations"].append(path)
                continue

            doc = {
                "family": name,
                "version": str(package.version),
                "uri": package.uri,
                "tools": package.tools or [],
                "qualified_name": qualified_name,
                "timestamp": package.timestamp,
                "locations": [path],
            }
            seen[qualified_name] = doc

            yield doc


def defer(target,
          args=None,
          kwargs=None,
          on_success=lambda object: None,
          on_failure=lambda exception: None):
    """Perform operation in thread with callback

    Arguments:
        target (callable): Method or function to call
        callback (callable, optional): Method or function to call
            once `target` has finished.

    Returns:
        None

    """

    thread = Thread(target, args, kwargs, on_success, on_failure)
    thread.finished.connect(lambda: _threads.remove(thread))
    thread.start()

    # Cache until finished
    # If we didn't do this, Python steps in to garbage
    # collect the thread before having had time to finish,
    # resulting in an exception.
    _threads.append(thread)

    return thread


class Thread(QtCore.QThread):
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(Exception, str)

    def __init__(self,
                 target,
                 args=None,
                 kwargs=None,
                 on_success=None,
                 on_failure=None):
        super(Thread, self).__init__()

        self.args = args or list()
        self.kwargs = kwargs or dict()
        self.target = target
        self.on_success = on_success
        self.on_failure = on_failure

        connection = QtCore.Qt.BlockingQueuedConnection

        if on_success is not None:
            self.succeeded.connect(self.on_success, type=connection)

        if on_failure is not None:
            self.failed.connect(self.on_failure, type=connection)

    def run(self, *args, **kwargs):
        try:
            result = self.target(*self.args, **self.kwargs)

        except Exception as e:
            error = traceback.format_exc()
            return self.failed.emit(e, error)

        else:
            self.succeeded.emit(result)

