#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2026       Douglas S. Blank <doug.blank@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
from abc import abstractmethod

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gramps.gen.plug import Gramplet, BasePluginManager
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

from wordcloudwidget import WordCloudWidget
from slideroption import SliderOption, GuiSliderOption

# ------------------------------------------------------------------------
#
# Constants
#
# ------------------------------------------------------------------------

_YIELD_INTERVAL = 350

_DEFAULT_COLOR_LOW = "#99ccff"  # (0.6, 0.8, 1.0)
_DEFAULT_COLOR_HIGH = "#003399"  # (0.0, 0.2, 0.6)
_DEFAULT_COLOR_HOVER = "#cc0000"  # (0.8, 0.0, 0.0)
_DEFAULT_QUALITY = 0.0


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


# ------------------------------------------------------------------------
#
# CloudGramplet class
#
# ------------------------------------------------------------------------
class CloudGramplet(Gramplet):
    """A gramplet that displays a word cloud where word size reflects frequency."""

    def init(self):
        pmgr = BasePluginManager.get_instance()
        pmgr.register_option(SliderOption, GuiSliderOption)

        self.top_size = 150
        self.color_low = _DEFAULT_COLOR_LOW
        self.color_high = _DEFAULT_COLOR_HIGH
        self.color_hover = _DEFAULT_COLOR_HOVER
        self.quality = _DEFAULT_QUALITY
        self.filter_missing = True
        self.value_name = "default_value_name"
        self.preference_no_value = ""
        self._values_linked_data = {}

        self.word_cloud = WordCloudWidget(
            [],
            on_click=self._on_word_clicked,
            color_low=_hex_to_rgb(self.color_low),
            color_high=_hex_to_rgb(self.color_high),
            color_hover=_hex_to_rgb(self.color_hover),
            quality=self.quality,
        )
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.word_cloud)
        self.word_cloud.show()

    def set_value_name(self, value_name):
        """What the cloud displays. For a name cloud, `value_name` is "name"."""
        self.value_name = _(value_name)

    def set_preference_no_value(self, preference_no_value):
        """Config key holding the default text to show when there are no values."""
        self.preference_no_value = preference_no_value

    def _on_word_clicked(self, word):
        linked_data = self._values_linked_data.get(word)
        if linked_data is not None:
            self.on_item_clicked(word, linked_data)

    def on_item_clicked(self, word, linked_data):
        """Called when the user clicks a word. Subclasses override to navigate."""

    @abstractmethod
    def db_changed(self):
        """Connect the cloud with the database.
        See the example in surnamewordcloudgramplet.py.
        """

    @abstractmethod
    def get_items(self) -> list:
        """How to access data in the cloud. Must return an iterator of
        (value, linked_data, count) triples.
        See the example in surnamewordcloudgramplet.py.
        """

    def on_load(self):
        data = self.gui.data
        if len(data) >= 1:
            self.top_size = int(data[0])
        if len(data) >= 5:
            self.color_low = data[1]
            self.color_high = data[2]
            self.color_hover = data[3]
            self.quality = float(data[4])
        if len(data) >= 6:
            self.filter_missing = bool(int(data[5]))
        self.word_cloud.set_colors(
            _hex_to_rgb(self.color_low),
            _hex_to_rgb(self.color_high),
            _hex_to_rgb(self.color_hover),
        )
        self.word_cloud.set_quality(self.quality)

    def _read_options(self):
        self.top_size = int(
            self.get_option(_("Number of %s") % self.value_name).get_value()
        )
        self.color_low = self.get_option(_("Color (low)")).get_value()
        self.color_high = self.get_option(_("Color (high)")).get_value()
        self.color_hover = self.get_option(_("Hover color")).get_value()
        self.quality = float(self.get_option(_("Layout quality")).get_value())
        self.filter_missing = self.get_option(
            _("Filter missing/unknown words")
        ).get_value()

    def save_update_options(self, widget=None):
        self._read_options()
        self.gui.data = [
            self.top_size,
            self.color_low,
            self.color_high,
            self.color_hover,
            self.quality,
            int(self.filter_missing),
        ]
        self.update()

    def save_options(self):
        self._read_options()

    def main(self):
        yield True

        yield_counter = 0

        values_counts = {}
        values_linked_data = {}

        for value, linked_data, count in self.get_items():
            if value not in values_counts:
                values_linked_data[value] = linked_data
                values_counts[value] = count
            else:
                values_counts[value] += count

            yield_counter += 1
            if not yield_counter % _YIELD_INTERVAL:
                yield True

        # count order: [(value, count), ...]
        sorted_values = sorted(
            list(values_counts.items()), key=(lambda k: k[1]), reverse=True
        )

        # limit to top_size distinct values
        selected_values = sorted_values[: self.top_size]

        # Build words list for the widget, resolving empty-value display text
        self._values_linked_data = {}
        words = []
        for value, count in selected_values:
            if len(value) == 0:
                if self.preference_no_value != "":
                    display = config.get(self.preference_no_value)
                else:
                    display = _("[Missing %s]") % self.value_name
            else:
                display = value
            self._values_linked_data[display] = values_linked_data.get(value)
            words.append((display, count))

        self.word_cloud.configure(
            quality=self.quality,
            color_low=_hex_to_rgb(self.color_low),
            color_high=_hex_to_rgb(self.color_high),
            color_hover=_hex_to_rgb(self.color_hover),
        )
        self.word_cloud.set_words(words)

    def build_options(self):
        from gramps.gen.plug.menu import BooleanOption, ColorOption

        self.add_option(
            SliderOption(_("Number of %s") % self.value_name, self.top_size, 1, 150)
        )
        self.add_option(ColorOption(_("Color (low)"), self.color_low))
        self.add_option(ColorOption(_("Color (high)"), self.color_high))
        self.add_option(ColorOption(_("Hover color"), self.color_hover))
        self.add_option(SliderOption(_("Layout quality"), self.quality, 0.0, 1.0, 0.1))
        self.add_option(
            BooleanOption(_("Filter missing/unknown words"), self.filter_missing)
        )
