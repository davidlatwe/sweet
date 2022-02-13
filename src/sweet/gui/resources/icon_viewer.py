
from pathlib import Path
from sweet.gui._vendor.Qt5 import QtWidgets, QtGui
from sweet.gui import resources as res


ext = ".svg", ".png"


def launch():
    app = QtWidgets.QApplication()

    res.load_themes()
    qss = res.get_style_sheet()

    dialog = QtWidgets.QDialog()
    view = QtWidgets.QListWidget()

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.addWidget(view)

    for icon in (Path(__file__).parent / "icons").iterdir():
        if not any(icon.name.endswith(e) for e in ext):
            continue

        icon_path = ":/icons/" + icon.name

        item = QtWidgets.QListWidgetItem()
        item.setText(icon_path)  # Hit Ctrl+C to copy icon path
        item.setIcon(QtGui.QIcon(icon_path))
        view.addItem(item)

    dialog.setWindowTitle("Sweet Icons")
    dialog.setWindowIcon(QtGui.QIcon(":/icons/rez_logo.svg"))
    dialog.setStyleSheet(qss)
    dialog.open()
    app.exec_()


if __name__ == "__main__":
    launch()
