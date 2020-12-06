
import time
from datetime import datetime
from ..vendor.Qt5 import QtWidgets


class TableViewRowHover(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent=None):
        super(TableViewRowHover, self).__init__(parent)
        self.view = None
        self._col = None

    def paint(self, painter, option, index):
        row = index.row()
        column = index.column()

        if option.state & QtWidgets.QStyle.State_MouseOver:
            self._col = column
            while True:
                super(TableViewRowHover, self).paint(painter, option, index)
                if column == 0:
                    break
                column -= 1  # repaint previous columns
                index = index.sibling(row, column)
                option.rect = self.view.visualRect(index)

        else:
            if self._col is not None and column > self._col:
                # hover the reset of columns
                option.state |= QtWidgets.QStyle.State_MouseOver
            else:
                self._col = None

            super(TableViewRowHover, self).paint(painter, option, index)


def pretty_date(t, now=None, strftime="%b %d %Y %H:%M"):
    """Parse datetime to readable timestamp

    Within first ten seconds:
        - "just now",
    Within first minute ago:
        - "%S seconds ago"
    Within one hour ago:
        - "%M minutes ago".
    Within one day ago:
        - "%H:%M hours ago"
    Else:
        "%Y-%m-%d %H:%M:%S"

    """

    assert isinstance(t, datetime)
    if now is None:
        now = datetime.now()
    assert isinstance(now, datetime)
    diff = now - t

    second_diff = diff.seconds
    day_diff = diff.days

    # future (consider as just now)
    if day_diff < 0:
        return "just now"

    # history
    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(second_diff // 60) + " minutes ago"
        if second_diff < 86400:
            minutes = (second_diff % 3600) // 60
            hours = second_diff // 3600
            return "{0}:{1:02d} hours ago".format(hours, minutes)

    return t.strftime(strftime)


def pretty_timestamp(t, now=None):
    """Parse timestamp to user readable format

    >>> pretty_timestamp("20170614T151122Z", now="20170614T151123Z")
    'just now'

    >>> pretty_timestamp("20170614T151122Z", now="20170614T171222Z")
    '2:01 hours ago'

    Args:
        t (str): The time string to parse.
        now (str, optional)

    Returns:
        str: human readable "recent" date.

    """

    if now is not None:
        try:
            now = time.strptime(now, "%Y%m%dT%H%M%SZ")
            now = datetime.fromtimestamp(time.mktime(now))
        except ValueError as e:
            print("Can't parse 'now' time format: {0} {1}".format(t, e))
            return None

    if isinstance(t, (int, float)):
        dt = datetime.fromtimestamp(t)
    else:
        # Parse the time format as if it is `str` result from
        # `pyblish.lib.time()` which usually is stored in Avalon database.
        try:
            t = time.strptime(t, "%Y%m%dT%H%M%SZ")
        except ValueError as e:
            print("Can't parse time format: {0} {1}".format(t, e))
            return None
        dt = datetime.fromtimestamp(time.mktime(t))

    # prettify
    return pretty_date(dt, now=now)


class PrettyTimeDelegate(QtWidgets.QStyledItemDelegate):
    """A delegate that displays a timestamp as a pretty date.

    This displays dates like `pretty_date`.

    """

    def displayText(self, value, locale):

        if value is None:
            # Ignore None value
            return

        return pretty_timestamp(value)
