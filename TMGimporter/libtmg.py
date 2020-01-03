#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# TMG Importer addon for Gramps genealogy program
#
# Copyright (C) 2017-2018 Sam Manzi
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

'''
Import from an Wholly Genes - The Master Genealogist (TMG) Project backup file
(*.SQZ)
'''

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import os  # Used by clearconsole()
import glob  # Used by insensitive_glob()
import configparser
import zipfile  # Used to read sqz
import tempfile
import calendar  # Used by TMG parse_date
from io import StringIO  # Used to read sqz

import logging
LOG = logging.getLogger(".TMGImport")

#------------------------------------------------------------------------
#
# External Libraries
#
#------------------------------------------------------------------------
# Name: dbf.pypi
# https://pypi.python.org/pypi/dbf
try:
    from dbf import Table
except (ImportError, ValueError):
    print("\nFor TMG Importer to work please install 'dbf' \
           from https://pypi.python.org/pypi/dbf ")

#-------------------------------------------------------------------------
#
# GTK libraries
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------

from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.lib import (
    Address, Attribute, AttributeType, ChildRef,
    ChildRefType, Citation, Date, Event, EventRef, EventRoleType,
    EventType, Family, FamilyRelType, LdsOrd, Location, Media,
    MediaRef, Name, NameType, Note, NoteType, Person, PersonRef, Place,
    RepoRef, Repository, RepositoryType, Researcher,
    Source, SourceMediaType, SrcAttribute,
    Surname, Tag, Url, UrlType, PlaceType, PlaceRef, PlaceName)
from gramps.gen.db import DbTxn
from gramps.gen.utils.file import media_path
from gramps.gen.utils.id import create_id

from gramps.gui.glade import Glade
from gramps.gui.managedwindow import ManagedWindow
#from gramps.gen.utils.libformatting import ImportInfo

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------

# TMG Database Table names

global tmgtables_ext, tmgPeople, tmgSourceCategories, tmgFocusGroupMembers, \
tmgCustomFlags, tmgDataSets, tmgDNAinformation, tmgParticipantsWitnesses, \
tmgParentChildRelationships, tmgEvents, tmgExhibits, tmgTimelineLocks, \
tmgResearchTasks, tmgSources, tmgNames, tmgNameDictionary, tmgNamePartType, \
tmgNamePartValue, tmgFocusGroups, tmgPlaces, tmgPlaceDictionary, \
tmgPlacePartType, tmgPlacePartValue, tmgRepositories, tmgCitations, tmgStyles, \
tmgTagTypes, tmgSourceComponents, tmgSourceRepositoryLinks, \
tmgExcludedDuplicates

#------------------------------------------------------------------------
#
# TMG Importer - Support functions
#
#------------------------------------------------------------------------


class TMGError(Exception):
    """
    Class used to report TMG errors.
    """
    def __init__(self, value=''):
        Exception.__init__(self)
        self.value = value

    def __str__(self):
        return self.value


def insensitive_glob(pattern):
    '''
    Returns Case insensitive name
    .............................
    Replace each alphabetic character 'c' with [cC]
    '''
    def either(c):
        return '[%s%s]' % (c.lower(), c.upper()) if c.isalpha() else c
    return glob.glob(''.join(map(either, pattern)))

#------------------------------------------------------------------------
#
# TMG Project management of tables etc (read (*.PJC) text file of settings)
#TODO Add methods for
#               - Default directories eg: Image, Backup, Timeline,
#                   GEDCOM, Reports(config), Repeat, Geographic,
#                   Slideshow, ReportsOutput,
#               -
#               -
#               -
#               -
#               -
#               -
#------------------------------------------------------------------------


class TmgProject(object):
    '''
    TMG Project management of tables etc
    * Returns the name of the project
    * Provides information from the (.PJC) file
    * Provides a file summary
    '''
    def __init__(self, tmgproject):
        self.tmgproject = tmgproject
        self.pathandfile = os.path.split(self.tmgproject)
        self.projectpath = self.path()

        self.tables = {}

    def __str__(self):
        '''
        Project name (.PJC)
        '''
        projectname = self.pathandfile[1]

        return projectname

    def path(self):
        '''
        Project path

        Usage:
        > TmgProject.path()
        '''
        projectpath = self.pathandfile[0]

        return projectpath

    def version(self):
        '''
        TMG Project Version from (.PJC)

        Usage:
        > TmgProject.version()

        Result:
        > 8.0
        '''
        config = configparser.ConfigParser()
        config.read(self.tmgproject)
        version = config['Stamp']['PjcVersion']
        version = float(version)
        #return 'PJC version : {}'.format(version)
        return version

    def researcher(self):  # TODO Use to populate Gramps Researcher
        '''
        Researcher details

        Usage:
        > TmgProject.researcher()

        [Researcher]
        Name
        Address1
        Address2
        Phone
        Email
        Website
        '''
        config = configparser.ConfigParser()
        config.read(self.tmgproject)

        name = config['Researcher']['Name']
        address1 = config['Researcher']['Address1']
        address2 = config['Researcher']['Address2']
        phone = config['Researcher']['Phone']
        email = config['Researcher']['Email']
        website = config['Researcher']['Website']

        researcher = '\n##########Researcher############\n\
                        Name: {}\nAddress: {}\n\t {}\nPhone: {}\n\
                        Email: {}\nWebsite: {}'.format(
            name,
            address1,
            address2,
            phone,
            email,
            website)
        return researcher

    def status(self):
        '''
        [Advanced] details associated with project

        Usage:
        > TmgProject.status()

        * Use International Date format YYYY/MM/DD

        CreatedDate
        CreateTime
        LastIndexed
        LastVFI
        LastOptimized

        eg:
        Status:
        Create Date: 2006/05/15
        Create Time: 07:32:18 PM
        Last Indexed: 2012/07/30
        Last VFI: 2013/06/07
        Last Optimized: 2013/06/12
        '''
        config = configparser.ConfigParser()
        config.read(self.tmgproject)

        createdate = config['Advanced']['CreateDate']
        _createdate = createdate[0:4] + '/' + \
            createdate[4:6] + '/' + createdate[6:8]
        createdate = _createdate

        createtime = config['Advanced']['CreateTime']

        lastindexed = config['Advanced']['LastIndexed']
        _lastindexed = lastindexed.split('/')
        _lastindexed = _lastindexed[2] + '/' + \
            _lastindexed[0] + '/' + _lastindexed[1]
        lastindexed = _lastindexed

        lastvfi = config['Advanced']['LastVFI']
        _lastvfi = lastvfi.split('/')
        _lastvfi = _lastvfi[2] + '/' + _lastvfi[0] + '/' + _lastvfi[1]
        lastvfi = _lastvfi

        lastoptimized = config['Advanced']['LastOptimized']
        _lastoptimized = lastoptimized.split('/')
        _lastoptimized = _lastoptimized[2] + '/' + \
            _lastoptimized[0] + '/' + _lastoptimized[1]
        lastoptimized = _lastoptimized

        status = '\n######Status######\nCreate Date: {}\n\
                  Create Time: {}\nLast Indexed: {}\n\
                  Last VFI: {}\nLast Optimized: {}'.format(
            createdate,
            createtime,
            lastindexed,
            lastvfi,
            lastoptimized)

        return status

    def summary(self):
        '''
        Project File summary

        Usage:
        > TmgProject.summary()

        File types - Usage:
        SQZ - TMG Backup file

        CDX - Foxpro Structural Compound Index Files
        DBF - FoxPro Database Files
        FPT - Foxpro Memo Files
        LOG - TMG Log File
        PJC - TMG Project Configuration File

        ACC - Accent Definition Files
        FLC - TMG Filter Definition Files - List of Citations
        FLE - TMG Filter Definition Files - List of Events
        FLK - TMG Filter Definition Files - List of Tasks
        FLL - TMG Filter Definition Files - List of Places
        FLN - TMG Filter Definition Files - List of Names
        FLP - TMG Filter Definition Files - List of People
        FLR - TMG Filter Definition Files - List of Repositories
        FLS - TMG Filter Definition Files - List of Sources
        FLY - TMG Filter Definition Files - List of Tag Types
        FLW - TMG Filter Definition Files - List of Witnesses

        COL - Color Definition Files
        DNA - DNA Laboratory Definition files
        INI - Configuration Files
        LO  - Layout Files
        TBR - Toolbar Files
        TXT - Text Files
        DBT - Database Text Files Used With Timeline databases
        DOC - Descriptive Text Files used with Timeline databases
        RPT - Report Definition Files
        BKP - Backup Definition Files
        EMF - Frame Files for use with Visual ChartForm
        LOG - Text File For Logging major events in a Project

        total files

        See: http://www.tmgtips.com/dbnames2.htm
        '''
        #TODO expand this to identify all tmg file types
        #TODO use a dict to collect it all
        tmgproject = self.tmgproject.rsplit('/', 1)
        print('Project path =:', tmgproject[0])
        projectpath = tmgproject[0] + '/'
        ###########

        # read sqz
        sqz_names = insensitive_glob(str(projectpath + '*.' + 'sqz'))
        sqzfiles = len(sqz_names), 'TMG backup file (SQZ)'

        # read pjcs
        project_names = insensitive_glob(str(projectpath + '*.' + 'pjc'))
        pjcfiles = len(project_names), 'TMG Project Configuration File (PJC)'

        # read dbfs
        dbf_names = insensitive_glob(str(projectpath + '*.' + 'dbf'))
        dbffiles = len(dbf_names), 'FoxPro Database Files (DBF)'

        # read fpts
        fpt_names = insensitive_glob(str(projectpath + '*.' + 'fpt'))
        fptfiles = len(fpt_names), 'Foxpro Memo Files (FPT)'

        # read cdxs
        cdx_names = insensitive_glob(str(projectpath + '*.' + 'cdx'))
        cdxfiles = len(
            cdx_names), 'Foxpro Structural Compound Index Files (CDX)'

        # read logs
        log_names = insensitive_glob(str(projectpath + '*.' + 'log'))
        logfiles = len(log_names), 'TMG Log File (LOG)'

        # read *(all files in directory)
        all_names = insensitive_glob(str(projectpath + '*.' + '*'))
        allfiles = len(
            all_names), 'Total all files in directory provided (*.*)'

        #(0, 'TMG backup file (SQZ)',
        # 1, 'TMG Project Configuration File (PJC)',
        # 29, 'FoxPro Database Files (DBF)',
        # 18, 'Foxpro Memo Files (FPT)',
        # 0, 'Foxpro Structural Compound Index Files (CDX)',
        # 0, 'TMG Log File (LOG)',
        # 87, 'all files in directory provided')
        summaryfiles = sqzfiles + pjcfiles + dbffiles + \
            fptfiles + cdxfiles + logfiles + allfiles

        _summaryfiles = ''
        for datum in range(0, len(summaryfiles), 2):
            #print('{:>8}|{}'.format(summaryfiles[datum],
            #                        summaryfiles[datum + 1]))
            _summaryfiles = _summaryfiles + \
                '{:>7}|{}\n'.format(
                    summaryfiles[datum],
                    summaryfiles[datum + 1])

        return ('\n#####File Summary#######\nNumber |Usage (Type)\n{}'.format(
                _summaryfiles))

#------------------------------------------------------------------------
##TODO
# Identify TMG DBF version by table names
#
#------------------------------------------------------------------------


'''
Test TMG DBF fields exist in Tables to determine/verify TMG Project file
version

    Table (DBF) / Field / New in TMG Version
    A / reminders / 7.01
    C / property / 8.0
    D / dsp2 / 8.0
    DNA / descript / 6.04
    DNA / kitnumber / 7.04
    DNA / type / 7.04
    DNA / namerec / 7.04
    E / sequence / 6.0
    i / caption / 6.0
    i / sortexh / 6.01
    i / imagefore / 7.0
    i / imageback / 7.0
    i / transpar / 7.0
    L / refernce / 6.0
    M / reminders / 7.01
    O / recent / 6.0
    T / reminders / 7.1
    T / tsentence / ? change structure in v9.0 ?
    N / sndxsurn / 7.01
    N / sndxgvn / 7.01
    N / pbirth / 7.01
    N / pdeath / 7.01
    N / refer / 7.01
    N / pref_id / 7.01
    N / last_edit / 7.01
    S / sequence / 6.0
    S / citmemo / 6.0
'''

#------------------------------------------------------------------------
#
# Database related functions
#
#------------------------------------------------------------------------


def map_dbfs_to_tables(tablemap):
    '''
    TMG table Mappings

    Map database tables to internal names after
    being passed a project file ( .pjc)

    Usage:
    > map_dbfs_to_tables()
    '''
    #TODO - Make it simpler. Use a dict. Open and close all tables from here?
    #TODO - Get rid of need for globals.

    global tmgtables_ext, tmgPeople, tmgSourceCategories, tmgFocusGroupMembers, \
    tmgCustomFlags, tmgDataSets, tmgDNAinformation, tmgParticipantsWitnesses, \
    tmgParentChildRelationships, tmgEvents, tmgExhibits, tmgTimelineLocks, \
    tmgResearchTasks, tmgSources, tmgNames, tmgNameDictionary, tmgNamePartType, \
    tmgNamePartValue, tmgFocusGroups, tmgPlaces, tmgPlaceDictionary, tmgPlacePartType, \
    tmgPlacePartValue, tmgRepositories, tmgCitations, tmgStyles, tmgTagTypes, \
    tmgSourceComponents, tmgSourceRepositoryLinks, tmgExcludedDuplicates

    # only works if you pass a pjc file
    if len(tablemap) == 0:
        print("No name for the tablemap was passed", tablemap)
        return
    else:
        tmgtables_ext = tablemap

    #print("tmgtables_ext", tmgtables_ext)

    # Initialise all TMG 'Visual FoxPro Database Files (DBF)'

    tmgPeople = Table(
        tmgtables_ext['tmgPeople'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgSourceCategories = Table(
        tmgtables_ext['tmgSourceCategories'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgFocusGroupMembers = Table(
        tmgtables_ext['tmgFocusGroupMembers'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgCustomFlags = Table(
        tmgtables_ext['tmgCustomFlags'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgDataSets = Table(
        tmgtables_ext['tmgDataSets'][1],
        ignore_memos=True,
        #ignore_memos=False,
        dbf_type='vfp')

    tmgDNAinformation = Table(
        tmgtables_ext['tmgDNAinformation'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgParticipantsWitnesses = Table(
        tmgtables_ext['tmgParticipantsWitnesses'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgParentChildRelationships = Table(
        tmgtables_ext['tmgParentChildRelationships'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgEvents = Table(
        tmgtables_ext['tmgEvents'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgExhibits = Table(
        tmgtables_ext['tmgExhibits'][1],
        ignore_memos=True,   # TODO Don't ignore memo's if present (try/except)
        #ignore_memos=False,
        dbf_type='vfp')

    tmgTimelineLocks = Table(
        tmgtables_ext['tmgTimelineLocks'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgResearchTasks = Table(
        tmgtables_ext['tmgResearchTasks'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgSources = Table(
        tmgtables_ext['tmgSources'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgNames = Table(
        tmgtables_ext['tmgNames'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgNameDictionary = Table(
        tmgtables_ext['tmgNameDictionary'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgNamePartType = Table(
        tmgtables_ext['tmgNamePartType'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgNamePartValue = Table(
        tmgtables_ext['tmgNamePartValue'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgFocusGroups = Table(
        tmgtables_ext['tmgFocusGroups'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgPlaces = Table(
        tmgtables_ext['tmgPlaces'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgPlaceDictionary = Table(
        tmgtables_ext['tmgPlaceDictionary'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

# tmgPicklist = Table(tmgtables_ext['tmgPicklist'][1], ignore_memos=True,
# dbf_type='vfp') # dbf.DbfError: Visual Foxpro does not support FoxPro
# w/memos [f5]

    tmgPlacePartType = Table(
        tmgtables_ext['tmgPlacePartType'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgPlacePartValue = Table(
        tmgtables_ext['tmgPlacePartValue'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgRepositories = Table(
        tmgtables_ext['tmgRepositories'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgCitations = Table(
        tmgtables_ext['tmgCitations'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgStyles = Table(
        tmgtables_ext['tmgStyles'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgTagTypes = Table(
        tmgtables_ext['tmgTagTypes'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgSourceComponents = Table(
        tmgtables_ext['tmgSourceComponents'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgSourceRepositoryLinks = Table(
        tmgtables_ext['tmgSourceRepositoryLinks'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    tmgExcludedDuplicates = Table(
        tmgtables_ext['tmgExcludedDuplicates'][1],
        #ignore_memos=True,
        ignore_memos=False,
        dbf_type='vfp')

    #print("----TMG DBF table initialisation---done")
    return

#------------------------------------------------------------------------
#
# TMG table Mappings
#
#------------------------------------------------------------------------


class TmgTable(object):

    '''
    TMG table Mappings

    Map database tables to internal names

    When passed the project tablefolder returns a dict
    '''

    def __init__(self, tablefolder):
        self.tablefolder = tablefolder
        self.table_mapped = False
        self.dbf_names = []
        self.tmgtables_ext = {
            'tmgPeople': ('_$.dbf', ''),
            'tmgSourceCategories': ('_a.dbf', ''),
            'tmgFocusGroupMembers': ('_b.dbf', ''),
            'tmgCustomFlags': ('_c.dbf', ''),
            'tmgDataSets': ('_d.dbf', ''),
            'tmgDNAinformation': ('_dna.dbf', ''),
            'tmgParticipantsWitnesses': ('_e.dbf', ''),
            'tmgParentChildRelationships': ('_f.dbf', ''),
            'tmgEvents': ('_g.dbf', ''),
            'tmgExhibits': ('_i.dbf', ''),
            'tmgTimelineLocks': ('_k.dbf', ''),
            'tmgResearchTasks': ('_l.dbf', ''),
            'tmgSources': ('_m.dbf', ''),
            'tmgNames': ('_n.dbf', ''),
            'tmgNameDictionary': ('_nd.dbf', ''),
            'tmgNamePartType': ('_npt.dbf', ''),
            'tmgNamePartValue': ('_npv.dbf', ''),
            'tmgFocusGroups': ('_o.dbf', ''),
            'tmgPlaces': ('_p.dbf', ''),
            'tmgPlaceDictionary': ('_pd.dbf', ''),
            # 'tmgPicklist': ('_pick1.dbf', ''),
            'tmgPlacePartType': ('_ppt.dbf', ''),
            'tmgPlacePartValue': ('_ppv.dbf', ''),
            'tmgRepositories': ('_r.dbf', ''),
            'tmgCitations': ('_s.dbf', ''),
            'tmgStyles': ('_st.dbf', ''),
            'tmgTagTypes': ('_t.dbf', ''),
            'tmgSourceComponents': ('_u.dbf', ''),
            'tmgSourceRepositoryLinks': ('_w.dbf', ''),
            'tmgExcludedDuplicates': ('_xd.dbf', '')}

    def __str__(self):
        '''
        Return the dict for the mapped tables
        '''
        #self.dbfnames()
        self.tablemap()
        if len(self.tmgtables_ext) == 0:
            print('failed to create dbf table mapping')

        return '{} Tables Mapped'.format(len(self.tmgtables_ext))

    def tablemap(self):
        r'''
         assign table names to correct tables

         create tmg tables dictionary and replace entries with the file path to
         the table

         eg:call it using:
           tmgtables['tmgPeople']

         to add the file path use:
           tmgtables['tmgPeople'] = '\path\to\file\projectname__$.dbf'

        # combined dict with a tuple per key
        '''
        # Get DBF names from provided directory
        self.dbf_names = insensitive_glob(str(self.tablefolder + '*.' + 'dbf'))

        # store the filepath in tmgtables_temp
        tmgtables_temp = {}
        x = 0
        # dbf_names holds the file paths for dbfs from glob
        for dbffile in self.dbf_names:
            test = dbffile.upper()
            for part in self.tmgtables_ext:
                extension = self.tmgtables_ext[part][0]
                if test.endswith((extension.upper())):
                    # add to dict as
                    # eg:{'tmgPeople':['_$.dbf','path/to/file/name.dbf'], ...
                    tmgtables_temp[part] = extension, dbffile
                    x += 1

        # copy temp dict over original
        self.tmgtables_ext = dict(tmgtables_temp)
        self.table_mapped = True
        return self.tmgtables_ext


#------------------------------------------------------------------------
#
# TMG DataSet
#
#------------------------------------------------------------------------


def datasets():
    '''
    Return a dictionary of Datasets in TMG project

    Tables:
    D .dbf - tmgDataSets - Data Set File

    -----------------------------
      0 - dsid      : 8                            # DataSet ID# (Primary key)
      1 - dsname    : u'sample / Royal92 - 2nd import'  # DataSet Name
      2 - dslocation: u'royal92.ged'               # Original Import location
      3 - dstype    : 1                                 # Import type
      4 - dslocked  : False                             # Is DataSet Locked
      5 - dsenabled : True                              # Is DataSet Enabled
      6 - property  : u''
      7 - dsp       : u''
      8 - dsp2      : u''                               # Only in TMG 8 +
      9 - dcomment  : u'A comment is here sometimes'    # DataSet Comment
     10 - host      : u''
     # Default name style for this dataset Relates to st.styleid(ST.dbf).
     11 - namestyle : 0
     # Default place style for this dataset Relates to st.styleid(ST.dbf).
     12 - placestyle: 0
     13 - tt        : u' '
    -----------------------------
    '''
    with tmgDataSets:
        alldatasets = {}
        for count, record in enumerate(tmgDataSets):
            if record.dsid:
                alldatasets[count] = record.dsid, record.dsname.rstrip(), \
                                     record.dslocation.rstrip(), \
                                     record.dstype, \
                                     record.dslocked, record.dsenabled, \
                                     record.property, record.dsp, \
                                     record.dcomment.rstrip(), \
                                     record.host.rstrip(), record.namestyle, \
                                     record.placestyle, record.tt.rstrip()
    '''
    All datasets() =
    {0: (1, 'TMG Sample Data Set', 'C:\\MYDATA\\SAMPLE'   , 1,
         False, True , '', '', '', '', 0, 0, ''),
     1: (2, 'sample / Royal92 - 1st import', 'royal92.ged', 1,
         True , True , '', '', '', '', 0, 0, ''),
     2: (8, 'sample / Royal92 - 2nd import', 'royal92.ged', 1,
         False, True , '', '', '', '', 0, 0, ''),
     3: (9, 'sample / Royal92 - 3rd import', 'royal92.ged',
         1, False, False, '', '', '', '', 0, 0, '')}
    '''

    return alldatasets


def only_has_one_dataset():
    '''
    Returns true if only one Dataset in Project
    '''
    datasets_total = len(datasets())

    if datasets_total > 1:
        print("datasets_total = ", datasets_total)
        return False
    else:
        print("datasets_total = ", datasets_total)
        return True

    return True

def only_first_dataset():
    '''
    Returns only the first Dataset number in a multi-dataset backup
    Project (used by the command line)
    '''
    first_datasetid = (datasets()[0][0])

    print("first_datasetid = {}".format(first_datasetid))

    #datasets_total = len(datasets())
    #print("first_datasetid = {} of {} ".format(first_datasetid, datasets_total))

    # test output of other dataset ids
    '''
    second_datasetid = (datasets()[1][0])
    third_datasetid = (datasets()[2][0])
    forth_datasetid = (datasets()[3][0])
    print("second_datasetid = {} of {} ".format(
        second_datasetid, datasets_total))
    print("third_datasetid = {} of {} ".format(
        third_datasetid, datasets_total))
    print("forth_datasetid = {} of {} ".format(
        forth_datasetid, datasets_total))
    '''
    return first_datasetid

#-------------------------------------------------------------------------
#
#
# Trial of dbf fields from Datasets table
#
#-------------------------------------------------------------------------


def trial_d_dbf():
    '''
    Trial All TMG DBF Tables (Fields & Info)

    '''
    with tmgPeople:
        t = tmgPeople
        print("Version:\n", t.version)
        print("Filename:\n", t.filename)
        print("Memoname:\n", t.memoname)
        print("Field names:\n", t.field_names)
        print("Total Field count:\n", t.field_count)
        print("Last update:\n", t.last_update)
        print("Codepage:\n", t.codepage)
        print("Status:\n", t.status)
        print("Structure:\n", t.structure)
        print("Supported_tables:\n", t.supported_tables)
        print("First record:\n", t.first_record)
        print("Last record:\n", t.last_record)
        print()
        count = 0
        for record in tmgPeople:
            if record.dsid == 9:
                #person = record.per_no
                count += 1
        print("Number of People records from dataset 9 = ", count)
        return

#--------------------------------------------------------------------------
#
# Util
#
#--------------------------------------------------------------------------


def trial_print_table_fields():
    '''
    Print table fields for reference
    '''
    for x in (tmgPeople, tmgSourceCategories, tmgFocusGroupMembers,
              tmgCustomFlags, tmgDataSets, tmgDNAinformation,
              tmgParticipantsWitnesses, tmgParentChildRelationships, tmgEvents,
              tmgExhibits, tmgTimelineLocks, tmgResearchTasks, tmgSources,
              tmgNames, tmgNameDictionary, tmgNamePartType,
              tmgNamePartValue, tmgFocusGroups, tmgPlaces, tmgPlaceDictionary,
              tmgPlacePartType, tmgPlacePartValue, tmgRepositories,
              tmgCitations, tmgStyles, tmgTagTypes, tmgSourceComponents,
              tmgSourceRepositoryLinks, tmgExcludedDuplicates):
        print("**************************************************************")
        print(x, x.field_names)
        print("**************************************************************")
    return

#--------------------------------------------------------------------------
#
# people  ($.dbf) table trial  (proof of concept )
#
#--------------------------------------------------------------------------


def trial_people(database, tmg_dataset):
    '''
    Pass the gramps 'database' name and the tmg dsid
    '''
    #------------------------------------
    #1. get a list of per_no id's for that dataset only
    #------------------------------------
    with tmgPeople:
        tmg_people_in_dataset = []
        tmg_dataset = tmg_dataset
        for record in tmgPeople:
            if record.dsid == tmg_dataset:
                if record.dsid is None:
                    return
                else:
                    tmg_people_in_dataset.append(record.per_no)

    #------------------------------------
    # get each persons name
    #------------------------------------
    with tmgNames:
        tmg_people_named = {}
        for record in tmgNames:
            if (record.dsid == tmg_dataset) and (record.primary is True):
                namesplit = record.srnamedisp.split()
                surname = namesplit[-1]
                givenname = namesplit[0]
                tmg_people_named[record.pref_id] = surname, givenname
    '''
    {1: ('ALEXANDER,', 'Frank'),
    2: ('KEEBLER,', 'Mary'),
    3: ('ALEXANDER,', 'Samuel')}
    '''
    #-------------------------
    #Add those people to the open Gramps database
    #-------------------------
    for tmgname in tmg_people_named:
        firstname = tmg_people_named[tmgname][0]
        surname = tmg_people_named[tmgname][1]
        # see gramps/gen/db/txn.py  (DbTxn )
        data = {"primary_name": {"first_name": firstname,
                "surname_list": [{"surname": surname}]}, }
        # AttributeError: 'dict' object has no attribute 'handle
        person = Person.create(Person.serialize(data))
        with DbTxn("Add Person", database) as tran:
            database.add_person(person, tran)

    return

#--------------------------------------------------------------------------
# lookups
#--------------------------------------------------------------------------


def short_place_name(database, placenum, tmg_dataset):
    '''
    When passed the tmg g.placenum returns the tmg p.shortplace name

    eg:
    short_place_name(database, 73, tmg_dataset)
    >>New York
    '''
    #--------------------------------------------
    #display place name
    #--------------------------------------------
    with tmgPlaces:
        tmg_dataset = tmg_dataset
        for record in tmgPlaces:
            if (record.dsid == tmg_dataset) and (record.recno == placenum):
                print("record.recno = ", record.recno,
                      "record.styleid = ", record.styleid,
                      "record.comment = ", record.comment,
                      "record.shortplace =", record.shortplace)
                return record.shortplace.rstrip()


def tag_type_name(database, eventtype, tmg_dataset):
    '''
    When passed the tmg eventtype number returns the tmg etypename

    Note: The etypenum'bers are not always identical between project sets if
          originally created with an older version of TMG!

    eg:
    tag_type_name(database, 12, tmg_dataset)
    >>Baptism
    '''
    #--------------------------------------------
    #display tag type
    #--------------------------------------------
    with tmgTagTypes:
        tmg_dataset = tmg_dataset
        for record in tmgTagTypes:
            if (record.dsid == tmg_dataset) and (record.etypenum == eventtype):
                return record.etypename.rstrip()
    '''
   Initial list From blank.pjc (tmg905)
1 Adoption             ado.
2 Birth                b.
3 Death                d.
4 Marriage             m.
5 Divorce              div.
6 Burial               bur.
7 Immigration          imm.
8 Address              add.
9 Employment           emp.
10 Residence            res.
11 Annulment            ann.
12 Baptism              bap.
13 Military-Begin       mlb.
14 Religion             rel.
15 Education            edu.
16 BaptismLDS           bap.
17 BarMitzvah           bar.
18 BatMitzvah           bat.
19 Census               cen.
20 Christening          chr.
21 Communion1st         com.
22 Divorce Filing       dvf.
23 Engagement           eng.
24 EndowmentLDS         end.
25 Graduation           grd.
26 Marriage bann        mbn.
27 Marriage contract    mcn.
28 Marriage license     mlc.
29 Marriage settlement  mst.
30 Passenger List       psg.
31 Probate              pro.
32 SealParentLDS        sp.
33 SealSpouseLDS        ss.
34 Misc                 msc.
35 Retirement           ret.
36 Name-Married         nam.
37 Name-Variation       nam.
38 Name-Change          nam.
39 Will                 wi.
40 Illness              ill.
41 Birth-Covenant       bct.
42 Blessing             bls.
43 Infant BlessingLDS   bls.
44 CancelSeal           can.
45 Codicil              cod.
46 Confirmation         cnf.
47 ConfirmLDS           cnf.
48 Criminal             crm.
49 Emigration           emi.
50 Excommunication      exc.
51 Naturalization       nat.
52 NullifyLDS           nul.
53 Ordinance            ord.
54 OrdinationLDS        ord.
55 Ordination           ord.
56 Presumed cancelled   prs.
57 Ratification         rat.
58 Rebaptism            rbp.
59 Reseal               rsl.
60 Restoration          rst.
61 SealChildLDS         sc.
62 Birth-Stillborn      b.
63 VoidLiving           vdl.
64 WAC                  wac.
65 Military-End         mle.
66 Occupation           occ.
67 Event-Misc           msc.
68 Birth-Illegitimate   b.
69 Living               liv.
70 Name-Baptism         nam.
71 Anecdote             ane.
72 Name-Nick            nam.
73 Attributes           att.
74 Association          ass.
75 Reference            ref.
76 GEDCOM               ged.
77 Note                 nt.
78 History              his.
79 Father-Biological
80 Father-Adopted
81 Father-Step
82 Father-God
83 Father-Foster
84 Father-Other
85 Mother-Biological
86 Mother-Adopted
87 Mother-Other
88 Mother-Step
89 Mother-God
90 Mother-Foster
91 Parent-Biological
92 Parent-Adopted
93 Parent-Other
94 Parent-Step
95 Parent-God
96 Parent-Foster
97 Stake                stk.
98 AFN                  afn.
99 Telephone            tel.
100 Namesake             nsk.
101 Number of marriages  #m.
102 Number of children   #c.
103 Age                  age.
104 Nationality          nat.
105 Caste                cst.
106 SSN                  ssn.
107 Description          des.
108 HTML                 htm:
109 NarrativeChildren    nar.
110 JournalIntro         nar.
111 JournalConclusion    nar.
    '''
    pass

#--------------------------------------------------------------------------
#
# Events (G/T/P tables) trial  (proof of concept)
# Uses:
# g.ETYPE > t.etypenum (Tag Type)
# g.PLACENUM > p.recno (Place file)
# convert dates to gramps date object
#--------------------------------------------------------------------------


def trial_events(database, tmg_dataset):
    '''
    Events trial import
    '''
    #--------------------------------------------
    #
    #--------------------------------------------
    with tmgEvents:
        tmg_events = {}
        tmg_dataset = tmg_dataset
        for record in tmgEvents:
            if record.dsid == tmg_dataset:
                eventtype = tag_type_name(database, record.etype, tmg_dataset)
                eventdate = parse_date(record.edate)
                shortplacename = short_place_name(database, record.placenum,
                                                  tmg_dataset)
                tmg_events[record.recno] = eventtype, record.per1, \
                                           record.per2, eventdate, \
                                           shortplacename, \
                                           record.efoot.rstrip()
    '''
[Recno =  2 ]
[Event type = Education ]
[per1 = 1 ]
[per2 = 0 ]
[event date = None ]
[Short PlaceName =   ]
[Event memo = [:CR:][:CR:]Frank Alexander was educated at Duffield Academy
  in Elizabethton and at Emory and Henry College in Washington County,
  Tennessee. ]
    '''
    #--------------------------------------------
    #
    #--------------------------------------------
    '''
    for tmgevent in tmg_events:
        eventtype = tmg_events[tmgevent][1]
        eventdate = tmg_events[tmgevent][4]
        eventplace = tmg_events[tmgevent][5]
        #data = {"type": {eventtype}, "date" : eventdate,
        #        "place" : eventplace,}
        data = {"date" : eventdate , "place" : eventplace}
        event = Event.create(Event.from_struct(data))
        with DbTxn("Add Event", database) as tran:
            database.add_event(event, tran)

    '''
    #--------------------------------------------
    #
    #--------------------------------------------
    pass

#-------------------

def on_changed(selection):
    # Get the selected Dataset row
    (model, iter) = selection.get_selected()
    # print value selected
    print("\nYou selected : TMG Data Set %s %s" %
          (model[iter][0], model[iter][1]))  # Datasetnumber & datasetname
    selecteddataset = int(model[iter][0])
    print("selecteddataset : ", selecteddataset)

    # set the label to a new value depending on the selection
    #self.label.set_text("\n %s %s %s" %
    #                    (model[iter][0],  model[iter][1], model[iter][2]))
    return True


#-------------------------------------------------------------------------
#
# Import data into the currently open database.     #####See: importxml.py
# Must take care of renaming media files according to their new IDs. #### ?
#
#-------------------------------------------------------------------------


def importData(database, sqzfilename, user):

    ######Check if Gramps Family Tree is empty if not stop import
    if not database.get_total() == 0:
        #TODO pop up GUI warning for tmg import, or just exit silently?
        LOG.warn("Create a New Family Tree to import your TMG Backup into.")
        tmgabortimport = True   # Report import stopped
        return
    #print("Current Family Tree is empty! database.get_total() = ",
    #      database.get_total())

    sqzfilename = os.path.normpath(sqzfilename)
    basefiledir = os.path.dirname(sqzfilename)

    ######check if SQZ contains a valid TMG PJC file
    rename_required = None
    if sqz_pjc_exist(sqzfilename):
        if check_dbf_lowercase(sqzfilename):
            rename_required = True
        else:
            rename_required = False

        #Create temporary folder for everything to work in
        # create temp folder for all extracted files & folders
        with tempfile.TemporaryDirectory() as tmpdirname:
            # extract files from SQZ
            extractsqz(sqzfilename, tmpdirname)

            #Find folder location of PJC file
            pjcfilelocation = find_file_ext(".PJC", tmpdirname)
            pjcfolder = os.path.dirname(pjcfilelocation)

            #Rename files to lowercase
            if rename_required:
                rename_files_lowercase(pjcfolder)

            #Initialize
            #TODO make this section simpler
            # updated name for pjc after rename
            pjcfilelocation = find_file_ext(".PJC", tmpdirname)
            project = TmgProject(pjcfilelocation)

            # Check PJC version is for TMG 9.02 or newer (PJCVERSION = 11.0)
            # and continue (For the TMG Program Version; generally subtract 1
            # from the PjcVersion number)
            pjcverresult = project.version()
            # PJC version number v11.0 or greater for TMG 9.02 +
            print("PJC version : {}".format(project.version()))
            if pjcverresult >= 11:
                print("**** TMG 9.02 or greater project backup reported by"
                      " pjc text file  ******")
            else:
                print("**** TMG 9.01 or earlier project backup reported by "
                      "pjc text file  ******")
                print("**** Please use the last version of TMG to upgrade "
                      "your backup and follow the advice here: ")
                print("**** https://gramps-project.org/wiki/index.php?title="
                      "Addon:TMGimporter#Before_Import_From_TMG_Backup_file  "
                      "******")
                tmgabortimport = True   # Report import stopped
                return
            # load DBF Tables
            pathtodbfs = os.path.split(pjcfilelocation)
            projecttables = TmgTable(pathtodbfs[0] + os.sep)
            tablesdbf = projecttables.tablemap()
            map_dbfs_to_tables(projecttables.tablemap())

            #--------------------------------
            #TMG Dataset to use
            # Detect if TMG project file contains more than one dataset and
            # allows selection

            # get list of datasets in (D.dbf) for combo box if more than one
            # dataset
            print("only_has_one_dataset() = ", only_has_one_dataset())
            # check if running from cli (see: importgedcom.py)
            if not only_has_one_dataset() and user.uistate:
                print("GUI running show dialog libtmg.glade")
                top = Glade()
                liststore = top.get_object('liststore1')
                # Add list of Datasets from TMG Project
                datasetchoice = datasets()
                print("All datasets()", datasets())  # list all datasets
                for datasetrow in datasetchoice.items():
                    liststore.append((str(datasetrow[1][0]),
                                      str(datasetrow[1][1])))
                # Which row is selected in the list
                treeview1 = top.get_object('treeview1')
                treeview1.get_selection().connect("changed", on_changed)
                #TODO connect help / cancel & import tmg buttons
                window = top.get_object('tmgimporterwindow')
                dialog = top.toplevel
                dialog.set_transient_for(user.uistate.window)
                #print(dir(dialog))
                dialog.show_all()
                #dialog.run()
                #TODO return selected data set from on_changed?
                # shows but with error! NameError: name 'selecteddataset'
                # is not defined
                #tmg_dataset = selecteddataset

                dialog.destroy()

                # select first dataset in a multidataset backup if on cli
                #only_first_dataset()
                #TODO remove this when gui fixed
                #user_dsid = input("Selected TMG file has multiple datasets. "
                #                  "Please select one to import? ")
                #print("You selected dataset = ", user_dsid)
                # select the first dsid number from the dataset table
                #tmg_dataset = datasetchoice[int(user_dsid)][0]
            elif only_has_one_dataset():
                print("Only one Dataset found.")
                # if true get the dsid of the dataset
                # not alway "1" especially when you delete and renumber
                # datasets like myself
                # {1: (1, 'blank / My Data Set', False, True)}
                # use first dataset in (D.dbf) eg
                datasetchoice = datasets()  # TODO fix this wrong result
                user_dsid = 0  # only choice #TODO fix this wrong result
                # select the dsid number from the dataset table
                #TODO fix this wrong result
                #tmg_dataset = datasetchoice[int(user_dsid)][0]
            else:
                #No dataset available then stop
                LOG.warn("No TMG datasets available!")
                return
###############################################################################
            #Process TMG Project for import
            #------------------------------------------------------
            print("Not working yet")
            #trial_people(database, tmg_dataset)  # test import of names
            #trial_events(database, tmg_dataset)  # test import of events

            ####-------Processing order----
            #TODO split to own function or class "TMGParser(dbase, user, ...)"
            # see below
            #[1] notes
            #[2] events
            #[3] people
            #[4] families(relationships)
            #[5] repositories
            #[6] sources
            #[7] citations
            #[8] place
            #[9] media

            #[] ImportInfo report errors etc

            #------------------------------------------------------
            #TODO option to tag source on import.

    else:
        print("%%%%%%%% invalid tmg")  # log message and exit import
        return
    return

#-------------------------------------------------------------------------
#
#
#-------------------------------------------------------------------------


def sqz_pjc_exist(sqzfiletocheck):
    '''
    Test if SQZ file is a valid TMG Backup file and contains
    * PJC file  and warn if older TMG file backup

    Returns:  True or False
    '''
    zip = zipfile.ZipFile(sqzfiletocheck)
    pjcfile = zip.namelist()
    validtmgfile = None
    for x in pjcfile:
        # Check backup contains valid Project Config or Version control file
        # *.VER - Version Control File (v0.x to v1.2a)
        # *.TMG - Version Control File (v2.0 to v4.0d)
        # *.PJC - TMG Project Configuration File (v5.0 to v9.05)
        if(x.endswith('.PJC') or x.endswith('.pjc') or
           x.endswith('.tmg') or x.endswith('.VER')):
            #TODO if tmg or ver  mention older valid tmg backup not supported
            # by tmg import addon
            #TODO "Please upgrade the TMG database format using the TMG 9.05
            # trial version and creating a new TMG backup file"
            validtmgfile = True
        else:
            validtmgfile = False
        if validtmgfile is True:
            break
    if validtmgfile is False:
        return False
    # print content of valid file
    try:
        _data = zip.read(x)
    except KeyError:
        print('ERROR: Did not find %s in zip file' % sqzfiletocheck)
    else:
        print(x, ':')
    return True

#-------------------------------------------------------------------------
#
#
#-------------------------------------------------------------------------


def check_dbf_lowercase(sqzfiletocheck):
    '''
    Check if all the DBF file extensions are lowercase otherwise
    DBF.pypi does not work!

    Returns: True or False

    Count how many files end with *.DBF (Uppercase) and *.dbf (Lowercase)
    '''
    zip = zipfile.ZipFile(sqzfiletocheck)
    pjcfile = zip.namelist()

    otherfiles = 0
    dbfuppercase = 0
    dbflowercase = 0
    dbftotalfiles = 0
    rename_needed = None

    for extension in pjcfile:
        if extension.endswith('.DBF') or extension.endswith('.dbf'):
            dbftotalfiles += 1
            if extension.endswith('.DBF'):
                dbfuppercase += 1
            elif extension.endswith('.dbf'):
                dbflowercase += 1
        else:
            otherfiles += 1  # file not does not end in dbf

    if dbflowercase != dbftotalfiles:
        rename_needed = True
        #TODO to rename use:   os.rename(sourcefile, destfile)
        # Copy DBF & FPT files to lowercase in temp folder
        #Minimal files need by TMG Importer
        #TODO (TMG 5.x or greater) DBF, FPT, PJC
        #?? (TMG 4.x) DBF, FPT, MEM, TMG, DOC
    else:
        rename_needed = False
    return rename_needed

#-------------------------------------------------------------------------
#
#
#-------------------------------------------------------------------------


def extractsqz(sqzfilename, tmpdirname):
    '''
    Extract SQZ files to tmpdirname
    '''
    with zipfile.ZipFile(sqzfilename) as zf:
        zf.extractall(tmpdirname)

    #print("TMG backup file extracted to: ", tmpdirname)

    return

#-------------------------------------------------------------------------
#
#
#-------------------------------------------------------------------------


def find_file_ext(fileext2find, tmpdirname):
    '''
    Find file
    '''
    found = None

    for root, _dirs, files in os.walk(tmpdirname):
        for name in files:
            if(name.endswith(fileext2find.lower()) or
               name.endswith(fileext2find)):
                print(os.path.abspath(os.path.join(root, name)))
                found = os.path.abspath(os.path.join(root, name))

    path2filename2find = found

    return path2filename2find

#-------------------------------------------------------------------------
#
#
#-------------------------------------------------------------------------


def rename_files_lowercase(pjcfolder):
    '''
    Rename files in folder to lowercase
    '''
    for _i, filename in enumerate(os.listdir(pjcfolder)):
        #print(_i, filename)
        src = os.path.join(pjcfolder, filename)
        dest = os.path.join(pjcfolder, filename.lower())
        os.rename(src, dest)

    return

#-------------------------------------------------------------------------
#
# (based on importgpkg.py)
#
#-------------------------------------------------------------------------


def MediaSqzExtract(database, filename, user):  # dsid media to extract
    """
    Function called by Gramps to extract TMG Media/Exhibits by Dataset number.
    """
    mediastatus = None

    oldmediapath = database.get_mediapath()
    # Use home dir if no media path
    my_media_path = media_path(database)
    media_dir = "%s.media" % os.path.basename(filename)
    tmpdir_path = os.path.join(my_media_path, media_dir)
    if not os.path.isdir(tmpdir_path):
        try:
            print("create media directory", tmpdir_path)
            # create directory for extracted TMG media files
            # os.mkdir(tmpdir_path, 0o700)
        except:
            user.notify_error(_("Could not create media directory %s") %
                              tmpdir_path)
            return
    elif not os.access(tmpdir_path, os.W_OK):
        user.notify_error(_("Media directory %s is not writable") %
                          tmpdir_path)
        return
    else:
        # mediadir exists and writable -- User could have valuable stuff in
        # it, have him remove it!
        user.notify_error(_("Media directory %s exists. Delete it first, then"
                          " restart the import process") % tmpdir_path)
        return
    try:
        #TODO extract External TMG media files here
        #
        #  Note that the PJC file contains the default mediapath stored in
        #   [Advanced][ImageDirectory=...]
        #  if more than one dataset is involved check each files Dataset ID is
        #  valid before extracting
        #
        #TODO TMG Media files may also be internal Exhibits if so no media
        # will be extracted here!
        #TODO see libtmg.py to extract internal exhibits from the
        # "Exhibits Tables" [I.DBF & I.FPT])
        #TODO or provide a warning they are internal exhibits and to use
        # John Cardinals TMGUtil to
        # "Export Images" and convert internal images to external images then
        # make a new TMG Backup(*.SQZ) file
        # consider a donation to Johns favorite charity.
        # http://www.johncardinal.com/tmgutil/
        # http://www.johncardinal.com/tmgutil/toc.htm
        # http://www.johncardinal.com/tmgutil/exportimages.htm

        print("#TODO extract TMG media files here")
        #archive = tarfile.open(name)
        #for tarinfo in archive:
        #    archive.extract(tarinfo, tmpdir_path)
        #archive.close()
    except:
        user.notify_error(_("Error extracting into %s") % tmpdir_path)
        return
    ###################################################################
    newmediapath = database.get_mediapath()
    #import of gpkg should not change media path as all media has new paths!
    if not oldmediapath == newmediapath:
        database.set_mediapath(oldmediapath)

    # Set correct media dir if possible, complain if problems
    if oldmediapath is None:
        database.set_mediapath(tmpdir_path)
        user.warn(_("Base path for relative media set"),
                  _("The base media path of this Family Tree has been set to "
                    "%s. Consider taking a simpler path. You can change this "
                    "in the Preferences, while moving your media files to the "
                    "new position, and using the media manager tool, option "
                    "'Replace substring in the path' to set"
                    " correct paths in your media objects."
                    ) % tmpdir_path)
    else:
        user.warn(_("Cannot set base media path"),
                  _("The Family Tree you imported into already has a base media "
                    "path: %(orig_path)s. The imported media objects however "
                    "are relative from the path %(path)s. You can change the "
                    "media path in the Preferences or you can convert the "
                    "imported files to the existing base media path. You can "
                    "do that by moving your media files to the "
                    "new position, and using the media manager tool, option "
                    "'Replace substring in the path' to set"
                    " correct paths in your media objects."
                    ) % {'orig_path': oldmediapath, 'path': tmpdir_path})

    return mediastatus

#-------------------------------------------------------------------------
#
# for dbman.py  (use to potentially select dataset?)
# using a list of datasets show them in a table and allow selection for
# import
#-------------------------------------------------------------------------


class Information(ManagedWindow):

    def __init__(self, uistate, data, parent):
        super().__init__(uistate, [], self)
        self.window = Gtk.Dialog()
        self.set_window(self.window, None, _("Database Information"))
        self.window.set_modal(True)
        self.ok = self.window.add_button(_('_OK'), Gtk.ResponseType.OK)
        self.ok.connect('clicked', self.on_ok_clicked)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_default_size(600, 400)
        s = Gtk.ScrolledWindow()
        titles = [
            (_('Setting'), 0, 150),
            (_('Value'), 1, 400)
        ]
        treeview = Gtk.TreeView()
        model = Gtk.ListModel(treeview, titles)
        for key, value in sorted(data.items()):
            model.add((key, str(value),), key)
        s.add(treeview)
        self.window.vbox.pack_start(s, True, True, 0)
        if parent:
            self.window.set_transient_for(parent)
        self.show()

    def on_ok_clicked(self, obj):
        self.window.close()

    def build_menu_names(self, obj):
        return (_('Database Information'), None)

#-------------------------------------------------------------------------
#
# TMG Parser - #TODO WIP
#
#-------------------------------------------------------------------------


class TMGParser(object):
    """Class to read data in TMG DBF data from a file object."""
    def __init__(self, dbase, user, default_tag_format=None):
        self.db = dbase
        self.user = user
        pass

    def parse(self, filehandle):  # filehandle will refer to the TMG dbf
        """
        Prepare the database and parse the input file.

        :param filehandle: open file handle positioned at start of the file
        """
        pass

    def _parse_dataset(self):
        "Identify and select the correct TMG Dataset - DSID"
        pass

    def _parse_note(self):
        "Note Fields in assorted Tables"
        pass

    def _parse_event(self):
        "TMG Event Table"
        pass

    def _parse_person(self):
        "TMG Person Table."
        pass

    def _parse_family(self):
        "TMG Parent/Child Relationship File"
        pass

    def _parse_repository(self):
        "TMG Repository File"
        pass

    def _parse_place(self):
        "TMG Place File"
        pass

    def _parse_citation(self):
        "TMG Citation File"
        pass

    def _parse_source(self):
        "TMG Source File"
        pass

    def _parse_media(self):
        "TMG Exhibt File - Media"
        pass

    def _parse_tags(self):
        "TMG Fields in assorted Tables"
        pass

    def _parse_np_style(self):
        "TMG Style File = Name & Place Style Templates"
        pass

    def _parse_tag_type(self):
        '''
        TMG Tag Type File - Like Event types in Gramps
        and not the same as Gramps idea of Tags for that see "_parse_tags"
         '''
        pass

    def _parse_focus_group(self):
        '''TMG Focus Group  - Don't believe Gramps has equivalent in Gramps
           - similar to saved named lists of filtered people
        '''
        pass

    def _parse_timeline(self):
        "TMG Time Lock File - History events locked against individuals"
        pass

    def _parse_dna(self):
        "TMG DNA File"
        pass

    def _parse_excluded_pair(self):
        '''
        TMG Excluded Pair File - People who have been marked "Not Duplicate"
        for TMG's "Check Duplicate People" tool
        '''
        pass

#------------------------------------------------------------------------
#
#  TMG parse_date
#
#------------------------------------------------------------------------

'''
Parse and display TMG Date format & Convert to Gramps Date Object.
'''
'''
Special Field Values
====================

Dates
=====
Date fields contain a structured value as follows:

--------------------------------------------------
Irregular Dates
--------------------------------------------------
Position | Value    | Meaning
--------------------------------------------------
   1     |  “0”     | Irregular date code
--------------------------------------------------
  2-30   | (text)   | Irregular date value
--------------------------------------------------
Regular Dates
--------------------------------------------------
Position | Value    | Meaning
--------------------------------------------------
   1     |  “1”     | Regular date code
--------------------------------------------------
  2-9    |“YYYYMMDD”| Regular date value
--------------------------------------------------
   10    |   “0”    | Not Old Style
         |   “1”    | Old Style
--------------------------------------------------
   11    |   “0”    | Before date
         |   “1”    | Say date
         |   “2”    | Circa date
         |   “3”    | Exact date
         |   “4”    | After date
         |   “5”    | Between date
         |   “6”    | Or date
         |   “7”    | From…to date
--------------------------------------------------
  12-19  |“00000000”| Used for before, say,
         |          | circa, exact, and after
         |          | dates.
--------------------------------------------------
         |“YYYYMMDD”| Second date for between,
         |          | or, and from/to dates.
--------------------------------------------------
   20    |   “0”    | Used for before, say,        # Missing
         |          | circa, exact, and after      #(Not old style date 2)
         |          | dates.
.................................................. # Missing
         |   "1"    | Old style date 2             # Missing
--------------------------------------------------
  21     |   “0”    | No question mark
         |   “1”    | Question mark
--------------------------------------------------
  22-30  |(reserved)| (reserved)
--------------------------------------------------

Date Examples:
--------------------------------------------------
Stored as                   | Displayed As
--------------------------------------------------
“0Third Monday in January”  | “Third Monday in January”
--------------------------------------------------
“119610924000000000000   ”  | “Before 09 Sep 1961”
--------------------------------------------------
“117120100130000000000   ”  | “Jan 1712/13”
--------------------------------------------------
“119420000051943000000   ”  | “Between 1942 and 1943”
--------------------------------------------------
“100000000030000000000   ”  |(empty date)
--------------------------------------------------
Page: 22
The Master Genealogist (TMG) - File Structures for v9
Last Updated: July 2014
COPYRIGHT © 2014, Wholly Genes, Inc. All Rights Reserved.
Filename: TMG9_file_structures.rtf
URL: http://www.whollygenes.com/forums201/index.php?
/topic/381-file-structures-for-the-master-genealogist-tmg/
'''
#TODO Convert to Gramps Date.set() [gramps.gen.lib.DateObjects]
#TODO Convert Gramps Date back to TMG Date for Export to TMG 9.05
#TODO from gramps.gen.datehandler import parser as _dp
#TODO _dp.parse(parse_date)  # Parses the text, returning a Date object.
#TODO https://gramps-project.org/docs/date.html
#     gramps.gen.datehandler._dateparser.DateParser.parse
#------------------------------------------------------------------------
#
#  TMG parse_date Helper function
#
#------------------------------------------------------------------------


def num_to_month(convertmonth):
    '''
    Pass a two digit tmg month string in the form
    of MM and return Mmm (eg: 09 => Sep)
    '''
    convertmonth = int(convertmonth)
#    longmonth = calendar.month_name[convertmonth]
    shortmonth = calendar.month_abbr[convertmonth]
    return shortmonth

#------------------------------------------------------------------------
#
#  TMG parse_date Helper function
#
#------------------------------------------------------------------------


def num_to_date(convertdate):
    '''
    Pass a 8 digit tmg string in the form of YYYYMMDD and return DD Mmm YYYY
    (eg: 20130920 => 20 Sep 2013)
    '''
    convertdate = convertdate
    YYYY, MM, DD = convertdate[0:4], convertdate[4:6], convertdate[6:8]
    dd1 = int(DD)
    mm1 = int(MM)
    yyyy1 = int(YYYY)

    mm2 = num_to_month(int(MM))

    # 000 if each field has no value return None
    if (dd1 <= 0) and (mm1 <= 0) and (yyyy1 <= 0):
        # return a blank field ""? or None? was '(empty date)'
        return

    # 001 display only the year
    if ((dd1 <= 0) and (mm1 <= 0)) and (yyyy1 > 0):
        shortdate = "{}".format(YYYY)
        return shortdate

    # 010 display only the month
    if ((dd1 <= 0) and (yyyy1 <= 0)) and (mm1 > 0):
        mm1date = "{}".format(mm2)
        return mm1date

    # 100 display only the day
    if ((mm1 <= 0) and (yyyy1 <= 0)) and (dd1 > 0):
        dd1date = "{}".format(dd1)
        return dd1date

    # 011 display only the month and year
    if ((mm1 > 0) and (yyyy1 > 0)) and (dd1 <= 0):
        mm1yyyy1date = "{} {}".format(mm2, YYYY)
        return mm1yyyy1date

    # 110 display only the day and month
    if ((dd1 > 0) and (mm1 > 0)) and (yyyy1 <= 0):
        dd1mm1date = "{} {}".format(dd1, mm2)
        return dd1mm1date

    # 111 If each field has a value return a full date
    if ((dd1 > 0) and (mm1 > 0) and (yyyy1 > 0)):
        fulldate = "{} {} {}".format(DD, mm2, YYYY)
        return fulldate

    return

#------------------------------------------------------------------------
#
#  TMG parse_date function
#
#------------------------------------------------------------------------


def parse_date(tmgdate):
    '''Parse TMG date string

    Usage:
    >>>parse_date("119420000051943000000")
    DISPLAY: Between 1942 and 1943
    '''
    datefieldtype = tmgdate[0]
    validdatecodes = ["0", "1"]

    if datefieldtype in validdatecodes:
        if datefieldtype == "1":
            '''Regular date code'''
            regulardate1value2_9 = tmgdate[1:9]  # "YYYYMMDD"
            is_oldstyle10 = tmgdate[9]  # "0" = No / "1" = Yes
            date2yyold = tmgdate[9:11]  # Oldstyle YY
            # Before/Say/Circa/Exact/After/Between Or/From...to
            datemodifier11 = tmgdate[10]
            validdatemodifiercodes = ["0", "1", "2", "3", "4", "5", "6", "7"]
            regulardate2value12_19 = tmgdate[11:19]  # "00000000"
            is_eightzeros = None  # rename to empty field or emptydate?
            if regulardate2value12_19 == "00000000":
                is_eightzeros = True
            else:
                is_eightzeros = False
            regulardate3value12_19 = tmgdate[11:19]  # "YYYYMMDD"
            is_oldstyledate2nd_20 = tmgdate[19]  # "0" = No / "1" = Yes
            has_questionmark21 = tmgdate[20]  # "0" = No / "1" = Yes
            questionmark = None
            if has_questionmark21 == "0":
                questionmark = ""
            else:
                questionmark = "?"
            regulardate4value22_30 = tmgdate[21:29]  # (reserved)

            if is_oldstyle10 == "0":
                if datemodifier11 in validdatemodifiercodes:
                    if datemodifier11 == "0":
                        #before_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('Before {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "1":
                        #say_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('Say {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "2":
                        #circa_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('Circa {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "3":
                        #exact_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('{}{}'.format(date1, questionmark))
                    elif datemodifier11 == "4":
                        #after_date_mod
                        if is_eightzeros:
                            date1 = num_to_date(regulardate1value2_9)
                            return ('After {}{}'.format(date1, questionmark))
                    elif datemodifier11 == "5":
                        #between_date_mod
                        date1 = num_to_date(regulardate1value2_9)
                        date2 = num_to_date(regulardate3value12_19)
                        return ('Between {} and {}{}'.format(date1, date2,
                                                             questionmark))
                    elif datemodifier11 == "6":
                        #or_date_mod
                        date1 = num_to_date(regulardate1value2_9)
                        date2 = num_to_date(regulardate3value12_19)
                        return ('{} or {}{}'.format(date1, date2,
                                                    questionmark))
                    elif datemodifier11 == "7":
                        #from_to_date_mod
                        date1 = num_to_date(regulardate1value2_9)
                        date2 = num_to_date(regulardate3value12_19)
                        return ('From {} to {}{}'.format(date1, date2,
                                                         questionmark))
                else:
                    # Invalid issue with database?
                    return(tmgdate,
                           "Invalid datemodifier11: ----------{}"
                           "----------".format(datemodifier11))
            elif is_oldstyle10 == "1":
                date1 = num_to_date(regulardate1value2_9)
                YYold2 = date2yyold
                return ('{}/{}{}'.format(date1, YYold2, questionmark))
        elif datefieldtype == "0":
            '''Irregular date code'''
            irregulardatevalue = tmgdate[1:29]
            return irregulardatevalue
    else:
        # Invalid issue with database?
        return(tmgdate,
               "Invalid datefieldtype: {}"
                "--------------------".format(datefieldtype))
#------------------------------------------------------------------------
#
#  TMG parse_date function - End
#
#------------------------------------------------------------------------

#------------------------------------------------------------------------
#
#  The Master Genealogist (TMG) Backup File 'SQZ' reader and extracter
#
#------------------------------------------------------------------------


#TODO have gramps. import the function to read the sqz

"The Master Genealogist (TMG) Backup File 'SQZ' reader and extracter"


#-------------------------------------------------------------------------
#
# TmgExtractSQZ function
#
#-------------------------------------------------------------------------
def TmgExtractSQZ(tmgsqzfilename):  # TODO split into seperate functions
    """
    Open a TMG SQZ file

    test sqz

    then extract all the files to a temp directory/location
    python namedtemp directory?
    """
    print("Filename:", tmgsqzfilename)

    # Open the TMG SQZ file as readonly
    try:
        # Test sqz file is a valid zipfile
        if zipfile.is_zipfile(tmgsqzfilename):
            print("Is this a Zipfile:" , zipfile.is_zipfile(tmgsqzfilename))
            with zipfile.ZipFile(tmgsqzfilename, 'r') as tmgsqz:
                # Read the SQZ files filenames and paths

                tmgsqzfilenames = tmgsqz.namelist()
                #print("namelist", tmgsqzfilenames)
                print("number of files", len(tmgsqzfilenames))

                # Check a TMG "Version Control File"(*.pjc/*.ver/*.tmg)
                # files exist in the SQZ
                # Early TMG versions used *.VER
                # TMG v4.x used *.TMG
                # TMG v5.x and higher use *.PJC
                for filename in tmgsqzfilenames:
                    if filename.endswith('.pjc') or filename.endswith('.PJC'):
                        tmgprojectfilename = filename
                        print("tmgprojectfilename:", tmgprojectfilename)
                    elif (filename.endswith('.tmg') or
                          filename.endswith('.TMG')):
                        # Present a notification message to Projects with
                        # (*.ver/*.tmg)
                        # eg:TMG v4 and earlier. That tmgimport only supports
                        # tmg versions 5.x to 9.x
                        tmgprojectfilenameold = filename
                        print("tmgprojectfilename old:", tmgprojectfilenameold)
                        return
                    elif (filename.endswith('.ver') or
                          filename.endswith('.VER')):
                        # Present a notification message to Projects with
                        # (*.ver/*.tmg)
                        # eg:TMG v4 and earlier. That tmgimport only supports
                        # tmg versions 5.x to 9.x
                        tmgprojectfilenameevenolder = filename
                        print("tmgprojectfilename even older:",
                              tmgprojectfilenameevenolder)
                        return
                    else:
                        print("Are you sure this is a tmgprojectfilename? "
                              "if so contact me.")
                        return

                # Extract the found (*.pjc)  to a temporary location

                # Read the (*.pjc) contents and report TMG version it was
                # created with along with some other information.

                pjccontents = StringIO(tmgsqz.read(tmgprojectfilename))
                print(tmgprojectfilename, ':')

                # PjcVersion=10.0
                # For the TMG Program Version; subtract 1 from the PjcVersion
                # number
                for line in pjccontents:
                    if line.startswith("PjcVersion=") > 0:
                        pjcversionraw = line

                print("TMG pjc version - pjcversionraw", pjcversionraw)
                pjcversionraw2 = pjcversionraw.rsplit('\r\n')
                print("TMG pjc version - pjcversionraw2", pjcversionraw2)
                pjcversionraw3 = pjcversionraw2[0].rsplit('=')
                print("TMG pjc version - pjcversionraw3", pjcversionraw3)
                pjcversion = pjcversionraw3[1]
                pjcversion = int(float(pjcversion) - 1)
                print("TMG pjc version", pjcversion)

                # CreateDate=20140208
                # CreateTime=09:10:22 AM
                # LastIndexed=02/08/2014
                # LastVFI=02/08/2014
                # LastOptimized=02/08/2014

                # Check the TMG Project's "Data Sets"
                # Read the Table > _D.dbf fields "DSID & DSNAME"
                # to see if contains more than one dataset
                # http://tmg.reigelridge.com/projects-datasets.htm
                # GUI = tmgdataset

                # If any of the "Data Sets" are locked indicate it.

                # GUI(importtmg.glade)

                # Present a drop down box to select only one of the TMG
                # "Data Sets" to be imported.
                # (I believe Gramps can only have one family tree open at
                # a time,
                #  and muliple dataset can not be shown in the list views
                # eglike tmgs 1:23, 2:13)

                # Test the TMG SQZ for Internal exhibits
                # http://tmg.reigelridge.com/exhibits.htm
                # Mention that: John Cardinal's TMG Utility will
                # convert internal exhibits to external...
                # see http://www.johncardinal.com/tmgutil/
                # In TMG Utility, try the Other->Export Data option and select
                # Exhibit Log;
                # after you've chosen where to save it, you'll be prompted;
                # http://www.johncardinal.com/tmgutil/exportimages.htm#task1

        else:
            # Display an informational popup
            # http://www.whollygenes.com/forums201/index.php?
            #/topic/14299-opening-old-sqz-files/?p=57594
            # Early TMG versions used the FoxPro SQZ file as a backup archive
            # and this is not a ZIP file.
            # If the file came from TMG prior to v5, in a trial version of
            # TMG you should try import, not restore. File / Import
            # Select 'The Master Genealogist v4.x or earlier BACKUP (*.SQZ)'.
            # That may or may not work.
            # If the SQZ came from an early version of TMG, you might need to
            # talk to Whollygenes  Support and they will want to examine the
            # file.
            # There are also other genealogy databases that used the .SQZ
            # file extension:
            # Family Gathering, Roots IV, Roots V, Ultimate Family Tree,
            # Visual Roots.
            print(tmgsqzfilename, "is not a TMG SQZ file or \
                  was created in TMG version 4.x or earlier")
            return
    except IOError:
        return
#------------------------------------------------------------------------
#
#  TMG Backup File 'SQZ' reader and extracter
#  END
#------------------------------------------------------------------------


#------------------------------------------------------------------------
#
# TMG DBF tables  # TODO redo table code framework below
#
#------------------------------------------------------------------------
'''
All TMG DBF Tables
'''
#------------------------------------------------------------------------
#
#  Person File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
$.DBF - tmgPeople - Person File
'''


#------------------------------------------------------------------------
#
#  Source Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
A .dbf - tmgSourceCategories - Source Type File
'''


#------------------------------------------------------------------------
#
#  Focus Group Members
##TODO
#------------------------------------------------------------------------
'''

Table:
B .dbf - tmgFocusGroupMembers - Focus Group Member File
'''


#------------------------------------------------------------------------
#
#  Flag File
##TODO
#------------------------------------------------------------------------
'''

Table:
C.DBF - tmgCustomFlags - Flag File
'''


#------------------------------------------------------------------------
#
#  Data Set File
##TODO
#------------------------------------------------------------------------
'''

Table:
D .dbf - tmgDataSets - Data Set File
'''
'''
Fields:
-----------------------------
 0 - dsid      : 8                 # DataSet ID# (Primary key)
 1 - dsname    : u'Royal92 import' # DataSet Name
 2 - dslocation: u'royal92.ged'    # Original Import location
 3 - dstype    : 1                 # Import type
 4 - dslocked  : False             # Is DataSet Locked
 5 - dsenabled : True              # Is DataSet Enabled
 6 - property  : u''               #
 7 - dsp       : u''               #
 8 - dsp2      : u''               # Only in TMG 8 +
 9 - dcomment  : u'A comment here' # DataSet Comment
10 - host      : u''               #
11 - namestyle : 0                 # Default name style for this dataset
                                     Relates to st.styleid(ST.DBF).
12 - placestyle: 0                 # Default place style for this dataset
                                     Relates to st.styleid(ST.DBF).
13 - tt        : u' '              #
-----------------------------
'''


def d_dbf():
    with tmgDataSets:
        d_fields = {}
        print(tmgDataSets.fields)
        print(tmgDataSets.field_count)
        print(tmgDataSets.record_count)
        return d_fields


#------------------------------------------------------------------------
#
#  DNA
##TODO
#------------------------------------------------------------------------
'''

Table:
dna.dbf - tmgDNAinformation - DNA File
'''


#------------------------------------------------------------------------
#
#  Event Witness File
##TODO
#------------------------------------------------------------------------
'''

Table:
E.DBF - tmgParticipantsWitnesses -Event Witness File
'''


#------------------------------------------------------------------------
#
#  Parent/Child Relationship
##TODO
#------------------------------------------------------------------------
'''

Table:
F .dbf - tmgParentChildRelationships - Parent/Child Relationship
'''


#------------------------------------------------------------------------
#
#  Event File
##TODO
#------------------------------------------------------------------------
'''

Table:
G.DBF - tmgEvents - Event File
'''


#------------------------------------------------------------------------
#
#  Exhibits
##TODO
#------------------------------------------------------------------------
'''

Table:
I .dbf - tmgExhibits - Exhibit File
'''


#------------------------------------------------------------------------
#
#  Timeline
##TODO
#------------------------------------------------------------------------
'''

Table:
K .dbf - tmgTimelineLocks - Timeline Lock File
'''


#------------------------------------------------------------------------
#
#  Research Tasks
##TODO
#------------------------------------------------------------------------
'''

Table:
L .dbf - tmgResearchTasks - Research Log File
'''

#------------------------------------------------------------------------
#
#  Source File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
M .dbf - tmgSources - Source File
'''


#------------------------------------------------------------------------
#
#  Name File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
N.DBF - tmgNames - Name File
'''


#------------------------------------------------------------------------
#
#  Name Dictionary File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
ND.DBF - tmgNameDictionary - Name Dictionary File
'''


#------------------------------------------------------------------------
#
#  Name Part Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
NPT.DBF - tmgNamePartType - Name Part Type File
'''


#------------------------------------------------------------------------
#
#  Name Part Value File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
NPV.DBF - tmgNamePartValue - Name Part Value File
'''


#------------------------------------------------------------------------
#
#  Focus Groups
##TODO
#------------------------------------------------------------------------
'''

Table:
O .dbf - tmgFocusGroups - Focus Group File
'''


#------------------------------------------------------------------------
#
#  Place File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
P.DBF - tmgPlaces - Place File
'''


#------------------------------------------------------------------------
#
#  Place Dictionary File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
PD.DBF - tmgPlaceDictionary - Place Dictionary File
'''


#------------------------------------------------------------------------
#
#  Place Part Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
PPT.DBF - tmgPlacePartType - Place Part Type File
'''


#------------------------------------------------------------------------
#
#  Place Part Value File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
PPV.DBF - tmgPlacePartValue - Place Part Value File
'''


#------------------------------------------------------------------------
#
#  Repository File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
R .dbf - tmgRepositories - Repository File
'''


#------------------------------------------------------------------------
#
#  Source Citation File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
S .dbf - tmgCitations - Source Citation File
'''


#------------------------------------------------------------------------
#
#  Style File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
ST.DBF - tmgStyles - Style File
'''


#------------------------------------------------------------------------
#
#  Tag Type File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
T.DBF - tmgTagTypes - Tag Type File
'''


#------------------------------------------------------------------------
#
#  Source Element File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
U .dbf - tmgSourceComponents - Source Element File
'''


#------------------------------------------------------------------------
#
#  Repository Link File
##TODO
#------------------------------------------------------------------------
'''

Table(s):
W .dbf - tmgSourceRepositoryLinks - Repository Link File
'''


#------------------------------------------------------------------------
#
#  Excluded Pair File
##TODO
#------------------------------------------------------------------------
'''

Table:
XD .dbf - tmgExcludedDuplicates - Excluded Pair File
'''


############################################################
# Testing (#TODO: move to seperate file and expand)
############################################################
#if __name__ == '__main__':
#    pass
