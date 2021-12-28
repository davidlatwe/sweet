
import functools
from blinker import signal

SIG_TOOL_FLUSHED = signal("sop.tool.flushed")

SIG_TOOL_UPDATED = signal("sop.tool.updated")

SIG_CTX_UPDATING = signal("sop.ctx.updating")

SIG_CTX_UPDATED = signal("sop.ctx.updated")

SIG_CTX_RESOLVED = signal("sop.ctx.resolved")
"""Context resolved signal.
"""


def attach_sender(sender, func, sig):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        returned = func(*args, **kwargs)
        sig.send(sender)
        return returned
    return wrapper
