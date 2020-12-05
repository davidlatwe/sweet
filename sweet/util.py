
from Qt5 import QtCore
import traceback

_threads = []


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

