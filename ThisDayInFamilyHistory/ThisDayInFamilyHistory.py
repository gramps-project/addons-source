#------------------------------------------------------------
#
# This Day In Family History Gramplet
# File: ThisDayInFamilyHistory.py
# Author: Stephen Adams
# Initial creation: 2018-05-26
# Version: 0.0.1
#
# Purpose: Generate short reminders of events that have occurred
# within the current family tree.  Allow flexibility to filter
# events between living and deceased tree members and to customize
# the level of detail received.
#
#------------------------------------------------------------
from gramps.gen.plug import Gramplet
from string import Template
from gramps.gen.lib import FamilyRelType

class ThisDayInFamilyHistory( Gramplet ):

    # despite the highly repetitive strings chosen here I decided not to
    # generate the string through concatenation both for translation
    # considerations future customization opportunity
    
    # instead each string is built up of a message prefix, the name
    # and a message suffix in the format:
    # __EVENT_MESSAGE[ event.get_type().string.lower() ] = ( Template( Prefix_String ), Template( Suffix_String ) )
    #
    #     Prefix "", name "John Doe", suffix "was baptized in $year"
    #     i.e. John Doe was baptized in 1752 (English)
    #
    # this was chosen to accomodate translation challenges:
    #     Prefix "Baisteadh", name "John Doe", suffix "i $year"
    #     i.e. Baisteadh John Doe i 1752 (Irish)
    #
    # both prefix and suffix will insert $year correctly

    __EVENT_MESSAGE = {}
    __EVENT_MESSAGE[ "adopted" ] = ( Template( "" ), Template( " was adopted in $year at $place" ) )
    __EVENT_MESSAGE[ "adult christening" ] = ( Template( "" ), Template( " was christened in $year at $place" ) )
    __EVENT_MESSAGE[ "alternate marriage" ] = ( Template( "" ), Template( " was married in $year at $place" ) )
    __EVENT_MESSAGE[ "annulment" ] = ( Template( "" ), Template( " received an annulment in $year at $place" ) )
    __EVENT_MESSAGE[ "baptism" ] = ( Template( "" ), Template( " was baptized in $year at $place" ) )
    # source for wording: http://www.jewfaq.org/barmitz.htm 
    # a quick google check supports that this is generally accepted phrasing
    __EVENT_MESSAGE[ "bar mitzvah" ] = ( Template( "" ), Template( " became a bar mitzvah in $year at $place" ) )
    __EVENT_MESSAGE[ "bat mitzvah" ] = ( Template( "" ), Template( " became a bat mitzvah in $year at $place" ) )
    __EVENT_MESSAGE[ "birth" ] = ( Template( "" ), Template( " was born in $year at $place" ) )
    __EVENT_MESSAGE[ "blessing" ] = ( Template( "" ), Template( " was blessed in $year at $place" ) )
    __EVENT_MESSAGE[ "burial" ] = ( Template( "" ), Template( " was buried in $year at $place" ) )
    __EVENT_MESSAGE[ "census" ] = ( Template( "" ), Template( " participated in a census in $year at $place" ) )
    __EVENT_MESSAGE[ "christening" ] = ( Template( "" ), Template( " was christened in $year at $place" ) )
    __EVENT_MESSAGE[ "confirmation" ] = ( Template( "" ), Template( " was confirmed in $year at $place" ) )
    __EVENT_MESSAGE[ "cremation" ] = ( Template( "" ), Template( " was cremated in $year at $place" ) )
    __EVENT_MESSAGE[ "death" ] = ( Template( "" ), Template( " died in $year at $place" ) )
    __EVENT_MESSAGE[ "degree" ] = ( Template( "" ), Template( " was awarded a degree in $year at $place" ) )
    __EVENT_MESSAGE[ "divorce" ] = ( Template( "" ), Template( " was granted a divorce in $year at $place" ) )
    __EVENT_MESSAGE[ "divorce filing" ] = ( Template( "" ), Template( " filed for divorce in $year at $place" ) )
    __EVENT_MESSAGE[ "elected" ] = ( Template( "" ), Template( " was elected in $year at $place" ) )
    __EVENT_MESSAGE[ "emigration" ] = ( Template( "" ), Template( " emmigrated in $year at $place" ) )
    __EVENT_MESSAGE[ "engagement" ] = ( Template( "" ), Template( " became engaged in $year at $place" ) )
    __EVENT_MESSAGE[ "first communion" ] = ( Template( "" ), Template( " received first communion in $year at $place" ) )
    __EVENT_MESSAGE[ "graduation" ] = ( Template( "" ), Template( " graduated in $year at $place" ) )
    __EVENT_MESSAGE[ "immigration" ] = ( Template( "" ), Template( " immigrated in $year at $place" ) )
    # attempt to distinguish between the marriage type events
    __EVENT_MESSAGE[ "marriage" + str( FamilyRelType.MARRIED ) ] = ( Template( "" ), Template( " got married in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage" + str( FamilyRelType.UNMARRIED ) ] = ( Template( "" ), Template( " started a family in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage" + str( FamilyRelType.CIVIL_UNION ) ] = ( Template( "" ), Template( " entered a civil union in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage" + str( FamilyRelType.UNKNOWN ) ] = ( Template( "" ), Template( " started a family in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage" + str( FamilyRelType.CUSTOM ) ] = ( Template( "" ), Template( " started a family in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage banns" ] = ( Template( "" ), Template( " announced a marriage banns in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage contract" ] = ( Template( "" ), Template( " entered a marriage contract in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage license" ] = ( Template( "" ), Template( " obtained a marriage license in $year at $place" ) )
    __EVENT_MESSAGE[ "marriage settlement" ] = ( Template( "" ), Template( " obtained a marriage settlement in $year at $place" ) )
    __EVENT_MESSAGE[ "military service" ] = ( Template( "" ), Template( " entered military service in $year at $place" ) )
    __EVENT_MESSAGE[ "naturalization" ] = ( Template( "" ), Template( " became naturalized in $year at $place" ) )
    __EVENT_MESSAGE[ "nobility title" ] = ( Template( "" ), Template( " had a title bestowed in $year at $place" ) )
    __EVENT_MESSAGE[ "ordination" ] = ( Template( "" ), Template( " was ordained in $year at $place" ) )
    __EVENT_MESSAGE[ "probate" ] = ( Template( "" ), Template( " was granted probate in $year at $place" ) )
    __EVENT_MESSAGE[ "retirement" ] = ( Template( "" ), Template( " retired in $year at $place" ) )

    # Mostly because I can't think of a decent way to express what the event is trying to convey, they're unsupported.
    # It seems events are being somewhat overloaded to track notes about a person.
    __UNSUPPORTED_EVENTS = [ 'alternate parentage', 'cause of death', 'education', 'medical information', 'number of marriages', 'occupation', 'property', 'religion', 'residence', 'will', 'year' ]

    __INTRO   = "On this day in family history ..." + "\n"
    __NOEVENT = "...nothing happened!  Maybe tomorrow!"

    # String constants related to the options menu
    __LIVINGONLY  = "Report only living tree members"
    __SHOWEVENT = "Show these events"
    __SORTBY = "Sort by "
    
    def init( self ):
        from gramps.gen.lib.date import Today
        self.set_text( self.__INTRO )
        self.tDay = Today().get_day()
        self.tMonth = Today().get_month()
        
    def on_load( self ):
        self.set_wrap( False )

    def db_changed( self ):
        self.update()
        
    def build_options( self ):
        from gramps.gen.plug.menu._booleanlist import BooleanListOption
        from gramps.gen.plug.menu._enumeratedlist import EnumeratedListOption
        
        self.opts = []
        
        #items = ''
        #op = EnumeratedListOption( self.__LIVINGONLY, items )
        #items = op.add_item( "Yes", "Yes" )
        #items = op.add_item( "No", "No" )
        #self.opts.append( op )

        #items = ''
        #op = EnumeratedListOption( self.__SORTBY, items )
        #op.add_item( 0, "Person Name" )
        #op.add_item( 1, "Event Type" )
        #op.add_item( 2,"Event Year" )
        #op.add_item( 3,"Gramps ID" )
        #op.add_item( 4,"Location" )
        #self.opts.append( op )
        
        op = BooleanListOption( self.__SHOWEVENT )
        op.add_button( "adopted", True )
        op.add_button( "adult\nchristening", True )
        op.add_button( "alternate\nmarriage", False )
        op.add_button( "annulment", False )
        op.add_button( "baptism", False )
        op.add_button( "bar mitzvah", False )
        op.add_button( "bat mitzvah", False )
        op.add_button( "birth", True )
        op.add_button( "blessing", False )
        op.add_button( "burial", False )
        op.add_button( "census", False )
        op.add_button( "christening", False )
        op.add_button( "confirmation", False )
        op.add_button( "cremation", False )
        op.add_button( "death", True )
        op.add_button( "degree", False )
        op.add_button( "divorce", False )
        op.add_button( "divorce\nfiling", False )
        op.add_button( "elected", True )
        op.add_button( "emigration", True )
        op.add_button( "engagement", False )
        op.add_button( "first\ncommunion", False )
        op.add_button( "graduation", True )
        op.add_button( "immigration", True )
        op.add_button( "marriage", True )
        op.add_button( "marriage\nbanns", False )
        op.add_button( "marriage\ncontract", False )
        op.add_button( "marriage\nlicense", False )
        op.add_button( "marriage\nsettlement", False )
        op.add_button( "military\nservice", True )
        op.add_button( "naturalization", True )
        op.add_button( "nobility\ntitle", True )
        op.add_button( "ordination", True )
        op.add_button( "probate", False )
        op.add_button( "retirement", True )
        self.opts.append( op )

        list(map(self.add_option, self.opts))

    def main( self ):
        """
        Iterate over the people in the database and report events that occurred
        on the current day and month.  Optionally discard results of people who
        are deceased.  A person will be considered deceased if they have a death
        or burial event associated with them.  Optionally report only a user
        defined list of events.  It is possible to report different events for
        living and deceased people.  Report may be sorted by name, event type,
        or by year.
        
        Events that are not associated with any person will not be reported.
        """
       
        eventList  = self.getEvents( 'People' )
        eventList += self.getEvents( 'Family' )

        self.generateReport( eventList )

    def getEvents( self, eventType):
        from gramps.gen.lib.date import Date

        eventType = eventType.lower()
        ev = { 'people': ( self.dbstate.db.iter_people, 'Person' ), 'family':( self.dbstate.db.iter_families, 'Family' ) }

        eventList = []
        handleType = ev[eventType][1]
        for p in ev[eventType][0]():
            for ref in p.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle( ref.ref )
                eType = event.get_type().string
                if not eType.lower() in self.__UNSUPPORTED_EVENTS:
                    if eventType == 'people':
                        name = p.get_primary_name().get_regular_name()
                        # TODO: It is possible to figure out the spouse of someone who has an Person marriage event
                        # not linked to a family, if the spouse is also listed with the marriage as a Person event.
                        # The simplest way is probably to compare the gramps_id and to emulate the family style reporting.
                        # see https://stackoverflow.com/a/16013517/759749 for how to count the gramps_ids and discover which
                        # have multiplicity > 1
                        if eType.lower() == 'marriage':
                            extraInfo = int( FamilyRelType.UNKNOWN )
                        else:
                            extraInfo = ""
                    elif eventType == 'family':
                        # I think the most common family events are marriage, residence, or divorce, though I stand
                        # ready to be corrected on a number of other family events.
                        #
                        # For family events other than where the mother and father are the named people,
                        # expect unusual output.
                        father = self.dbstate.db.get_person_from_handle( p.get_father_handle() )
                        mother = self.dbstate.db.get_person_from_handle( p.get_mother_handle() )
                        extraInfo = int( p.get_relationship() )

                        # attempt to make presentation arbitrary on a basis other than gender
                        if mother.get_primary_name().get_name() < father.get_primary_name().get_name():
                            name = mother.get_primary_name().get_regular_name() + " and " + father.get_primary_name().get_regular_name()
                        else:
                            name = father.get_primary_name().get_regular_name() + " and " + mother.get_primary_name().get_regular_name()
                    else:
                        name = "unknown participant"
                        extraInfo = ""
                        
                    handle = p.handle
                    eDate = event.get_date_object()
                    eCalendar = eDate.get_calendar()
                    
                    if eCalendar != Date.CAL_GREGORIAN:
                       eDate = eDate.to_calendar( "gregorian" )
                    
                    eDay = eDate.get_day()
                    eMonth = eDate.get_month()
                    eYear = eDate.get_year()
                    
                    eID    = event.gramps_id
                    
                    ePlace = "unknown location"
                    evRefs = event.get_referenced_handles( )
                    for r in evRefs:
                        # This is a touch basic, if you've done a good job of defining a place hierarchy then
                        # this only prints the most local place value available instead of the entire hierarchical name.
                        # TODO: Improve the name reporting to include hierarchical name
                        if r[0] == 'Place':
                            ePlace = self.dbstate.db.get_place_from_handle( r[1] ).get_name().get_value()

                    dateMatch = eMonth == self.tMonth and eDay == self.tDay
                    
                    if dateMatch:
                        eventList.append( ( name, handle, handleType, eType, eYear, eID, ePlace, extraInfo ) )
        return eventList

    def generateReport( self, events ):
        if len( events ) == 0:
            message = "\t" + self.__NOEVENT + "\n"
            self.append_text( message )
        else:
            # TODO allow sort by any key, user defined
            events.sort( key = lambda x: x[4] )
            for name, handle, hType, eType, year, grampsID, place, extraInfo in events:
                eStr = eType.lower()
                if eStr == 'marriage':
                    # Marriage messages are stored in marriageN where N is the integer relationship type
                    eStr = eStr + str( extraInfo )
                    
                prefix = self.__EVENT_MESSAGE[ eStr ][ 0 ].safe_substitute( year = year, place = place )
                suffix = self.__EVENT_MESSAGE[ eStr ][ 1 ].safe_substitute( year = year, place = place )

                self.append_text( "\t... " + prefix )
                self.link( name, hType, handle )
                self.append_text( suffix + "\n" )