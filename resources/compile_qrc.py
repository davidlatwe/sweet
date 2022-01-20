
import os
import sys
import shutil
import subprocess
from pathlib import Path

here = Path(__file__).parent
sweet_src = here.parent / "src"
sweet_gui = sweet_src / "sweet" / "gui"


def import_Resource():
    try:
        import sweet
    except ImportError:
        sys.path.append(str(sweet_src))

    try:
        from sweet.gui.resources import Resources
    except ImportError:
        raise

    return Resources


def compile_qrc():
    """The generated qrc .py works with both pyside2 and pyqt5, no matter
    which was used to generate it.
    """
    Resources = import_Resource()

    _cwd = os.getcwd()
    resources = here
    assert resources.is_dir(), f"{resources} not exists."

    # check compiler
    _bin_dir = Path(sys.executable).parent
    _execs = {
        "PyQt5": "pyrcc5",
        "PySide2": "pyside2-rcc",
    }
    for binding, rcc_exec in _execs.items():
        rcc_exec += ".exe" if sys.platform == "win32" else ""
        rcc_exec = _bin_dir / rcc_exec
        if os.access(rcc_exec, os.X_OK):
            break
    else:
        raise Exception("Resource compiler not found.")

    # go to work
    os.chdir(resources)

    q_res = []
    # icons
    for i in Path(resources / "icons").iterdir():
        if i.is_file() and any(i.name.endswith(_) for _ in Resources.icons_ext):
            q_res.append(f"\n    <file>icons/{i.name}</file>")
    # fonts
    for fn in Resources.fonts:
        q_res.append(f"\n    <file>fonts/{fn}</file>")
    # re-write resources/sweet-rc.qrc
    with open("sweet-rc.qrc", "w") as file:
        file.write(f"""
<!DOCTYPE RCC><RCC version="1.0">
<qresource>{''.join(q_res)}
</qresource>
</RCC>
""")

    # compile
    print(f"about to compile .qrc with {rcc_exec!r}...")
    subprocess.check_output(
        [str(rcc_exec), "sweet-rc.qrc", "-o", "sweet_rc.py"], cwd=str(resources)
    )
    shutil.move("sweet_rc.py", sweet_gui / "sweet_rc.py")

    # change to use vendorized Qt5.py
    os.chdir(sweet_gui)
    with open("sweet_rc.py", "r") as r:
        s = r.read().replace(
            (
                "from PyQt5 import QtCore" if binding == "PyQt5"
                else "from PySide2 import QtCore"
            ),
            "from ._vendor.Qt5 import QtCore",
        )
    with open("sweet_rc.py", "w") as w:
        w.write(s)

    # go home
    os.chdir(_cwd)


if __name__ == "__main__":
    compile_qrc()
