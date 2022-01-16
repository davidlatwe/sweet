
from blinker import signal


tool_flushed = signal("sop.tool.flushed")

tool_updated = signal("sop.tool.updated")

ctx_updating = signal("sop.ctx.updating")

ctx_updated = signal("sop.ctx.updated")

ctx_resolved = signal("sop.ctx.resolved")
"""Context resolved signal.
"""
