
import functools
from blinker import signal


sig_tool_flushed = signal("sop.tool.flushed")
sig_tool_updated = signal("sop.tool.updated")


def attach_sender(sender, func, sig):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        returned = func(*args, **kwargs)
        sig.send(sender)
        return returned
    return wrapper
