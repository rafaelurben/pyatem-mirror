# Copyright 2021 - 2022, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
import math

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GObject, Gio, Gdk


class AdjustmentEntry(Gtk.Entry):
    __gtype_name__ = 'AdjustmentEntry'

    def __init__(self, adjustment, display_min, display_max):
        super(Gtk.Entry, self).__init__()
        self.adjustment = None
        self.updating_model = False
        self.display_min = display_min
        self.display_max = display_max
        self.debounce = False
        self.set_adjustment(adjustment)
        self.get_style_context().add_class('adjustmententry')
        self.display = 0

    def set_adjustment(self, adjustment):
        self.adjustment = adjustment
        self.adjustment.connect('value-changed', self.adj_changed)
        self.adj_changed()

    def get_adjustment(self):
        return self.adjustment

    def _remap(self, value, old_min, old_max, new_min, new_max):
        return ((value - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min

    def _update(self, *args):
        self.updating_model = True
        text = "{:.2f}".format(self.display)
        # Entry.set_text() segfaults GTK3 occasionally
        self.set_text(text)
        self.updating_model = False
        self.debounce = False

    def adj_changed(self, *args):
        if hasattr(self.adjustment, 'get_value_log'):
            value = self.adjustment.get_value_log()
        else:
            value = self.adjustment.get_value()
        self.display = self._remap(value, self.adjustment.get_lower(), self.adjustment.get_upper(), self.display_min,
                                   self.display_max)

        if not self.debounce:
            self.debounce = True
            GLib.timeout_add(500, self._update)

    def do_activate(self):
        if not isinstance(self, AdjustmentEntry):
            return
        if self.updating_model:
            return

        try:
            value = float(self.get_text())
        except:
            return

        value = self._remap(value, self.display_min, self.display_max, self.adjustment.get_lower(),
                            self.adjustment.get_upper())

        if hasattr(self.adjustment, 'set_value_log'):
            self.adjustment.set_value_log(value)
        else:
            self.adjustment.set_value(value)
