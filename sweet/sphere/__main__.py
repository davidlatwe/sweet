
import os
import sys
from Qt5 import QtWidgets
from . import show


os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
show()
sys.exit(app.exec_())
