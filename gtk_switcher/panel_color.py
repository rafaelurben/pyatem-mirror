# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
from gi.repository import Gtk, GObject, Gdk

from gtk_switcher.palettepanel import PalettePanel
from pyatem.command import ColorGeneratorCommand


class ColorPanel(PalettePanel):
    __gtype_name__ = 'ColorPanel'

    def __init__(self, connection):
        self.connection = connection
        self.name = _("Color Generators")

        super().__init__(self.name, connection, preset_domain="colors", preset_fields=['color-generator'])

        self.colors = {}
        for c in range(2):
            widget = Gtk.ColorButton()
            widget.index = c
            widget.connect('color-set', self.on_color_set)
            self.colors[c] = widget
            self.add_control(_("Color {}").format(c + 1), widget)

        self.show_all()

    def __repr__(self):
        return '<ColorPanel {}>'.format(self.panel_name)

    @PalettePanel.event('change:color-generator:*')
    def on_color_change(self, data):
        r, g, b = data.get_rgb()
        color = Gdk.RGBA()
        color.red = r
        color.green = g
        color.blue = b
        color.alpha = 1.0
        self.colors[data.index].set_rgba(color)

    def on_color_set(self, widget):
        color = widget.get_rgba()
        cmd = ColorGeneratorCommand.from_rgb(index=widget.index, red=color.red, green=color.green, blue=color.blue)
        self.run(cmd)
