# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
from gi.repository import Gtk, GObject, Gdk

from gtk_switcher.palettepanel import PalettePanel
from pyatem.command import MediaplayerSelectCommand


class MediaPlayerPanel(PalettePanel):
    __gtype_name__ = 'MediaPlayerpanel'

    def __init__(self, index, model_media, connection):
        self.index = index
        self.model_media = model_media
        self.connection = connection

        self.name = _("Media Player {}").format(index + 1)
        super().__init__(self.name, connection)

        dropdown = Gtk.ComboBox.new_with_model(self.model_media)
        dropdown.set_entry_text_column(1)
        dropdown.set_id_column(0)
        self.dropdown = dropdown

        dropdown.connect('changed', self.on_mediaplayer_change)
        self.add_control(_("Media"), dropdown)

        renderer = Gtk.CellRendererText()
        dropdown.pack_start(renderer, True)
        dropdown.add_attribute(renderer, "text", 1)

        self.show_all()

    def __repr__(self):
        return '<MediaPlayerPanel {}>'.format(self.panel_name)

    @PalettePanel.event('change:mediaplayer-selected:*')
    def on_mediaplayer_switcher_source_change(self, data):
        if data.index != self.index:
            return

        self.model_changing = True
        if data.source_type == 1:
            self.dropdown.set_active_id(str(data.slot))
        self.model_changing = False

    def on_mediaplayer_change(self, widget, *args):
        if self.model_changing:
            return

        index = widget.get_active_id()
        if index == "":
            return

        index = int(index)
        self.run(MediaplayerSelectCommand(self.index, still=index))
