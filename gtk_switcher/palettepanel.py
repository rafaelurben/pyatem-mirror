# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
from gi.repository import Gtk, GObject, Gdk, GLib
import inspect

# State for the decorators
from pyatem.protocol import AtemProtocol

_palette_field = {}


class PalettePanel(Gtk.Overlay):
    __gtype_name__ = 'PalettePanel'

    def __init__(self, panel_name, connection: AtemProtocol, preset_domain=None):
        self.panel_name = panel_name
        self.connection = connection

        self.model_changing = False
        self.slider_held = False

        self._row = 0

        super(Gtk.Overlay, self).__init__()

        # Build expander for panel
        self.expander = Gtk.Expander()
        self.expander.get_style_context().add_class('bmdgroup')
        frame_label = Gtk.Label(self.panel_name)
        frame_label.get_style_context().add_class("heading")
        self.expander.set_label_widget(frame_label)
        self.expander.set_expanded(True)
        self.add(self.expander)

        # Optionally create the preset button for this panel
        self.preset_domain = None
        if preset_domain is not None:
            self.preset_domain = preset_domain
            self.preset_button = Gtk.MenuButton()
            self.preset_button.set_valign(Gtk.Align.START)
            self.preset_button.set_halign(Gtk.Align.END)
            self.set_class(self.preset_button, 'flat', True)
            self.set_class(self.preset_button, 'preset', True)
            self.apply_css(self.preset_button, self.provider)
            self.add_overlay(self.preset_button)

            hamburger = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.BUTTON)
            self.preset_button.set_image(hamburger)
            self.preset_button.set_name(preset_domain)

        # Create the expandable frame
        self.frame = Gtk.Frame()
        self.expander.add(self.frame)
        self.frame.set_margin_top(6)
        self.frame.get_style_context().add_class('view')

        # Create the grid to contain the settings
        self.grid = Gtk.Grid()
        self.grid.set_column_spacing(12)
        self.grid.set_row_spacing(12)
        self.grid.set_margin_top(12)
        self.grid.set_margin_bottom(12)
        self.grid.set_margin_start(12)
        self.grid.set_margin_end(12)
        self.frame.add(self.grid)

        self.show_all()

        # Hook up decorators
        ptype = self.__class__.__name__
        if ptype in _palette_field:
            callbacks = _palette_field[ptype]
            for selector in callbacks:
                for fun in callbacks[selector]:
                    fn_ref = getattr(self, fun)
                    self.connection.on(selector, fn_ref)

        GLib.timeout_add_seconds(1, self.initialize)

    def __repr__(self):
        return '<PalettePanel {}>'.format(self.panel_name)

    def initialize(self):
        ptype = self.__class__.__name__
        if ptype in _palette_field:
            callbacks = _palette_field[ptype]
            for selector in callbacks:
                if not selector.startswith('change:'):
                    continue
                part = selector.split(":")[1:]
                values = []
                if len(part) == 1:
                    values = [self.connection.mixerstate[part[0]]]
                elif len(part) == 2:
                    if part[1] == '*':
                        for f in self.connection.mixerstate[part[0]]:
                            values.append(self.connection.mixerstate[part[0]][f])
                    else:
                        values.append(self.connection.mixerstate[part[0]][int(part[1])])
                for fun in callbacks[selector]:
                    fn_ref = getattr(self, fun)
                    for v in values:
                        fn_ref(v)

        return False

    def set_class(self, widget, classname, state):
        if state:
            widget.get_style_context().add_class(classname)
        else:
            widget.get_style_context().remove_class(classname)

    def add_control(self, name, widget=None):
        label = Gtk.Label(name, xalign=1.0)
        label.get_style_context().add_class('dim-label')
        self.grid.attach(label, 0, self._row, 1, 1)
        if widget is not None:
            self.grid.attach(widget, 1, self._row, 1, 1)
        self._row += 1

    def run(self, cmd):
        """ Dispatch CMD to active connection """
        self.connection.send_commands([cmd])

    @classmethod
    def event(cls, name):
        """ Register the class name and function name in a global so on initialisation of the class
        the function can be hooked up to the active ATEM connection """

        def wrapper(func):
            global _palette_field
            panel, fn_name = func.__qualname__.split('.', maxsplit=1)
            if panel not in _palette_field:
                _palette_field[panel] = {}
            if name not in _palette_field[panel]:
                _palette_field[panel][name] = []

            _palette_field[panel][name].append(fn_name)
            return func

        return wrapper
