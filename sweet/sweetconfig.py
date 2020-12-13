

# default suite saving root
default_root = "local"


def saving_roots():
    """Return a dict of suite saving root path
    """
    from collections import OrderedDict as odict
    from . import util
    return odict([
        ("draft", util.normpath("~/rez/sweet/drafts")),
        ("local", util.normpath("~/rez/sweet/suites")),
    ])


# suite save options .ini file name
save_options_ini = "defaultSuiteOptions"


def suite_save_options():
    """Additional suite save option widgets

    Returns:
        list: A list of qargparse.QArgument instance

    """
    from .vendor import qargparse
    return [
        qargparse.Separator("demoArg"),
        qargparse.Integer("demoOption"),
        qargparse.String("version"),
        qargparse.String("path"),
    ]


def on_suite_saved_callback(suite_dir, options):
    """A callback that runs after suite saved

    This could be used to create/update Allzpark profile, or triggering
    VCS.

    Args:
        suite_dir (str): suite saved path
        options (dict): suite save options

    Returns:
        None

    """
    import os
    import errno
    import shutil
    from rez.package_maker import PackageMaker
    from rez.developer_package import DeveloperPackage

    root, name = os.path.split(suite_dir)

    maker = PackageMaker(name, package_cls=DeveloperPackage)
    maker.version = options["version"]  # or query from db
    maker.requires = []
    maker.variants = None
    maker.commands = '\n'.join([
        "env.PATH.prepend('{root}/suite/bin')",
    ])

    package = maker.get_package()

    data = maker._get_data()
    data["sweetAutoBuild"] = True  # breadcrumb for preprocessing

    # preprocessing
    result = package._get_preprocessed(data)

    if result:
        package, data = result

    variant = next(package.iter_variants())
    variant_ = variant.install(options["path"])

    root = variant_.root

    if root:
        try:
            os.makedirs(root)
        except OSError as e:
            if e.errno == errno.EEXIST:
                # That's ok
                pass
            else:
                raise

        # copy suite to package
        shutil.copytree(suite_dir, os.path.join(root, "suite"))

    return None
