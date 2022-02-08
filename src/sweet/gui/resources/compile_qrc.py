
import time
from pathlib import Path

here = Path(__file__).parent
resource = here
sweet_gui = resource.parent
sweet_pkg = sweet_gui.parent
sweet_src = sweet_pkg.parent
sweet_res = sweet_src / "sweet" / "gui" / "resources.py"


def trigger_update():
    """Trigger resource file update

    This doesn't update (compile) the qrc module, but update the timestamp
    in Resources class and the resource will be updated on next app launch.

    """
    with open(sweet_res, "r") as r:
        lines = r.readlines()
    for i, line in enumerate(lines):
        if "# !!<qrc-update-time>!!" in line:
            t = int(time.time())
            lines[i] = \
                f"    qrc_updated = {t}  # !!<qrc-update-time>!! don't touch\n"
            break
    else:
        raise Exception("Pragma not found.")

    with open(sweet_res, "w") as w:
        w.write("".join(lines))


if __name__ == "__main__":
    trigger_update()
