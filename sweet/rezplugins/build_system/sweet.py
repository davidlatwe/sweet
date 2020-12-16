
import os
import sys
from rezplugins.build_system import custom
from rez.resolved_context import ResolvedContext


class SweetBuildSystem(custom.CustomBuildSystem):

    @classmethod
    def name(cls):
        return "sweet"


def _FWD__invoke_suite_tool_alias_in_live(package_requests,
                                          context_name,
                                          tool_name,
                                          prefix_char=None,
                                          _script=None,
                                          _cli_args=None):
    suite_path = os.path.dirname(os.path.dirname(_script))
    context = ResolvedContext(package_requests)

    from rez.wrapper import Wrapper
    w = Wrapper.__new__(Wrapper)
    w._init(suite_path, context_name, context, tool_name, prefix_char)
    retcode = w.run(*(_cli_args or []))
    sys.exit(retcode)


def register_plugin():
    return SweetBuildSystem
