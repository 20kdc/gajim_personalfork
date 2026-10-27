# Copyright (C) 2016-2018 Philipp Hörist <philipp AT hoerist.com>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import pprint
import sys
import threading
import traceback
from io import StringIO
from types import TracebackType

import nbxmpp
from gi.repository import Gdk
from gi.repository import Gtk

import gajim
from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.version import get_glib_version
from gajim.common.util.version import get_gobject_version
from gajim.common.util.version import get_os_name
from gajim.common.util.version import get_os_version
from gajim.common.util.version import get_soup_version

from gajim.gtk.builder import get_builder
from gajim.gtk.util import get_gtk_version

_exception_in_progress = threading.Lock()

ISSUE_URL = 'https://dev.gajim.org/gajim/gajim/issues/new'

ISSUE_TEXT = '''## Versions:
- OS: {}
- GTK Version: {}
- PyGObject Version: {}
- GLib Version : {}
- libsoup Version: {}
- python-nbxmpp Version: {}
- Gajim Version: {}

## Traceback
```
{}
```
## Steps to reproduce the problem
...'''


def _hook(type_: type[BaseException],
          value: BaseException,
          tb: TracebackType
          ) -> None:
    if not _exception_in_progress.acquire(False):
        # Exceptions have piled up, so we use the default exception
        # handler for such exceptions
        sys.__excepthook__(type_, value, tb)
        return

    ExceptionDialog(type_, value, tb)
    _exception_in_progress.release()


class ExceptionDialog(Gtk.ApplicationWindow):
    def __init__(self,
                 type_: type[BaseException],
                 value: BaseException,
                 tb: TracebackType
                 ) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_resizable(True)
        self.set_default_size(700, -1)
        self.set_title(_('Gajim - Error'))

        self._traceback_data = (type_, value, tb)

        self._ui = get_builder('exception_dialog.ui')
        self.add(self._ui.exception_box)

        self._ui.close_button.grab_focus()
        self._ui.close_button.grab_default()

        trace = StringIO()
        traceback.print_exception(type_, value, tb, None, trace)

        self._issue_text = self._get_issue_text(trace.getvalue())
        buffer_ = self._ui.exception_view.get_buffer()
        buffer_.set_text(self._issue_text)

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    @staticmethod
    def _get_issue_text(traceback_text: str) -> str:
        return ISSUE_TEXT.format(
            f'{get_os_name()} {get_os_version()}',
            get_gtk_version(),
            get_gobject_version(),
            get_glib_version(),
            get_soup_version(),
            nbxmpp.__version__,
            gajim.__version__,
            traceback_text)

    def _before_send(self, event: dict[str, Any], hint: Any) -> dict[str, Any]:
        # Make sure the exception value is set, GitLab needs it.
        # The value is the arg which is passed to the Exception.
        # e.g. raise Exception('Error')
        try:
            value = event['exception']['values'][0].get('value')
            if not value:
                event['exception']['values'][0]['value'] = 'Unknown'
        except Exception:
            pass

        # Remove the hostname of the machine
        event['server_name'] = 'redacted'
        pprint.pprint(event)
        return event


def init() -> None:
    if sys.platform == 'win32' or not sys.stderr.isatty():
        sys.excepthook = _hook
