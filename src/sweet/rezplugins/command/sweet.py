"""
Rez suite composing GUI
"""
import os
import sys
import types
import argparse
try:
    from rez.command import Command
except ImportError:
    Command = object


command_behavior = {}


def rez_cli():
    from rez.cli._main import run
    from rez.cli._entry_points import check_production_install
    check_production_install()
    try:
        return run("sweet")
    except KeyError:
        pass
        # for rez version that doesn't have Command type plugin
    return standalone_cli()


def standalone_cli():
    # for running without rez's cli
    parser = argparse.ArgumentParser("sweet")
    setup_parser(parser)
    opts = parser.parse_args()
    return command(opts)


def setup_parser(parser, completions=False):
    parser.add_argument("--version", action="store_true",
                        help="Print out version of this plugin command.")
    parser.add_argument("--gui", action="store_true")


def command(opts, parser=None, extra_arg_groups=None):
    import logging
    from sweet import cli, report
    report.init_logging()

    if opts.debug:
        log = logging.getLogger("sweet")
        stream_handler = next(h for h in log.handlers if h.name == "stream")
        stream_handler.setLevel(logging.DEBUG)

    if opts.version:
        from sweet._version import print_info
        sys.exit(print_info())

    if opts.gui:
        from sweet.gui import app
        sys.exit(app.launch())

    return cli.main()


class CommandSweet(Command):
    schema_dict = {
        "suite_roots": dict,
        "default_root": str,
        "release_root": str,
        "on_suite_saved_callback": types.FunctionType,
        "omit_internal_version": str,
    }

    @classmethod
    def name(cls):
        return "sweet"


def find_configs(dir_path):
    configs = list()

    while True:
        config_file = os.path.join(dir_path, ".rezconfig.py")
        if os.path.isfile(config_file):
            configs.append(config_file)

        parent_dir = os.path.dirname(dir_path)
        if parent_dir == dir_path:
            break  # reach root

        dir_path = parent_dir

    return configs


def _FWD__invoke_suite_tool_alias_in_live(package_requests,
                                          context_name,
                                          tool_name,
                                          prefix_char=None,
                                          _script=None,
                                          _cli_args=None):
    # Load configs
    from rez.resolved_context import ResolvedContext
    from rez.config import _load_config_from_filepaths, config
    # todo: config override should be handled by the Application
    #   launcher, not sweet.
    configs = find_configs(os.getcwd())
    overrides, _ = _load_config_from_filepaths(configs)
    for key, value in overrides.items():
        config.override(key, value)

    # todo: instead of parsing requests, load the rxt and re-resolve
    #   again.
    suite_path = os.path.dirname(os.path.dirname(_script))
    context = ResolvedContext(package_requests)

    from rez.wrapper import Wrapper
    w = Wrapper.__new__(Wrapper)
    w._init(suite_path, context_name, context, tool_name, prefix_char)
    retcode = w.run(*(_cli_args or []))
    sys.exit(retcode)


def register_plugin():
    return CommandSweet
