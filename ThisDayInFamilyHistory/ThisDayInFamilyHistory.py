#!/usr/bin/python
# -*- coding: utf-8 -*-
# ------------------------------------------------------------
#
# This Day In Family History Gramplet
# File: ThisDayInFamilyHistory.py
# Author: Stephen Adams
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
# Initial creation: 2018-05-26
# Version: 1.0.5
#
# Purpose: Generate short reminders of events that have occurred
# within the current family tree.  Allow flexibility to filter
# events between living and deceased tree members and to customize
# the level of detail received.
#
# PEP8 check by http://pep8online.com
# ------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.lib import Person
from gramps.gen.lib import FamilyRelType

#------------------------------------------------------------------------
# Internationalisation
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class ThisDayInFamilyHistory(Gramplet):

    # Unsupported because I can't think of a decent way to express what the
    # event is trying to convey, these events are unsupported.

    __UNSUPPORTED_EVENTS = [
        'Alternate Parentage',
        'Cause Of Death',
        'Education',
        'Medical Information',
        'Number of Marriages',
        'Occupation',
        'Property',
        'Religion',
        'Residence',
        'Will',
        'Year'
        ]
    # Note to translators:  the various Event types listed here are a subset
    # of the gen.lib.eventtypes.py set, where they are already translated.
    # this allows us to use the 'deferred' translation to fill in the GUI


    defaultEventChoices = [
        ('Adopted', True),
        ('Adult Christening', True),
        ('Alternate Marriage', False),
        ('Annulment', False),
        ('Baptism', False),
        ('Bar Mitzvah', False),
        ('Bat Mitzvah', False),
        ('Birth', True),
        ('Blessing', False),
        ('Burial', False),
        ('Census', False),
        ('Christening', False),
        ('Confirmation', False),
        ('Cremation', False),
        ('Death', True),
        ('Degree', False),
        ('Divorce', False),
        ('Divorce Filing', False),
        ('Elected', True),
        ('Emigration', True),
        ('Engagement', False),
        ('First Communion', False),
        ('Graduation', True),
        ('Immigration', True),
        ('Marriage', True),
        ('Marriage Banns', False),
        ('Marriage Contract', False),
        ('Marriage License', False),
        ('Marriage Settlement', False),
        ('Military Service', True),
        ('Naturalization', True),
        ('Nobility Title', True),
        ('Ordination', True),
        ('Probate', False),
        ('Retirement', True),
        ]

    __INIT = _("Database is not open, can't check history right now.")
    __INTRO = _('On %(date)s in family history ...\n')
    __NOEVENT = _('... nothing happened!  Check again tomorrow!')

    # String constants related to the options menu

    __LIVINGONLY = _('Report only living tree members')
    __SHOWEVENT = _('Show these events')
    __SORTBY = _('Sort by ')
    __SORTASC = _('Sort in ascending order?')

    def init(self):
        from gramps.gen.lib.date import Today
        self.set_wrap(False)
        self.deceasedList = []
        self.set_text(self.__INIT)
        self.tDay = Today().get_day()
        self.tMonth = Today().get_month()

        # Would prefer a regional/calendar/translation sensitive
        # version of month string or date string.

        self.tDateStr = ['', _('January'), _('February'), _('March'),
                         _('April'), _('May'), _('June'), _('July'),
                         _('August'), _('September'), _('October'),
                         _('November'), _('December')][self.tMonth] +\
            ' ' + str(self.tDay)

        # These variables must be updated if reordering or adding new
        # options in build_options()
        #
        # Their order also is used in save_update_options() for the
        # persistent gui data list.

        self.__OPT_MAX = 4
        self.__OPT_SORT_DEFAULT = 4
        self.__OPT_LIVING_ONLY = 0
        self.__OPT_SORT_BY = 1
        self.__OPT_SORT_ASC = 2
        self.__OPT_EVENTS = 3

    def db_changed(self):
        self.connect(self.dbstate.db, 'home-person-changed',
                     self.update)
        self.connect(self.dbstate.db, 'person-add', self.update)
        self.connect(self.dbstate.db, 'person-delete', self.update)
        self.connect(self.dbstate.db, 'person-update', self.update)
        self.connect(self.dbstate.db, 'family-add', self.update)
        self.connect(self.dbstate.db, 'family-delete', self.update)
        self.connect(self.dbstate.db, 'family-update', self.update)

    def save_options(self):

        # Save configuration data

        self.__showOnlyLiving = self.opts[self.__OPT_LIVING_ONLY].get_value()\
            == 'Yes'
        s = self.opts[self.__OPT_SORT_BY].get_value()
        self.__sortOrder = (int(s) if s else self.__OPT_SORT_DEFAULT)
        tf_list = self.opts[self.__OPT_EVENTS].get_value().split(',')
        self.__eventsToShow = []
        for (indx, choice) in enumerate(tf_list):
            if choice == 'True':
                self.__eventsToShow.append(self.defaultEventChoices[indx][0])
        self.__sortAscending = self.opts[self.__OPT_SORT_ASC].get_value()\
            == 'Yes'

    def save_update_options(self, obj):

        # Save options to file

        self.save_options()
        self.gui.data = [self.__showOnlyLiving, self.__sortOrder,
                         self.__sortAscending, self.__eventsToShow]
        self.update()

    def on_load(self):

        # Restore previously configured options

        if len(self.gui.data) == self.__OPT_MAX:
            self.__showOnlyLiving = self.gui.data[self.__OPT_LIVING_ONLY]\
                == 'True'
            s = self.gui.data[self.__OPT_SORT_BY]
            self.__sortOrder = (int(s) if s else self.__OPT_SORT_DEFAULT)
            data = self.gui.data[self.__OPT_EVENTS]
            data = eval(data)
            self.__eventsToShow = [evt.title() for evt in data]
            self.__sortAscending = self.gui.data[self.__OPT_SORT_ASC] ==\
                'True'
        else:
            self.__showOnlyLiving = False
            self.__sortOrder = self.__OPT_SORT_DEFAULT
            self.__eventsToShow = [
                'Adopted',
                'Adult Christening',
                'Birth',
                'Death',
                'Elected',
                'Emigration',
                'Graduation',
                'Immigration',
                'Marriage',
                'Military Service',
                'Naturalization',
                'Nobility Title',
                'Ordination',
                'Retirement',
                ]
            self.__sortAscending = True

    def build_options(self):
        from gramps.gen.plug.menu._booleanlist import BooleanListOption
        from gramps.gen.plug.menu._enumeratedlist import EnumeratedListOption

        self.opts = []

        # If the options are re-ordered, the constants declared in init
        # must also be updated to reflect the new ordering.

        items = ''
        op = EnumeratedListOption(self.__LIVINGONLY, items)
        items = op.add_item('', '')
        items = op.add_item(_('Yes'), _('Yes'))
        items = op.add_item(_('No'), _('No'))
        self.opts.append(op)
        if len(self.gui.data) == self.__OPT_MAX:
            if self.__showOnlyLiving:
                self.opts[self.__OPT_LIVING_ONLY].set_value(_('Yes'))
            else:
                self.opts[self.__OPT_LIVING_ONLY].set_value(_('No'))

        # item order matches the order of eventsList as written in getEvents()
        # name, handle, hType, eType, year, grampsID, place, extraInfo

        items = ''
        op = EnumeratedListOption(self.__SORTBY, items)

        # If the values of these items is updated, the self.__OPT_SORT_DEFAULT
        # variable should also be updated to reflect the new numbering

        op.add_item(-1, '')
        op.add_item(0, _('Person Name'))
        op.add_item(3, _('Event Type'))
        op.add_item(4, _('Event Year'))
        op.add_item(5, _('Gramps ID'))
        op.add_item(6, _('Location'))
        self.opts.append(op)
        if len(self.gui.data) == self.__OPT_MAX:
            ops = self.opts[self.__OPT_SORT_BY].get_items()
            for o in ops:
                if o[0] == self.__sortOrder:
                    self.opts[self.__OPT_SORT_BY].set_value(o[0])
                    break

        items = ''
        op = EnumeratedListOption(self.__SORTASC, items)
        items = op.add_item('', '')
        items = op.add_item(_('Yes'), _('Yes'))
        items = op.add_item(_('No'), _('No'))
        self.opts.append(op)
        if len(self.gui.data) == self.__OPT_MAX:
            if self.__sortAscending:
                self.opts[self.__OPT_SORT_ASC].set_value(_('Yes'))
            else:
                self.opts[self.__OPT_SORT_ASC].set_value(_('No'))

        op = BooleanListOption(self.__SHOWEVENT)
        if len(self.gui.data) == self.__OPT_MAX:
            userOptionsAvailable = True
            uo = self.__eventsToShow
        else:
            userOptionsAvailable = False

        for (e, d) in self.defaultEventChoices:
            if userOptionsAvailable:
                if e in uo:
                    op.add_button(_(e), True)
                else:
                    op.add_button(_(e), False)
            else:
                op.add_button(e, d)

        self.opts.append(op)

        list(map(self.add_option, self.opts))

    def main(self):
        """
        Iterate over the people in the database and report events that
        occurred on the current day and month.  Optionally discard results
        of people who are deceased.  A person will be considered deceased
        if they have a death or burial event associated with them.  Optionally
        report only a user defined list of events.  Report may be sorted by
        name, event type, or by year.  Sort may be ascending or descending.

        Events that are not associated with any person or family will not be
        reported.
        """

        self.set_text(self.__INTRO % dict(date=self.tDateStr))
        eventList = self.getEvents('People')
        eventList += self.getEvents('Family')
        self.generateReport(eventList)

    def getEvents(self, eventType):
        from gramps.gen.lib.date import Date

        eventType = eventType.lower()
        ev = {'people': (self.dbstate.db.iter_people, _('Person')),
              'family': (self.dbstate.db.iter_families, _('Family'))}

        eventList = []

        handleType = ev[eventType][1]
        for p in ev[eventType][0]():
            for ref in p.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(ref.ref)

                eDate = event.get_date_object()
                eCalendar = eDate.get_calendar()

                if eCalendar != Date.CAL_GREGORIAN:
                    eDate = eDate.to_calendar(_('gregorian'))

                eDay = eDate.get_day()
                eMonth = eDate.get_month()
                eYear = eDate.get_year()

                eType = event.get_type().xml_str()
                if eType.lower() in ['burial', 'cremation', 'death',
                                     'cause of death', 'will']:
                    if eventType == 'people':
                        gid = p.serialize()[1]
                        self.deceasedList.append(gid)
                    elif eventType == 'family':
                        # TODO perform this check for family "death" events
                        pass

                if eMonth == self.tMonth and eDay == self.tDay:
                    if eType not in self.__UNSUPPORTED_EVENTS \
                            and eType in self.__eventsToShow:
                        if eventType == 'people':
                            name = \
                                p.get_primary_name().get_regular_name()
                            pid = (p.serialize()[1], None)
                            gender = p.get_gender()

                            """
                            TODO: It is possible to figure out the spouse of
                            someone who has an Person marriage event not
                            linked to a family, if the spouse is also listed
                            with the marriage as a Person event.  The
                            simplest way is probably to compare the gramps_id
                            and to emulate the family style reporting.
                            see https://stackoverflow.com/a/16013517/759749
                            for how to count the gramps_ids and discover which
                            have multiplicity > 1
                            """

                            if eType.lower() == 'marriage':
                                extraInfo = int(FamilyRelType.UNKNOWN)
                            else:
                                extraInfo = ''
                        elif eventType == 'family':

                            """
                            I think the most common family events are marriage,
                            residence, or divorce, though I stand ready to be
                            corrected on a number of other family events.

                            For family events other than where the mother and
                            father are the named people, expect unusual output.
                            """

                            fh = p.get_father_handle()
                            if fh is None:
                                fsn = _('Unknown')
                                frn = _('Unknown father/partner')
                                fid = None
                                fg = Person.UNKNOWN
                            else:
                                father = \
                                    self.dbstate.db.get_person_from_handle(fh)
                                fsn = father.get_primary_name().get_name()
                                frn = father.get_primary_name()\
                                    .get_regular_name()
                                fid = father.serialize()[1]
                                fg = father.get_gender()

                            mh = p.get_mother_handle()
                            if mh is None:
                                msn = _('Unknown')
                                mrn = _('Unknown mother/partner')
                                mid = None
                                mg = Person.UNKNOWN
                            else:
                                mother = \
                                    self.dbstate.db.get_person_from_handle(mh)
                                msn = mother.get_primary_name().get_name()
                                mrn = mother.get_primary_name()\
                                    .get_regular_name()
                                mid = mother.serialize()[1]
                                mg = mother.get_gender()

                            pid = (fid, mid)
                            extraInfo = int(p.get_relationship())

                            # if someone has defined a same sex family using
                            # the father/mother fields, try to detect this
                            # and define the gender of the family as the
                            # gender of the participants.  Traditional
                            # marriages will be listed as gender unknown.
                            if fg == mg:
                                gender = fg
                            else:
                                gender = Person.UNKNOWN

                            # attempt to make presentation arbitrary on a
                            # basis other than gender

                            if msn < fsn:
                                name = mrn + _(' and ') + frn
                            else:
                                name = frn + _(' and ') + mrn
                        else:
                            name = _('unknown participant')
                            extraInfo = ''

                        handle = p.handle

                        eID = event.gramps_id

                        ePlace = _('unknown location')
                        evRefs = event.get_referenced_handles()
                        for r in evRefs:

                            """
                            TODO: Improve to include full hierarchical name

                            This is a touch basic, if you've done a good job
                            of defining a place hierarchy then this only
                            prints the most local place value available
                            instead of the entire hierarchical name.
                            """
                            if r[0] == 'Place':
                                ePlace = \
                                    self.dbstate.db.get_place_from_handle(
                                        r[1]).get_name().get_value()

                        eventList.append((
                            name,
                            handle,
                            handleType,
                            eType,
                            eYear,
                            eID,
                            ePlace,
                            extraInfo,
                            pid,
                            gender
                            ))

        if self.__showOnlyLiving:
            for e in list(eventList):
                if e[8][0] in self.deceasedList:
                    if e[8][1] is None or\
                       e[8][1] in self.deceasedList:
                        eventList.remove(e)

        return eventList

    def generateReport(self, events):
        __EVENT_MESSAGE = {}
        __EVENT_MESSAGE['adopted'] = {}
        __EVENT_MESSAGE['adopted']['male'] = \
            _("%(male_name)s was adopted in %(year)s at %(place)s.")
        __EVENT_MESSAGE['adopted']['female'] = \
            _("%(female_name)s was adopted in %(year)s at %(place)s.")
        __EVENT_MESSAGE['adult christening'] = {}
        __EVENT_MESSAGE['adult christening']['male'] = \
            _("%(male_name)s was christened in %(year)s at %(place)s.")
        __EVENT_MESSAGE['adult christening']['female'] = \
            _("%(female_name)s was christened in %(year)s at %(place)s.")
        __EVENT_MESSAGE['alternate marriage'] = {}
        __EVENT_MESSAGE['alternate marriage']['male'] = \
            _("%(male_name)s was married in %(year)s at %(place)s.")
        __EVENT_MESSAGE['alternate marriage']['female'] = \
            _("%(female_name)s was married in %(year)s at %(place)s.")
        __EVENT_MESSAGE['annulment'] = {}
        __EVENT_MESSAGE['annulment']['male'] = \
            _("%(male_name)s received an annulment in %(year)s at %(place)s.")
        __EVENT_MESSAGE['annulment']['female'] = \
            _("%(female_name)s received an annulment in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['baptism'] = {}
        __EVENT_MESSAGE['baptism']['male'] = \
            _("%(male_name)s was baptized in %(year)s at %(place)s.")
        __EVENT_MESSAGE['baptism']['female'] = \
            _("%(female_name)s was baptized in %(year)s at %(place)s.")
        __EVENT_MESSAGE['bar mitzvah'] = {}
        __EVENT_MESSAGE['bar mitzvah']['male'] = \
            _("%(male_name)s became a bar mitzvah in %(year)s at %(place)s.")
        __EVENT_MESSAGE['bar mitzvah']['female'] = \
            _("%(female_name)s became a bar mitzvah in %(year)s at %(place)s.")
        __EVENT_MESSAGE['bat mitzvah'] = {}
        __EVENT_MESSAGE['bat mitzvah']['male'] = \
            _("%(male_name)s became a bat mitzvah in %(year)s at %(place)s.")
        __EVENT_MESSAGE['bat mitzvah']['female'] = \
            _("%(female_name)s became a bat mitzvah in %(year)s at %(place)s.")
        __EVENT_MESSAGE['birth'] = {}
        __EVENT_MESSAGE['birth']['male'] = \
            _("%(male_name)s was born in %(year)s at %(place)s.")
        __EVENT_MESSAGE['birth']['female'] = \
            _("%(female_name)s was born in %(year)s at %(place)s.")
        __EVENT_MESSAGE['blessing'] = {}
        __EVENT_MESSAGE['blessing']['male'] = \
            _("%(male_name)s was blessed in %(year)s at %(place)s.")
        __EVENT_MESSAGE['blessing']['female'] = \
            _("%(female_name)s was blessed in %(year)s at %(place)s.")
        __EVENT_MESSAGE['burial'] = {}
        __EVENT_MESSAGE['burial']['male'] = \
            _("%(male_name)s was buried in %(year)s at %(place)s.")
        __EVENT_MESSAGE['burial']['female'] = \
            _("%(female_name)s was buried in %(year)s at %(place)s.")
        __EVENT_MESSAGE['census'] = {}
        __EVENT_MESSAGE['census']['male'] = \
            _("%(male_name)s participated in a census in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['census']['female'] = \
            _("%(female_name)s participated in a census in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['christening'] = {}
        __EVENT_MESSAGE['christening']['male'] = \
            _("%(male_name)s was christened in %(year)s at %(place)s.")
        __EVENT_MESSAGE['christening']['female'] = \
            _("%(female_name)s was christened in %(year)s at %(place)s.")
        __EVENT_MESSAGE['confirmation'] = {}
        __EVENT_MESSAGE['confirmation']['male'] = \
            _("%(male_name)s was confirmed in %(year)s at %(place)s.")
        __EVENT_MESSAGE['confirmation']['female'] = \
            _("%(female_name)s was confirmed in %(year)s at %(place)s.")
        __EVENT_MESSAGE['cremation'] = {}
        __EVENT_MESSAGE['cremation']['male'] = \
            _("%(male_name)s was cremated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['cremation']['female'] = \
            _("%(female_name)s was cremated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['death'] = {}
        __EVENT_MESSAGE['death']['male'] = \
            _("%(male_name)s died in %(year)s at %(place)s.")
        __EVENT_MESSAGE['death']['female'] = \
            _("%(female_name)s died in %(year)s at %(place)s.")
        __EVENT_MESSAGE['degree'] = {}
        __EVENT_MESSAGE['degree']['male'] = \
            _("%(male_name)s was awarded a degree in %(year)s at %(place)s.")
        __EVENT_MESSAGE['degree']['female'] = \
            _("%(female_name)s was awarded a degree in %(year)s at %(place)s.")
        __EVENT_MESSAGE['divorce'] = {}
        __EVENT_MESSAGE['divorce']['male'] = \
            _("%(male_name)s was granted a divorce in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['divorce']['female'] = \
            _("%(female_name)s was granted a divorce in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['divorce filing'] = {}
        __EVENT_MESSAGE['divorce filing']['male'] = \
            _("%(male_name)s filed for divorce in %(year)s at %(place)s.")
        __EVENT_MESSAGE['divorce filing']['female'] = \
            _("%(female_name)s filed for divorce in %(year)s at %(place)s.")
        __EVENT_MESSAGE['elected'] = {}
        __EVENT_MESSAGE['elected']['male'] = \
            _("%(male_name)s was elected in %(year)s at %(place)s.")
        __EVENT_MESSAGE['elected']['female'] = \
            _("%(female_name)s was elected in %(year)s at %(place)s.")
        __EVENT_MESSAGE['emigration'] = {}
        __EVENT_MESSAGE['emigration']['male'] = \
            _("%(male_name)s emigrated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['emigration']['female'] = \
            _("%(female_name)s emigrated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['engagement'] = {}
        __EVENT_MESSAGE['engagement']['male'] = \
            _("%(male_name)s became engaged in %(year)s at %(place)s.")
        __EVENT_MESSAGE['engagement']['female'] = \
            _("%(female_name)s became engaged in %(year)s at %(place)s.")
        __EVENT_MESSAGE['first communion'] = {}
        __EVENT_MESSAGE['first communion']['male'] = \
            _("%(male_name)s received first communion in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['first communion']['female'] = \
            _("%(female_name)s received first communion in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['graduation'] = {}
        __EVENT_MESSAGE['graduation']['male'] = \
            _("%(male_name)s graduated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['graduation']['female'] = \
            _("%(female_name)s graduated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['immigration'] = {}
        __EVENT_MESSAGE['immigration']['male'] = \
            _("%(male_name)s immigrated in %(year)s at %(place)s.")
        __EVENT_MESSAGE['immigration']['female'] = \
            _("%(female_name)s immigrated in %(year)s at %(place)s.")

        # attempt to distinguish between the marriage event types

        __EVENT_MESSAGE['marriage' + str(FamilyRelType.MARRIED)] = {}
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.MARRIED)]['male'] = \
            _("%(male_name)s got married in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.MARRIED)]['female'] = \
            _("%(female_name)s got married in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.UNMARRIED)] = {}
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.UNMARRIED)]['male'] =\
            _("%(male_name)s joined as a family in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.UNMARRIED)]['female'] =\
            _("%(female_name)s joined as a family in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.CIVIL_UNION)] = {}
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.CIVIL_UNION)]['male'] =\
            _("%(male_name)s entered a civil union in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.CIVIL_UNION)]['female']\
            = _("%(female_name)s entered a civil union in %(year)s at " +
                "%(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.UNKNOWN)] = {}
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.UNKNOWN)]['male'] = \
            _("%(male_name)s joined as a family in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.UNKNOWN)]['female'] = \
            _("%(female_name)s joined as a family in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.CUSTOM)] = {}
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.CUSTOM)]['male'] = \
            _("%(male_name)s had a custom marriage in %(year)s at %(place)s.")
        __EVENT_MESSAGE['marriage' + str(FamilyRelType.CUSTOM)]['female'] = \
            _("%(female_name)s had a custom marriage in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage banns'] = {}
        __EVENT_MESSAGE['marriage banns']['male'] = \
            _("%(male_name)s announced a marriage banns in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage banns']['female'] = \
            _("%(female_name)s announced a marriage banns in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage contract'] = {}
        __EVENT_MESSAGE['marriage contract']['male'] = \
            _("%(male_name)s entered a marriage contract in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage contract']['female'] = \
            _("%(female_name)s entered a marriage contract in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage license'] = {}
        __EVENT_MESSAGE['marriage license']['male'] = \
            _("%(male_name)s obtained a marriage license in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage license']['female'] = \
            _("%(female_name)s obtained a marriage license in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage settlement'] = {}
        __EVENT_MESSAGE['marriage settlement']['male'] = \
            _("%(male_name)s obtained a marriage settlement in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['marriage settlement']['female'] = \
            _("%(female_name)s obtained a marriage settlement in %(year)s " +
              "at %(place)s.")
        __EVENT_MESSAGE['military service'] = {}
        __EVENT_MESSAGE['military service']['male'] = \
            _("%(male_name)s entered military service in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['military service']['female'] = \
            _("%(female_name)s entered military service in %(year)s at " +
              "%(place)s.")
        __EVENT_MESSAGE['naturalization'] = {}
        __EVENT_MESSAGE['naturalization']['male'] = \
            _("%(male_name)s became naturalized in %(year)s at %(place)s.")
        __EVENT_MESSAGE['naturalization']['female'] = \
            _("%(female_name)s became naturalized in %(year)s at %(place)s.")
        __EVENT_MESSAGE['nobility title'] = {}
        __EVENT_MESSAGE['nobility title']['male'] = \
            _("%(male_name)s had a title bestowed in %(year)s at %(place)s.")
        __EVENT_MESSAGE['nobility title']['female'] = \
            _("%(female_name)s had a title bestowed in %(year)s at %(place)s.")
        __EVENT_MESSAGE['ordination'] = {}
        __EVENT_MESSAGE['ordination']['male'] = \
            _("%(male_name)s was ordained in %(year)s at %(place)s.")
        __EVENT_MESSAGE['ordination']['female'] = \
            _("%(female_name)s was ordained in %(year)s at %(place)s.")
        __EVENT_MESSAGE['probate'] = {}
        __EVENT_MESSAGE['probate']['male'] = \
            _("%(male_name)s was granted probate in %(year)s at %(place)s.")
        __EVENT_MESSAGE['probate']['female'] = \
            _("%(female_name)s was granted probate in %(year)s at %(place)s.")
        __EVENT_MESSAGE['retirement'] = {}
        __EVENT_MESSAGE['retirement']['male'] = \
            _("%(male_name)s retired in %(year)s at %(place)s.")
        __EVENT_MESSAGE['retirement']['female'] = \
            _("%(female_name)s retired in %(year)s at %(place)s.")

        if len(events) == 0:
            message = '\t' + self.__NOEVENT + '\n'
            self.append_text(message)
        else:
            if self.__sortOrder != -1:
                events.sort(key=lambda x: x[self.__sortOrder],
                            reverse=not(self.__sortAscending))
            for (
                    name,
                    handle,
                    hType,
                    eType,
                    year,
                    grampsID,
                    place,
                    extraInfo,
                    pid,
                    gender
                    ) in events:
                eStr = eType.lower()

                # Marriage messages are stored in marriageN where N is the
                # integer relationship type

                if eStr == 'marriage':
                    eStr = eStr + str(extraInfo)

                if year == 0:
                    year = _("unknown")

                # If gender is unknown the messages will default to
                # the male versions.  This is arbitrary and can be redefined.
                #
                # I don't think it makes any difference in English but I'm
                # uncertain if it will pose a translation issue.

                if gender == Person.FEMALE:
                    msg = __EVENT_MESSAGE[eStr]['female']
                    prefix = msg[0:msg.find('%(female_name)')] \
                        % dict(female_name='', year=year, place=place)
                    suffix = msg[msg.find('%(female_name)'):-1] \
                        % dict(female_name='', year=year, place=place)
                else:
                    msg = __EVENT_MESSAGE[eStr]['male']
                    prefix = msg[0:msg.find('%(male_name)')] \
                        % dict(male_name='', year=year, place=place)
                    suffix = msg[msg.find('%(male_name)'):-1] \
                        % dict(male_name='', year=year, place=place)

                self.append_text('\t... ' + prefix)
                self.link(name, hType, handle)
                self.append_text(suffix + '\n')
