#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017 Sam Manzi
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
# python modules
#
#------------------------------------------------------------------------
import os
import glob
#import sys
import configparser
import zipfile
import tempfile

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".TMGImport")

#------------------------------------------------------------------------
#
# External Libraries
#
#------------------------------------------------------------------------
from dbf import Table

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
from gramps.gui.managedwindow import ManagedWindow
from gramps.gen.db import DbTxn
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
#from gramps.gui.glade import Glade
from gramps.gen.utils.file import media_path

#from gramps.gen.utils.libformatting import ImportInfo
from gramps.gen.lib import (Name, NameType, Person, Event)

#------------------------------------------------------------------------
#
# TMG Importer - Support Libraries
#
#------------------------------------------------------------------------
from .libtmgdate import parse_date

#------------------------------------------------------------------------
#
# #TODO get rid of globals
#
#------------------------------------------------------------------------

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
# Utilties
#
#------------------------------------------------------------------------


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
# TMG Project management of tables etc (read PJC)
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
        '''
        config = configparser.ConfigParser()
        config.read(self.tmgproject)
        version = config['Stamp']['PjcVersion']
        return 'TMG Project type: {}'.format(version)

    def researcher(self):  #TODO Use to populate Gramps Researcher
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
        #print('Project path =:',tmgproject[0])
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

        #(0, 'TMG backup file (SQZ)', 1, 'TMG Project Configuration File (PJC)', 29, 'FoxPro Database Files (DBF)', 18, 'Foxpro Memo Files (FPT)', 0, 'Foxpro Structural Compound Index Files (CDX)', 0, 'TMG Log File (LOG)', 87, 'all files in directory provided')
        summaryfiles = sqzfiles + pjcfiles + dbffiles + \
            fptfiles + cdxfiles + logfiles + allfiles

        _summaryfiles = ''
        for datum in range(0, len(summaryfiles), 2):
            #print('{:>8}|{}'.format(summaryfiles[datum], summaryfiles[datum + 1]))
            _summaryfiles = _summaryfiles + \
                '{:>7}|{}\n'.format(
                    summaryfiles[datum],
                    summaryfiles[datum + 1])

        return ('\n######File Summary########\nNumber |Usage (Type)\n{}'.format(
                _summaryfiles))

#------------------------------------------------------------------------
##TODO
# Identify TMG DBF version by table names
#
#------------------------------------------------------------------------
'''
Test TMG DBF fields exist in Tables to determine/verify TMG Project file version
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

    # only works if you pass a pjc
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
        ignore_memos=True,
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
            'tmgPeople': ('_$.dbf',
                          ''),
            'tmgSourceCategories': ('_a.dbf',
                                    ''),
            'tmgFocusGroupMembers': ('_b.dbf',
                                     ''),
            'tmgCustomFlags': ('_c.dbf',
                               ''),
            'tmgDataSets': ('_d.dbf',
                            ''),
            'tmgDNAinformation': ('_dna.dbf',
                                  ''),
            'tmgParticipantsWitnesses': ('_e.dbf',
                                         ''),
            'tmgParentChildRelationships': ('_f.dbf',
                                            ''),
            'tmgEvents': ('_g.dbf',
                          ''),
            'tmgExhibits': ('_i.dbf',
                            ''),
            'tmgTimelineLocks': ('_k.dbf',
                                 ''),
            'tmgResearchTasks': ('_l.dbf',
                                 ''),
            'tmgSources': ('_m.dbf',
                           ''),
            'tmgNames': ('_n.dbf',
                         ''),
            'tmgNameDictionary': ('_nd.dbf',
                                  ''),
            'tmgNamePartType': ('_npt.dbf',
                                ''),
            'tmgNamePartValue': ('_npv.dbf',
                                 ''),
            'tmgFocusGroups': ('_o.dbf',
                               ''),
            'tmgPlaces': ('_p.dbf',
                          ''),
            'tmgPlaceDictionary': ('_pd.dbf',
                                   ''),
#            'tmgPicklist': ('_pick1.dbf',
#                            ''),
            'tmgPlacePartType': ('_ppt.dbf',
                                 ''),
            'tmgPlacePartValue': ('_ppv.dbf',
                                  ''),
            'tmgRepositories': ('_r.dbf',
                                ''),
            'tmgCitations': ('_s.dbf',
                             ''),
            'tmgStyles': ('_st.dbf',
                          ''),
            'tmgTagTypes': ('_t.dbf',
                            ''),
            'tmgSourceComponents': ('_u.dbf',
                                    ''),
            'tmgSourceRepositoryLinks': ('_w.dbf',
                                         ''),
            'tmgExcludedDuplicates': ('_xd.dbf',
                                      '')}

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
      0 - dsid      : 8                                 # DataSet ID# (Primary key)
      1 - dsname    : u'sample / Royal92 - 2nd import'  # DataSet Name
      2 - dslocation: u'royal92.ged'                    # Original Import location
      3 - dstype    : 1                                 # Import type
      4 - dslocked  : False                             # Is DataSet Locked
      5 - dsenabled : True                              # Is DataSet Enabled
      6 - property  : u''
      7 - dsp       : u''
      8 - dsp2      : u''
      9 - dcomment  : u'A comment is here sometimes'    # DataSet Comment
     10 - host      : u''
     11 - namestyle : 0                                 # Default name style for this dataset Relates to st.styleid(ST.dbf).
     12 - placestyle: 0                                 # Default place style for this dataset Relates to st.styleid(ST.dbf).
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
                                     record.dsp2, record.dcomment.rstrip(), \
                                     record.host.rstrip(), record.namestyle, \
                                     record.placestyle, record.tt.rstrip()
    '''
    All datasets() = {0: (1, 'TMG Sample Data Set', 'C:\\MYDATA\\SAMPLE',
                      1, False, True, '', '', '', '', '', 0, 0, ''),
                      1: (2, 'sample / Royal92 - 1st import', 'royal92.ged',
                      1, True, True, '', '', '', '', '', 0, 0, ''),
                      2: (8, 'sample / Royal92 - 2nd import', 'royal92.ged',
                      1, False, True, '', '', '', '', '', 0, 0, ''),
                      3: (9, 'sample / Royal92 - 3rd import', 'royal92.ged',
                      1, False, False, '', '', '', '', '', 0, 0, '')}
    '''

    return alldatasets


def only_one_dataset():
    '''
    Returns true if only one Dataset in Project
    '''
    datasets_total = len(datasets())
    print("datasets_total = ", datasets_total)

    if datasets_total > 1:
        print("datasets_total = ", datasets_total)
        return False

    return True

#-------------------------------------------------------------------------
#
#
# trial of dbf fields from Datasets table
#
#-------------------------------------------------------------------------


def trial_d_dbf():
    '''
    Trial All TMG DBF Tables (Fields & Info)

    '''
    with tmgPeople:
        t = tmgPeople
        print("Version:\n",t.version)
        print("Filename:\n",t.filename)
        print("Memoname:\n",t.memoname)
        print("Field names:\n",t.field_names)
        print("Total Field count:\n",t.field_count)
        print("Last update:\n",t.last_update)
        print("Codepage:\n", t.codepage)
        print("Status:\n", t.status)
        print("Structure:\n", t.structure)
        print("Supported_tables:\n", t.supported_tables)
        print("First record:\n",t.first_record)
        print("Last record:\n",t.last_record)
        print()
        count = 0
        for record in tmgPeople:
            if record.dsid == 9:
                person = record.per_no
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
    for x in (tmgPeople, tmgSourceCategories, tmgFocusGroupMembers, \
            tmgCustomFlags, tmgDataSets, tmgDNAinformation, tmgParticipantsWitnesses, \
            tmgParentChildRelationships, tmgEvents, tmgExhibits, tmgTimelineLocks, \
            tmgResearchTasks, tmgSources, tmgNames, tmgNameDictionary, tmgNamePartType, \
            tmgNamePartValue, tmgFocusGroups, tmgPlaces, tmgPlaceDictionary, tmgPlacePartType, \
            tmgPlacePartValue, tmgRepositories, tmgCitations, tmgStyles, tmgTagTypes, \
            tmgSourceComponents, tmgSourceRepositoryLinks, tmgExcludedDuplicates):
        print("*****************************************************************")
        print(x, x.field_names)
        print("*****************************************************************")
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
                if record.dsid == None:
                    return
                else:
                    tmg_people_in_dataset.append(record.per_no)

    #------------------------------------
    ## get each persons name
    #------------------------------------
    with tmgNames:
        tmg_people_named = {}
        for record in tmgNames:
            if (record.dsid == tmg_dataset) and (record.primary == True):
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
        #person = Person.create(Person.from_struct(data))  ##<<  from_struct is gone!
        #print(Person.unserialize())
        person = Person.create(data) # ValueError: not enough values to unpack (expected 21, got 1)
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
[Event memo = [:CR:][:CR:]Frank Alexander was educated at Duffield Academy in Elizabethton and at Emory and Henry College in Washington County, Tennessee. ]
    '''
    #--------------------------------------------
    #
    #--------------------------------------------
    '''
    for tmgevent in tmg_events:
        eventtype = tmg_events[tmgevent][1]
        eventdate = tmg_events[tmgevent][4]
        eventplace = tmg_events[tmgevent][5]
        #data = {"type": {eventtype}, "date" : eventdate , "place" : eventplace, }
        data = {"date" : eventdate , "place" : eventplace}
        event = Event.create(Event.from_struct(data))
        with DbTxn("Add Event", database) as tran:
            database.add_event(event, tran)

    '''
    #--------------------------------------------
    #
    #--------------------------------------------
    pass

#-------------------------------------------------------------------------
#
# Importing data into the currently open database.                    #####See: importxml.py
# Must take care of renaming media files according to their new IDs. #### ?
#
#-------------------------------------------------------------------------


def importData(database, sqzfilename, user):

    ######Check if Gramps Family Tree is empty if not stop import
    if not database.get_total() == 0:
        #TODO pop up GUI warning for tmg import, or just exit silently?
        print("Create a New Family Tree to import your TMG Backup into. As current Family Tree has ", database.get_total(), "People")
        return
    print("Current Family Tree is empty. Excellent!! database.get_total() = ", database.get_total())

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

            #Initialize and load DBF Tables
            #TODO make this section simpler
            pjcfilelocation = find_file_ext(".PJC", tmpdirname)  # updated name for pjc after rename
            project = TmgProject(pjcfilelocation)
            pathtodbfs = os.path.split(pjcfilelocation)
            projecttables = TmgTable(pathtodbfs[0] + os.sep)
            tablesdbf = projecttables.tablemap()
            map_dbfs_to_tables(projecttables.tablemap())

            #--------------------------------
            #TMG Dataset to use
            # Detect if TMG project file contains more than one dataset and allows selection

            # get list of datasets in (D.dbf) for combo box if more than one dataset
            if not only_one_dataset() and user.uistate:  # check if running from cli (see: importgedcom.py)
                datasetchoice = datasets()
                print("All datasets()",datasets())  # list all datasets
                user_dsid = input("This TMG file has multiple datasets. Please select which one you want to import ?")  #TODO remove this when gui fixed
                print("You selected dataset = ", user_dsid)
                tmg_dataset = datasetchoice[int(user_dsid)][0]  # select the first dsid number from the dataset table
            elif only_one_dataset():
                # if true get the dsid of the dataset
                # not alway "1" especially when you delete and renumber datasets like myself
                # {1: (1, 'blank / My Data Set', False, True)}
                # use first dataset in (D.dbf) eg
                datasetchoice = datasets()
                user_dsid = 0  # only choice
                tmg_dataset = datasetchoice[int(user_dsid)][0]  # select the dsid number from the dataset table
            else:
                #No dataset available then stop
                print("no datasets available") #TODO print warning in gui
                return

##################################################################################
            #Process TMG Project for import
            #------------------------------------------------------
            print("Not working yet")
            #trial_people(database, tmg_dataset)  # test import of names
            #trial_events(database, tmg_dataset)  # test import of events

            ####-------Processing order----#TODO split to own file "TMGParser(dbase, user, ...)" see below
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
        if x.endswith('.PJC') or x.endswith('.pjc') or x.endswith('.tmg') or x.endswith('.VER'):
            #TODO if tmg or ver  mention older valid tmg backup not supported by tmg import addon
            #TODO "Please upgrade the TMG database format using the TMG 9.05 trial version and creating a new TMG backup file"
            validtmgfile = True
        else:
            validtmgfile = False
        if validtmgfile is True:
            break
    if validtmgfile is False:
        return False
    # print content of valid file
    try:
        data = zip.read(x)
    except KeyError:
        print('ERROR: Did not find %s in zip file' % filename)
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

    print("TMG backup file extracted to: ", tmpdirname)

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

    for root, dirs, files in os.walk(tmpdirname):
        for name in files:
            if name.endswith(fileext2find.lower()) or name.endswith(fileext2find):
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
    for i, filename in enumerate(os.listdir(pjcfolder)):
        #print(i, filename)
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
        #  Note that the PJC file contains the default mediapath stored in [Advanced][ImageDirectory=...]
        #  if more than one dataset is involved check each files Dataset ID is valid before extracting
        #
        #TODO TMG Media files may also be internal Exhibits if so no media will be extracted here!
        #TODO see libtmg.py to extract internal exhibits from the "Exhibits Tables" [I.DBF & I.FPT])
        #TODO or provide a warning they are internal exhibits and to use John Cardinals TMGUtil to
        # "Export Images" and convert internal images to external images then make a new TMG Backup(*.SQZ) file
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
        user.warn(
                _("Base path for relative media set"),
                _("The base media path of this Family Tree has been set to "
                    "%s. Consider taking a simpler path. You can change this "
                    "in the Preferences, while moving your media files to the "
                    "new position, and using the media manager tool, option "
                    "'Replace substring in the path' to set"
                    " correct paths in your media objects."
                  ) % tmpdir_path)
    else:
        user.warn(
                _("Cannot set base media path"),
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
        model = ListModel(treeview, titles)
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
