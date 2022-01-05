
import re
from ..gui.vendor.Qt5 import QtWidgets, QtGui, QtCore
from ..gui import resources as res
from . import models


class CurrentSuite(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(CurrentSuite, self).__init__(*args, **kwargs)
        self.setObjectName("SuiteView")

        name = QtWidgets.QLineEdit()
        description = QtWidgets.QTextEdit()
        load_path = QtWidgets.QLineEdit()

        name.setPlaceholderText("Suite name..")
        description.setPlaceholderText("Suite description.. (optional)")
        description.setMinimumHeight(5)
        load_path.setReadOnly(True)
        load_path.setMinimumHeight(5)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(name)
        layout.addWidget(description, stretch=True)
        layout.addWidget(load_path)
        layout.addStretch()

        self._min_height = self.minimumSizeHint().height()
        self._hide_on_min = [description, load_path]

    def resizeEvent(self, event):
        h = event.size().height()
        for w in self._hide_on_min:
            w.setVisible(h > self._min_height)
        return super(CurrentSuite, self).resizeEvent(event)


class SuiteSavingDialog(QtWidgets.QDialog):
    pass


class ContextStack(QtWidgets.QWidget):
    added = QtCore.Signal(str)
    dropped = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        super(ContextStack, self).__init__(*args, **kwargs)
        self.setObjectName("ContextStack")

        label = QtWidgets.QLabel("Context Stack")

        btn_add = QtWidgets.QPushButton()
        btn_add.setIcon(res.icon("images", "plus.svg"))

        btn_rm = QtWidgets.QPushButton()
        btn_rm.setIcon(res.icon("images", "trash-fill-dim.svg"))

        stack = QtWidgets.QTreeView()
        stack.setDragEnabled(True)
        stack.setAcceptDrops(True)
        stack.setDropIndicatorShown(True)
        stack.setDragDropMode(stack.InternalMove)
        stack.setDefaultDropAction(QtCore.Qt.MoveAction)

        model = models.ContextStackModel()
        stack.setModel(model)

        # layout

        action_layout = QtWidgets.QVBoxLayout()
        action_layout.addWidget(btn_add)
        action_layout.addWidget(btn_rm)
        action_layout.addStretch()

        stack_layout = QtWidgets.QHBoxLayout()
        stack_layout.addLayout(action_layout)
        stack_layout.addWidget(stack)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(stack_layout)

        # signals

        btn_add.clicked.connect(self.add_context)
        btn_rm.clicked.connect(self.drop_context)

        self._stack = stack
        self._model = model

    def on_context_added(self, ctx):
        item = QtGui.QStandardItem(ctx.name)
        self._model.insertRow(0, item)

    def on_context_dropped(self, name):
        pass

    def on_suite_reset(self):
        self._model.clear()

    def add_context(self):
        existing_names = ["foo"]  # todo: get existing names from model
        widget = ContextNameEditor(existing_names=existing_names)
        dialog = YesNoDialog(widget, parent=self)
        dialog.setWindowTitle("Name New Context")

        def on_finished(result):
            if result:
                self.added.emit(widget.get_name())

        dialog.finished.connect(on_finished)
        dialog.open()

    def drop_context(self):
        pass

    def refresh(self, contexts):
        for ctx in contexts:
            item = QtGui.QStandardItem(ctx.name)
            self._model.appendRow(item)


class YesNoDialog(QtWidgets.QDialog):

    def __init__(self, widget, *args, **kwargs):
        super(YesNoDialog, self).__init__(*args, **kwargs)

        btn_accept = QtWidgets.QPushButton("Accept")
        btn_reject = QtWidgets.QPushButton("Cancel")

        btn_accept.setObjectName("AcceptButton")
        btn_reject.setObjectName("CancelButton")
        btn_accept.setDefault(True)
        btn_accept.setEnabled(False)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(widget, 0, 0, 1, 2)
        layout.addWidget(btn_accept, 1, 0, 1, 1)
        layout.addWidget(btn_reject, 1, 1, 1, 1)

        btn_accept.clicked.connect(lambda: self.done(self.Accepted))
        btn_reject.clicked.connect(lambda: self.done(self.Rejected))
        if hasattr(widget, "validated"):
            widget.validated.connect(btn_accept.setEnabled)


class ContextNameEditor(QtWidgets.QWidget):
    validated = QtCore.Signal(bool)
    colors = {
        "ready": QtGui.QColor("#78879b"),
        "invalid": QtGui.QColor("#C84747"),
    }

    def __init__(self, existing_names, *args, **kwargs):
        super(ContextNameEditor, self).__init__(*args, **kwargs)

        validator = RegExpValidator("^[a-zA-Z0-9_.]*$")

        name = QtWidgets.QLineEdit()
        name.setValidator(validator)
        name.setPlaceholderText("Input context name..")
        name.setToolTip("Only alphanumeric characters (A-Z a-z 0-9), "
                        "'_' and '.' are allowed.")

        message = QtWidgets.QLabel()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(name)
        layout.addWidget(message)

        timer = QtCore.QTimer(self)

        anim = QtCore.QPropertyAnimation()
        anim.setEasingCurve(QtCore.QEasingCurve.InCubic)
        anim.setDuration(1000)
        anim.setStartValue(self.colors["invalid"])
        anim.setEndValue(self.colors["ready"])

        validator.validated.connect(self.on_validated)
        name.textChanged.connect(self.on_named)
        timer.timeout.connect(lambda: message.setText(""))

        self._timer = timer
        self.animation = anim
        self._status_color = self.colors["ready"]
        self._name = ""
        self._message = message
        self._existing_names = existing_names

        anim.setTargetObject(self)
        anim.setPropertyName(QtCore.QByteArray(b"status_color"))

        self.validated.emit(False)

    def on_validated(self, state):
        if state == QtGui.QValidator.Invalid:
            self.log("Invalid char.")
            self.animation.stop()
            self.animation.start()

    def on_named(self, value):
        unique_name = value not in self._existing_names
        self._name = value
        self.validated.emit(unique_name and bool(value))
        if not unique_name:
            self.log("Duplicated name.")
            self.animation.stop()
            self.animation.start()

    def get_name(self):
        return self._name

    def log(self, message):
        self._message.setText(str(message))
        self._timer.setSingleShot(True)
        self._timer.start(1000)

    def _get_status_color(self):
        return self._status_color

    def _set_status_color(self, color):
        self._status_color = color
        self.setStyleSheet("border-color: %s;" % color.name())

    status_color = QtCore.Property(QtGui.QColor,
                                   _get_status_color,
                                   _set_status_color)


class RegExpValidator(QtGui.QRegExpValidator):
    validated = QtCore.Signal(QtGui.QValidator.State)

    def __init__(self, pattern):
        super(RegExpValidator, self).__init__(QtCore.QRegExp(pattern))
        self._pattern = re.compile(pattern)

    def validate(self, text, pos):
        state, t, c = super(RegExpValidator, self).validate(text, pos)
        self.validated.emit(state)
        return state, t, c


class ToolStack(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ToolStack, self).__init__(*args, **kwargs)
        self.setObjectName("ToolStack")

        label = QtWidgets.QLabel("Tool Stack")

        btn_filter = QtWidgets.QPushButton()  # toggleable
        btn_filter.setIcon(res.icon("images", "funnel-fill.svg"))

        stack = QtWidgets.QTreeView()

        model = models.ToolStackModel()
        stack.setModel(model)

        # layout

        action_layout = QtWidgets.QVBoxLayout()
        action_layout.addWidget(btn_filter)
        action_layout.addStretch()

        stack_layout = QtWidgets.QHBoxLayout()
        stack_layout.addLayout(action_layout)
        stack_layout.addWidget(stack)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(stack_layout)

        # signals


class RequestEditor(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(RequestEditor, self).__init__(*args, **kwargs)

        request = QtWidgets.QTextEdit()
        resolve = QtWidgets.QPushButton("Resolve")
        resolve.setObjectName("ContextResolveOpBtn")

        request.setPlaceholderText("requests..")
        request.setAcceptRichText(False)
        request.setTabChangesFocus(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(request)
        layout.addWidget(resolve)


class ResolvedPackages(QtWidgets.QWidget):
    pass


class ResolvedEnvironment(QtWidgets.QWidget):
    pass
