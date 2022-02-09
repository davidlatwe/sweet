
import os
import webbrowser
import subprocess
from rez.packages import Variant
from rez.rex import ActionInterpreter
from rez.resolved_context import ResolvedContext


def open_file_location(fname):
    if os.path.exists(fname):
        if os.name == "nt":
            fname = os.path.normpath(fname)
            subprocess.Popen("explorer /select,%s" % fname)
        else:
            webbrowser.open(os.path.dirname(fname))
    else:
        raise OSError("%s did not exist" % fname)


class Singleton(type):
    """A metaclass for creating singleton
    https://stackoverflow.com/q/6760685/14054728
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ContextEnvInspector(ActionInterpreter):
    """A rex interpreter for inspecting context environ vars

    By parsing rex commenting actions, trace which environ key-value
    was set/append/prepend by which package or by rez.

    Example 1:
        >>> from rez.resolved_context import ResolvedContext
        >>>
        >>> context = ResolvedContext(["maya-2020", "python"])
        >>> interp = ContextEnvInspector()
        >>> executor = context._create_executor(interp, parent_environ=None)
        >>> context._execute(executor)
        >>> executor.get_output()
        profit!!

    Example 2:
        >>> from rez.resolved_context import ResolvedContext
        >>>
        >>> context = ResolvedContext(["maya-2020", "python"])
        >>> ContextEnvInspector.inspect(context)
        easy profit!!!

    """
    expand_env_vars = True

    def __init__(self, context: ResolvedContext = None):
        self._scope = None
        self._envs = []
        self._pkgs = {}

        if context and context.success:
            for pkg in context.resolved_packages:
                self._pkgs[pkg.qualified_name] = pkg

    @classmethod
    def inspect(cls, context):
        interp = cls(context=context)
        executor = context._create_executor(interp, parent_environ=None)
        context._execute(executor)
        return executor.get_output()

    def get_output(self, style=None):
        """
        :param style:
        :rtype: list[tuple[Variant or str or None, str, str]]
        """
        return [
            (self._pkgs.get(scope, scope), key, value)
            for scope, key, value in self._envs
        ]

    def setenv(self, key, value):
        self._envs.append((self._scope, key, value))
        if key.startswith("REZ_") and key.endswith("_ORIG_ROOT"):
            # is a cached package (just a note for now)
            pass

    def prependenv(self, key, value):
        self._envs.append((self._scope, key, value))

    def appendenv(self, key, value):
        self._envs.append((self._scope, key, value))

    def unsetenv(self, key):
        pass

    def resetenv(self, key, value, friends=None):
        pass

    def info(self, value):
        pass

    def error(self, value):
        pass

    def command(self, value):
        pass

    def comment(self, value):
        # header comment
        sys_setup = "system setup"
        variables = "package variables"
        pre_commands = "pre_commands"
        commands = "commands"
        post_commands = "post_commands"
        ephemeral = "ephemeral variables"
        post_sys_setup = "post system setup"
        # minor header comment
        pkg_variables = "variables for package "
        pkg_pre_commands = "pre_commands from package "
        pkg_commands = "commands from package "
        pkg_post_commands = "post_commands from package "

        if value in (sys_setup, variables):
            self._scope = "system"

        elif value in (pre_commands, commands, post_commands):
            pass

        elif value.startswith(pkg_variables):
            self._scope = value[len(pkg_variables):]

        elif value.startswith(pkg_pre_commands):
            self._scope = value[len(pkg_pre_commands):]

        elif value.startswith(pkg_commands):
            self._scope = value[len(pkg_commands):]

        elif value.startswith(pkg_post_commands):
            self._scope = value[len(pkg_post_commands):]

        elif value in (ephemeral, post_sys_setup):
            self._scope = "post-system"

    def source(self, value):
        pass

    def alias(self, key, value):
        pass

    def shebang(self):
        pass

    def get_key_token(self, key):
        return "${%s}" % key  # It's just here because the API requires it.

    def _bind_interactive_rez(self):
        pass

    def _saferefenv(self, key):
        pass
