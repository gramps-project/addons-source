"""Translate addon strings from the directory containing its locale catalog."""

from gettext import NullTranslations

try:
    from gramps.gen.const import GRAMPS_LOCALE
except ModuleNotFoundError as error:
    if error.name != "gramps":
        raise
    # Pure model and drawing code can run outside Gramps.
    translator = NullTranslations()
else:
    translator = GRAMPS_LOCALE.get_addon_translator(__file__)

_ = translator.gettext
