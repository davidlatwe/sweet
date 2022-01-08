
from ._vendor.Qt5 import QtCore, QtGui, QtWidgets
from . import resources as res


class CompleterProxyModel(QtCore.QSortFilterProxyModel):
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.CheckStateRole:  # disable checkbox
            return
        return super(CompleterProxyModel, self).data(index, role)


class CompleterModel(QtCore.QAbstractListModel):

    def __init__(self, *args, **kwargs):
        super(CompleterModel, self).__init__(*args, **kwargs)
        self._items = []

    def clear(self):
        self._items.clear()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._items)

    def add_families(self, families):
        self._items += [f.name for f in families]

    def add_versions(self, versions):
        # todo: omit internal package version
        self._items += [v.qualified for v in versions]


class RequestCompleter(QtWidgets.QCompleter):

    def __init__(self, *args, **kwargs):
        super(RequestCompleter, self).__init__(*args, **kwargs)
        self.setModelSorting(self.CaseInsensitivelySortedModel)
        self.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setWrapAround(False)

        model = CompleterModel()
        proxy = CompleterProxyModel()
        proxy.setSourceModel(model)
        self.setModel(proxy)

        self._model = model
        self._proxy = proxy

    def model(self):
        return self._model

    def proxy(self):
        return self._proxy

    def splitPath(self, path):
        # TODO: "==", "+<", "..", ...
        return path.split("-", 1)


class CompleterPopup(QtWidgets.QListView):
    def __init__(self, *args, **kwargs):
        super(CompleterPopup, self).__init__(*args, **kwargs)
        self.setObjectName("CompleterPopup")
        # this seems to be the only way to apply stylesheet to completer
        # popup.
        self.setStyleSheet(res.load_theme())


class RequestTextEdit(QtWidgets.QTextEdit):

    def __init__(self, *args, **kwargs):
        super(RequestTextEdit, self).__init__(*args, **kwargs)
        self.setObjectName("RequestTextEdit")
        self._completer = None

    def setCompleter(self, c):
        if self._completer is not None:
            self._completer.activated.disconnect()

        self._completer = c

        c.setPopup(CompleterPopup())
        c.setWidget(self)
        c.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        c.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        c.activated.connect(self.insert_completion)

    def completer(self):
        return self._completer

    def insert_completion(self, completion):
        completer = self._completer
        if completer.widget() is not self:
            return

        prefix = completer.completionPrefix()
        prefix = completer.splitPath(prefix)[-1]
        extra = len(completion) - len(prefix)

        if extra != 0:
            tc = self.textCursor()
            tc.movePosition(QtGui.QTextCursor.Left)
            tc.movePosition(QtGui.QTextCursor.EndOfWord)
            tc.insertText(completion[-extra:])
            self.setTextCursor(tc)

    def text_under_cursor(self):
        tc = self.textCursor()
        # can't use `QTextCursor.WordUnderCursor`, text like "maya-" that
        # ends with "-" will not be recognized as a word.
        tc.select(QtGui.QTextCursor.LineUnderCursor)
        text = tc.selectedText().rsplit(" ", 1)[-1]
        return text

    def focusInEvent(self, event):
        if self._completer is not None:
            self._completer.setWidget(self)

        super(RequestTextEdit, self).focusInEvent(event)

    def keyPressEvent(self, event):
        c = self._completer
        if c is not None and c.popup().isVisible():
            # The following keys are forwarded by the completer to the widget.
            if event.key() in (QtCore.Qt.Key_Escape,
                               QtCore.Qt.Key_Enter,
                               QtCore.Qt.Key_Return,
                               QtCore.Qt.Key_Backtab,
                               QtCore.Qt.Key_Tab):
                event.ignore()
                # Let the completer do default behavior.
                return

        is_shortcut = ((event.modifiers() & QtCore.Qt.ControlModifier) != 0
                       and event.key() == QtCore.Qt.Key_0)
        if c is None or not is_shortcut:
            # Do not process the shortcut when we have a completer.
            super(RequestTextEdit, self).keyPressEvent(event)

        ctrl_or_shift = event.modifiers() & (QtCore.Qt.ControlModifier
                                             | QtCore.Qt.ShiftModifier)
        if c is None or (ctrl_or_shift and len(event.text()) == 0):
            return

        end_of_word = " "  # "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        has_modifier = ((event.modifiers() != QtCore.Qt.NoModifier)
                        and not ctrl_or_shift)
        completion_prefix = self.text_under_cursor()

        if (not is_shortcut and (has_modifier
                                 or len(event.text()) == 0
                                 or len(completion_prefix) < 2
                                 or event.text()[-1] in end_of_word)):
            c.popup().hide()
            return

        popup = c.popup()
        if completion_prefix != c.completionPrefix():
            c.setCompletionPrefix(completion_prefix)
            popup.setCurrentIndex(c.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(popup.sizeHintForColumn(0)
                    + popup.verticalScrollBar().sizeHint().width())
        c.complete(cr)
