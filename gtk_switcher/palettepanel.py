# Copyright 2025, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only
import glob
import json
import os
import uuid

from gi.repository import Gtk, GObject, Gdk, GLib, Gio
import pyatem.field as fieldmodule
from gtk_switcher.adjustmententry import AdjustmentEntry
from gtk_switcher.presetwindow import PresetWindow

from pyatem.protocol import AtemProtocol

_palette_field = {}


class EventGate:
    def __init__(self, reference):
        self.ref = reference

    def __enter__(self):
        self.ref.model_changing = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ref.model_changing = False


class PalettePanel(Gtk.Overlay):
    __gtype_name__ = 'PalettePanel'

    def __init__(self, panel_name, connection: AtemProtocol, preset_domain=None, preset_override=None,
                 preset_fields=None):
        self.panel_name = panel_name
        self.connection = connection
        self.window = None
        self.application = None

        self.model_changing = False
        self.model = EventGate(self)
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
        self.preset_override = preset_override
        if preset_domain is not None:
            self.preset_fields = preset_fields
            self.preset_domain = preset_domain
            self.preset_button = Gtk.MenuButton()
            self.preset_button.set_valign(Gtk.Align.START)
            self.preset_button.set_halign(Gtk.Align.END)
            self.preset_button.set_size_request(28, 28)
            self.set_class(self.preset_button, 'flat', True)
            self.set_class(self.preset_button, 'preset', True)
            self.add_overlay(self.preset_button)

            hamburger = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.BUTTON)
            self.preset_button.set_image(hamburger)
            self.preset_button.set_name(preset_domain)

            # Create `panel` action group
            self._action_group = str(uuid.uuid4())
            agp = Gio.SimpleActionGroup()
            self.insert_action_group(self._action_group, agp)

            # Create actions for the panel
            action = Gio.SimpleAction.new("savepreset", None)
            action.connect("activate", self._on_save_preset)
            agp.add_action(action)

            action = Gio.SimpleAction.new("recallpreset", GLib.VariantType.new("(ss)"))
            action.connect("activate", self._on_recall_preset)
            agp.add_action(action)

            self._preset_menu = Gio.Menu()
            self._presets = {}
            self._preset_submenu = Gio.Menu()
            self._preset_menu.append('Save preset', f"{self._action_group}.savepreset")
            self._preset_menu.append_section('Presets', self._preset_submenu)
            self._load_presets()
            self.preset_button.set_menu_model(self._preset_menu)

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

    def _load_presets(self):
        xdg_config_home = os.path.expanduser(os.environ.get('XDG_CONFIG_HOME', '~/.config'))
        presetdir = os.path.join(xdg_config_home, 'openswitcher', 'presets', self.preset_domain)
        loaded = {}
        for existing in glob.glob(os.path.join(presetdir, '*.json')):
            preset_code = os.path.basename(existing).replace('.json', '')
            with open(existing, 'r') as handle:
                data = json.load(handle)
                self._presets[preset_code] = data['fields']
                loaded[data['name']] = preset_code
        ordered = list(sorted(loaded.keys()))
        for preset_name in ordered:
            preset_code = loaded[preset_name]
            mi = Gio.MenuItem.new(preset_name, f"{self._action_group}.recallpreset")
            mi.set_detailed_action(f"{self._action_group}.recallpreset(('{self.preset_domain}', '{preset_code}'))")
            self._preset_submenu.append_item(mi)

    def _on_recall_preset(self, action, parameters):
        parameters = tuple(parameters)
        presetcode = parameters[1]
        preset = self._presets[presetcode]
        cmds = []

        for field in preset:
            classname = field['_name'].title().replace('-', '') + "Field"
            if hasattr(fieldmodule, classname):
                fieldclass = getattr(fieldmodule, classname)
                cmds.extend(fieldclass.restore(field, instance_override=self.preset_override))
            else:
                self.log_aw.error(f"Unknown field in preset: {field['_name']}")
                return
        self.connection.send_commands(cmds)

    def _on_save_preset(self, action, parameters):
        contents = []
        for field in self.preset_fields:
            ms = self.connection.mixerstate[field]
            if isinstance(ms, dict):
                for key in ms:
                    if self.preset_override is not None and len(self.preset_override) == 1:
                        if key != int(self.preset_override[0]):
                            continue
                    sf = ms[key]
                    s = sf.serialize()
                    if s is not None:
                        s['_name'] = field
                        contents.append(s)

        dialog = PresetWindow(self.window, self.application)
        response = dialog.run()

        if response == Gtk.ResponseType.CANCEL:
            return

        preset_name = dialog.get_name()
        dialog.destroy()

        code = str(uuid.uuid4())
        self._presets[code] = contents
        mi = Gio.MenuItem.new(preset_name, f"{self._action_group}.recallpreset")
        mi.set_detailed_action(f"{self._action_group}.recallpreset(('{self.preset_domain}', '{code}'))")
        self._preset_submenu.append_item(mi)

        xdg_config_home = os.path.expanduser(os.environ.get('XDG_CONFIG_HOME', '~/.config'))
        presetdir = os.path.join(xdg_config_home, 'openswitcher', 'presets', self.preset_domain)
        os.makedirs(presetdir, exist_ok=True)
        presetfile = os.path.join(presetdir, f'{code}.json')
        with open(presetfile, 'w') as handle:
            json.dump({
                'name': preset_name,
                'fields': contents,
            }, handle)

    def set_class(self, widget, classname, state):
        if state:
            widget.get_style_context().add_class(classname)
        else:
            widget.get_style_context().remove_class(classname)

    def add_separator(self):
        widget = Gtk.Separator()
        self.grid.attach(widget, 0, self._row, 2, 1)
        self._row += 1

    def add_control(self, name, widget=None, widget2=None):
        label = Gtk.Label(name, xalign=1.0)
        label.get_style_context().add_class('dim-label')
        self.grid.attach(label, 0, self._row, 1, 1)
        width = 2
        if widget2 is not None:
            width = 1
        if widget is not None:
            self.grid.attach(widget, 1, self._row, width, 1)
        if widget2 is not None:
            self.grid.attach(widget2, 2, self._row, width, 1)
        self._row += 1

    def add_control_dropdown(self, name, model, handler=None):
        widget = Gtk.ComboBox.new_with_model(model)
        widget.set_entry_text_column(1)
        widget.set_id_column(0)
        self.add_control(name, widget)
        renderer = Gtk.CellRendererText()
        widget.pack_start(renderer, True)
        widget.add_attribute(renderer, "text", 1)
        if handler is not None:
            def wrapper(*args, **kwargs):
                if self.model_changing:
                    return
                handler(*args, **kwargs)

            widget.connect('changed', wrapper)
        return widget

    def add_control_toggle(self, name, label, handler=None):
        # lbl = Gtk.Label(label=label)
        widget = Gtk.Button(label)
        # widget.add(lbl)
        widget.set_size_request(48, 48)
        widget.get_style_context().add_class('bmdbtn')
        self.add_control(name, widget)
        if handler is not None:
            widget.connect('clicked', handler)
        return widget

    def add_control_slider(self, name, adjustment: Gtk.Adjustment, handler=None):
        widget = Gtk.Scale()
        widget.set_draw_value(False)
        widget.set_adjustment(adjustment)
        widget.connect('button-press-event', self._on_slider_held)
        widget.connect('button-release-event', self._on_slider_released)
        self.add_control(name, widget)
        if handler is not None:
            def wrapper(*args, **kwargs):
                if not self.slider_held:
                    return
                handler(*args, **kwargs)

            adjustment.connect('value-changed', wrapper)

        return widget

    def add_control_slider_box(self, name, adjustment: Gtk.Adjustment, handler=None, handler_args=None,
                               display_min=None,
                               display_max=None):
        widget = Gtk.Scale()
        widget.set_draw_value(False)
        widget.set_adjustment(adjustment)
        widget.connect('button-press-event', self._on_slider_held)
        widget.connect('button-release-event', self._on_slider_released)
        widget.set_hexpand(True)

        if display_min is None:
            display_min = adjustment.get_lower()
        if display_max is None:
            display_max = adjustment.get_upper()

        box = AdjustmentEntry(adjustment, display_min, display_max)
        box.set_size_request(24, 24)
        box.set_hexpand(False)
        box.set_halign(Gtk.Align.END)
        box.set_width_chars(6)

        self.add_control(name, widget, box)
        if handler_args is None:
            handler_args = []
        if handler is not None:
            def wrapper(*args, **kwargs):
                if not self.slider_held:
                    return
                handler(*args, *handler_args, **kwargs)

            adjustment.connect('value-changed', wrapper)

        return widget

    def run(self, cmd):
        """ Dispatch CMD to active connection """
        self.connection.send_commands([cmd])

    def _on_slider_held(self, *args):
        self.slider_held = True

    def _on_slider_released(self, *args):
        self.slider_held = False

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
