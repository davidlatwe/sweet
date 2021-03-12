
from .vendor.Qt5 import QtCore, QtWidgets
from .vendor import qargparse
from . import resources as res


class Preference(QtWidgets.QWidget):
    """Sweet settings
    Changes will be saved and effected immediately.
    """
    changed = QtCore.Signal(str, object)

    def __init__(self, state, parent=None):
        super(Preference, self).__init__(parent=parent)
        self.setObjectName("Preference")

        options = [
            qargparse.Separator("Appearance"),

            qargparse.Enum(
                "theme",
                items=res.theme_names(),
                default=0,
                initial=state.retrieve("theme"),
                help="GUI skin. May need to restart Sweet after changed."),

            qargparse.Button("resetLayout", help=(
                "Reset stored layout to their defaults"
            )),

            qargparse.Separator("Settings"),

            qargparse.Integer("recentSuiteCount",
                              min=1,
                              default=10,
                              initial=state.retrieve("recentSuiteCount")),

            qargparse.Enum("suiteOpenAs",
                           items=["Ask", "Loaded", "Import"],
                           default=0,
                           initial=state.retrieve("suiteOpenAs")),
        ]

        widgets = {
            "doc": QtWidgets.QLabel(),
            "scroll": QtWidgets.QScrollArea(),
            "options": qargparse.QArgumentParser(options),
        }
        widgets["doc"].setObjectName("DocStrings")

        widgets["doc"].setText(self.__doc__.strip())

        widgets["scroll"].setWidget(widgets["options"])
        widgets["scroll"].setWidgetResizable(True)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["doc"], 0, 0, 1, -1)
        layout.addWidget(widgets["scroll"], 1, 0, 1, -1)
        layout.setSpacing(4)

        widgets["options"].changed.connect(self.on_option_changed)

        self._widgets = widgets
        self._state = state

    def on_option_changed(self, argument):
        name = argument["name"]
        value = argument.read()
        self._state.store(name, value)
        self.changed.emit(name, value)
