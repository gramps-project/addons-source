# -*- coding: utf-8 -*-

"Prepare for Familio export"

#-------------------------------------------------
#
# python modules
#
#-------------------------------------------------
import re
import uuid

#-------------------------------------------------
#
# GRAMPS modules
#
#-------------------------------------------------
from gramps.gui.plug import MenuToolOptions, PluginWindows
from gramps.gen.plug.menu import EnumeratedListOption, StringOption, BooleanOption
from gramps.gen.lib import (
    Event, EventType, EventRef, EventRoleType, FamilyRelType,
    AttributeType, Attribute,
)
from gramps.gen.db import DbTxn

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


#-------------------------------------------------
#
# Macro processor (from SetAttributeTool, trimmed to what's used here)
#
#-------------------------------------------------
class MacroProcessor:
    """Processes text${MACRO}text templates.

    Supported macros:
        ${GUID}   - a new random GUID (uppercase)
        ${NAME}   - the person's display name

    Note: the experimental ${FAMILIO_UID} macro (matching people in an
    existing Familio export by name+years) has been removed as unreliable -
    in testing it produced no useful matches and Familio duplicated the
    records anyway.
    """

    def generate_value(self, template, obj=None, db=None):
        def _replacer(match):
            macro = match.group(1)

            if macro == "GUID":
                return str(uuid.uuid4()).upper()

            elif macro == "NAME" and obj:
                try:
                    return str(obj.get_primary_name().get_regular_name())
                except Exception:
                    return "UNKNOWN"

            return match.group(0)

        return re.sub(r"\$\{([^}]+)\}", _replacer, template)


#-------------------------------------------------
#
# Options
#
#-------------------------------------------------
class FamilioPrepOptions(MenuToolOptions):
    """Options for the combined Familio export preparation tool"""

    def __init__(self, name, person_id=None, dbstate=None):
        MenuToolOptions.__init__(self, name, person_id, dbstate)

    def add_menu_options(self, menu):

        # ---------- _UID attribute ----------
        cat_uid = _("_UID attribute")

        add_uid = BooleanOption(_("Add _UID attribute to persons who don't have one"), True)
        add_uid.set_help(_("Existing _UID attributes are never modified or overwritten"))
        menu.add_option(cat_uid, "add_uid", add_uid)

        uid_attr_type = StringOption(_("Attribute type"), "_UID")
        uid_attr_type.set_help(_("Name of the attribute type to add"))
        menu.add_option(cat_uid, "uid_attr_type", uid_attr_type)

        uid_value_template = StringOption(_("Value template"), "${GUID}")
        uid_value_template.set_help(_(
            "Supported macros: ${GUID} - a new random GUID, "
            "${NAME} - the person's name"
        ))
        menu.add_option(cat_uid, "uid_value_template", uid_value_template)

        # ---------- Marriage events ----------
        cat_marr = _("Marriage events")

        add_marriages = BooleanOption(_("Add missing 'Marriage' events to families"), True)
        add_marriages.set_help(_(
            "Gramps only writes the required MARR tags on GEDCOM export if "
            "the family has an explicit 'Marriage' event"
        ))
        menu.add_option(cat_marr, "add_marriages", add_marriages)

        fallback_type = EnumeratedListOption(_("Fallback for unknown status (Unknown)"), 0)
        fallback_type.add_item(0, "marriage", _("marriage (legally married)"))
        fallback_type.add_item(1, "not married", _("not married (unmarried)"))
        fallback_type.add_item(2, "civil", _("civil (civil union)"))
        fallback_type.add_item(3, "unknown", _("unknown (unknown)"))
        fallback_type.set_help(_(
            "This value is written to MARR.TYPE when the family's "
            "relationship status in Gramps is 'Unknown'"
        ))
        menu.add_option(cat_marr, "fallback_type", fallback_type)


#-------------------------------------------------
#
# Tool window
#
#-------------------------------------------------
class FamilioPrepTool(PluginWindows.ToolManagedWindowBatch):

    def get_title(self):
        return _("Prepare for Familio export")

    def initial_frame(self):
        return _("_UID attribute")

    def run(self):
        opt = self.options.menu

        add_uid = opt.get_option_by_name('add_uid').get_value()
        uid_attr_type_str = opt.get_option_by_name('uid_attr_type').get_value().strip()
        uid_value_template = opt.get_option_by_name('uid_value_template').get_value()

        add_marriages = opt.get_option_by_name('add_marriages').get_value()
        fallback_idx = opt.get_option_by_name('fallback_type').get_value()
        index_to_str = {0: "marriage", 1: "not married", 2: "civil", 3: "unknown"}
        fallback_str = index_to_str.get(fallback_idx, "marriage")

        self.add_results_frame(_("Results"))

        # Remember the currently active person so we can restore the
        # selection after request_rebuild() (otherwise Gramps resets it
        # to the first person in the list)
        active_person_handle = None
        try:
            active_person_handle = self.uistate.get_active('Person')
        except Exception:
            pass

        self.db.disable_signals()

        uid_count = 0
        marriage_count = 0

        with DbTxn(_("Prepare Familio export"), self.db, batch=True) as self.trans:

            # ========== 1. _UID attribute ==========
            if add_uid:
                if not uid_attr_type_str:
                    self.results_write(_("No attribute type set for _UID, skipping this step.\n"))
                else:
                    macro_processor = MacroProcessor()
                    specified_type = AttributeType()
                    specified_type.set(uid_attr_type_str)

                    people_handles = list(self.db.iter_person_handles())
                    num_people = len(people_handles)

                    self.results_write(_("Adding attribute '%s'...\n") % uid_attr_type_str)
                    self.progress.set_pass(_('Processing people...'), num_people)

                    for person_handle in people_handles:
                        self.progress.step()
                        person = self.db.get_person_from_handle(person_handle)
                        if not person:
                            continue

                        already_has = any(
                            attr.get_type() == specified_type
                            for attr in person.get_attribute_list()
                        )
                        if already_has:
                            continue

                        new_value = macro_processor.generate_value(
                            uid_value_template, person, self.db
                        )

                        attr = Attribute()
                        attr.set_type(specified_type)
                        attr.set_value(new_value)
                        person.add_attribute(attr)

                        if attr.get_type().is_custom() and str(attr.get_type()):
                            self.db.individual_attributes.update([str(attr.get_type())])

                        self.db.commit_person(person, self.trans)
                        uid_count += 1

                    self.results_write(_("Added '%s' attributes: %d\n\n") %
                                        (uid_attr_type_str, uid_count))

            # ========== 2. Marriage events ==========
            if add_marriages:
                gedcom_mapping = {
                    FamilyRelType.MARRIED: "marriage",
                    FamilyRelType.UNMARRIED: "not married",
                    FamilyRelType.CIVIL_UNION: "civil",
                    FamilyRelType.UNKNOWN: fallback_str,
                }

                family_handles = list(self.db.iter_family_handles())
                num_families = len(family_handles)

                self.results_write(_("Adding 'Marriage' events...\n"))
                self.progress.set_pass(_('Processing families...'), num_families)

                for family_handle in family_handles:
                    self.progress.step()
                    family = self.db.get_family_from_handle(family_handle)
                    if not family:
                        continue

                    has_marriage = False
                    for event_ref in family.get_event_ref_list():
                        event = self.db.get_event_from_handle(event_ref.ref)
                        if event and int(event.get_type()) == EventType.MARRIAGE:
                            has_marriage = True
                            break
                    if has_marriage:
                        continue

                    new_event = Event()
                    new_event.set_type(EventType.MARRIAGE)

                    rel_type = int(family.get_relationship())
                    if rel_type == FamilyRelType.CUSTOM:
                        type_str = family.get_relationship_string().lower()
                    else:
                        type_str = gedcom_mapping.get(rel_type, fallback_str)

                    new_event.set_description(type_str)
                    self.db.add_event(new_event, self.trans)

                    event_ref = EventRef()
                    event_ref.set_reference_handle(new_event.handle)
                    event_ref.set_role(EventRoleType.FAMILY)
                    family.add_event_ref(event_ref)

                    self.db.commit_family(family, self.trans)
                    marriage_count += 1

                self.results_write(_("Added new 'Marriage' events: %d\n") % marriage_count)

        self.db.enable_signals()
        self.db.request_rebuild()

        # Restore the same active person that was selected before running
        if active_person_handle:
            try:
                self.uistate.set_active(active_person_handle, 'Person')
            except Exception:
                pass

        self.results_write(
            _("\nDone. _UID added: %d, marriage events added: %d\n") %
            (uid_count, marriage_count)
        )
