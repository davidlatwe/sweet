
# todo: test with pyside2 and pyqt5

from sweet.gui.app import Session

# testing reorder context by control
s = Session()
s.show()
s.process()

for c in range(4):
    s.ctrl.add_context(str(c), [])
    s.process()

s.ctrl.reorder_contexts([str(c) for c in range(4)])
s.process()

s.close()
