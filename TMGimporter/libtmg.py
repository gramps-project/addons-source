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
import re

import logging
LOG = logging.getLogger(".TMGImport")

# Minimum PJC version for TMG 9.02+ (PjcVersion >= 11.0)
MIN_PJC_VERSION = 11

#------------------------------------------------------------------------
#
# External Libraries
#
#------------------------------------------------------------------------
# Name: dbf.pypi
# https://pypi.python.org/pypi/dbf
try:
    import dbf
    if dbf.version < (0, 99, 0):
        raise ImportError(
            f"dbf >= 0.99.0 is required (found {'.'.join(str(x) for x in dbf.version)})")
    from dbf import Table
except (ImportError, ValueError) as e:
    LOG.error("For TMG Importer to work please install 'dbf >= 0.99.0' "
              "from https://pypi.python.org/pypi/dbf (%s)", e)

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
try:
    import gettext as _gettext
    import os as _os
    _localedir = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)), "locale")
    _ = _gettext.translation("addon", localedir=_localedir).gettext
except FileNotFoundError:
    _ = glocale.translation.gettext
from gramps.gen.lib import (
    Address, ChildRef,
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
#
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

    def _read_pjc_config(self):
        """Parse the PJC file into a ConfigParser, filtering out lines that
        would cause configparser to fail (malformed section headers, multi-line
        values, binary blobs).
        """
        config = configparser.ConfigParser(strict=False)
        with open(self.tmgproject, 'r', encoding='latin-1', errors='ignore') as f:
            raw = f.read()
        raw = raw.replace('\x00', '')
        cleaned_lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Only keep valid section headers [name], key=value lines,
            # and standard comment prefixes.  Lines like '[Exho' (no
            # closing bracket) are malformed TMG internal markers that
            # configparser cannot parse.
            if stripped.startswith('['):
                if ']' in stripped:
                    cleaned_lines.append(line)
                # else: malformed — skip silently
            elif stripped.startswith((';', '#')) or '=' in stripped:
                cleaned_lines.append(line)
        try:
            config.read_string('\n'.join(cleaned_lines))
        except configparser.ParsingError as exc:
            LOG.warning("PJC file parse error (partial data may be missing): %s", exc)
        return config

    def version(self):
        '''
        TMG Project Version from (.PJC)

        Usage:
        > TmgProject.version()

        Result:
        > 8.0
        '''
        config = self._read_pjc_config()
        version = config['Stamp']['PjcVersion']
        version = float(version)
        #return 'PJC version : {}'.format(version)
        return version

    def researcher(self):
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
        config = self._read_pjc_config()
        version = config['Stamp']['PjcVersion']

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
        config = self._read_pjc_config()
        version = config['Stamp']['PjcVersion']

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
        tmgproject = self.tmgproject.rsplit('/', 1)
        LOG.debug("TMG project path: %s", tmgproject[0])
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
# Identify TMG DBF version by table names
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
    global tmgtables_ext, tmgPeople, tmgSourceCategories, tmgFocusGroupMembers, \
    tmgCustomFlags, tmgDataSets, tmgDNAinformation, tmgParticipantsWitnesses, \
    tmgParentChildRelationships, tmgEvents, tmgExhibits, tmgTimelineLocks, \
    tmgResearchTasks, tmgSources, tmgNames, tmgNameDictionary, tmgNamePartType, \
    tmgNamePartValue, tmgFocusGroups, tmgPlaces, tmgPlaceDictionary, tmgPlacePartType, \
    tmgPlacePartValue, tmgRepositories, tmgCitations, tmgStyles, tmgTagTypes, \
    tmgSourceComponents, tmgSourceRepositoryLinks, tmgExcludedDuplicates

    # only works if you pass a pjc file
    if len(tablemap) == 0:
        LOG.warning("No name for the tablemap was passed: %s", tablemap)
        return
    else:
        tmgtables_ext = tablemap

    # On Linux the filesystem is case-sensitive. The dbf library derives the
    # memo file path (.fpt) directly from the .dbf filename, so a memo file
    # with a mismatched case (e.g. .FPT) won't be found.  Normalize the entire
    # DBF folder to lowercase once here so callers don't need to do it.
    _any_path = next(iter(tmgtables_ext.values()))[1]
    _folder = os.path.dirname(_any_path)
    rename_files_lowercase(_folder)
    # Update stored paths: only the filename part is renamed, not the directory
    tmgtables_ext = {
        k: (v[0], os.path.join(os.path.dirname(v[1]), os.path.basename(v[1]).lower()))
        for k, v in tmgtables_ext.items()
    }

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
            LOG.error("Failed to create DBF table mapping")

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
        LOG.debug("datasets_total = %s", datasets_total)
        return False
    else:
        LOG.debug("datasets_total = %s", datasets_total)
        return True

    return True

def only_first_dataset():
    '''
    Returns only the first Dataset number in a multi-dataset backup
    Project (used by the command line)
    '''
    first_datasetid = (datasets()[0][0])

    LOG.debug("first_datasetid = %s", first_datasetid)

    return first_datasetid

#-------------------------------------------------------------------------
#
#
# Trial of dbf fields from Datasets table
#
#-------------------------------------------------------------------------



#--------------------------------------------------------------------------
#
# people  ($.dbf) table trial  (proof of concept )
#
#--------------------------------------------------------------------------


def import_people(database, tmg_dataset):
    """Import TMG people with their primary name and gender."""
    LOG.info("TMG import people: dataset %s", tmg_dataset)

    # Collect primary name records: {nper: (givenname, surname)}
    with tmgNames:
        tmg_people_named = {}
        for record in tmgNames:
            if (record.dsid == tmg_dataset) and (record.primary is True):
                parts = record.srnamedisp.split(',', 1)
                surname  = parts[0].strip() if parts else ""
                givenname = parts[1].strip() if len(parts) > 1 else ""
                tmg_people_named[record.nper] = givenname, surname
    LOG.info("Names indexed: %s for dataset %s", len(tmg_people_named), tmg_dataset)

    # Collect gender: {per_no: Person.MALE/FEMALE/UNKNOWN}
    with tmgPeople:
        tmg_people_gender = {}
        for record in tmgPeople:
            if record.dsid == tmg_dataset:
                sex = record.sex.strip()
                if sex == 'M':
                    tmg_people_gender[record.per_no] = Person.MALE
                elif sex == 'F':
                    tmg_people_gender[record.per_no] = Person.FEMALE
                else:
                    tmg_people_gender[record.per_no] = Person.UNKNOWN
    _male = sum(1 for g in tmg_people_gender.values() if g == Person.MALE)
    _female = sum(1 for g in tmg_people_gender.values() if g == Person.FEMALE)
    LOG.info("Gender records: %s male, %s female, %s unknown for dataset %s",
             _male, _female, len(tmg_people_gender) - _male - _female, tmg_dataset)

    from gramps.gen.lib import Name, Surname

    imported = 0
    per_no_map = {}  # {tmg_per_no: gramps_handle}
    with DbTxn("Add People", database) as tran:
        for tmgname, (firstname, surname) in tmg_people_named.items():
            try:
                person = Person()
                name = Name()
                surname_obj = Surname()
                surname_obj.set_surname(surname)
                name.add_surname(surname_obj)
                name.set_first_name(firstname)
                person.set_primary_name(name)

                gender = tmg_people_gender.get(tmgname, Person.UNKNOWN)
                person.set_gender(gender)

                database.add_person(person, tran)
                per_no_map[tmgname] = person.get_handle()
                imported += 1
            except Exception as exc:
                LOG.warning("Failed to import person %s (%s %s): %s",
                            tmgname, firstname, surname, exc)

    LOG.info("Imported %s persons for dataset %s", imported, tmg_dataset)
    return per_no_map


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

#--------------------------------------------------------------------------
#
# Events (G/T/P tables) trial  (proof of concept)
# Uses:
# g.ETYPE > t.etypenum (Tag Type)
# g.PLACENUM > p.recno (Place file)
# convert dates to gramps date object
#--------------------------------------------------------------------------

_TMG_CODE_RE = re.compile(r'\[/?:?[A-Z_]+:?\]')

def _strip_tmg_codes(text):
    """Remove TMG inline formatting codes such as [:ITAL:], [:CR:], [BOLD:] etc."""
    if not text:
        return text
    cleaned = _TMG_CODE_RE.sub('', text)
    return cleaned.strip()


def tmg_date_to_gramps_date(tmgdate):
    """Convert a raw TMG date string to a structured Gramps Date object.

    TMG date format (29 chars):
      [0]     datefieldtype: '1' = regular date, '0' = empty/unknown
      [1:9]   first date YYYYMMDD
      [9]     old-style calendar flag ('0'=no, '1'=yes)
      [10]    modifier: 0=before 1=say 2=circa 3=exact 4=after 5=between 6=or 7=from-to
      [11:19] second date YYYYMMDD (used for range/span modifiers)
      [19]    old-style flag for 2nd date
      [20]    uncertain flag ('1' = question mark suffix)
    Returns a Date object, or None if the date is empty/unparseable.
    """
    from gramps.gen.lib import Date as _Date

    if not tmgdate or len(tmgdate) < 21 or tmgdate[0] != '1':
        return None

    def _ymd(s):
        try:
            return int(s[0:4]), int(s[4:6]), int(s[6:8])
        except (ValueError, IndexError):
            return 0, 0, 0

    y1, m1, d1 = _ymd(tmgdate[1:9])
    if y1 == 0 and m1 == 0 and d1 == 0:
        return None  # entirely empty date

    modifier_code = tmgdate[10]
    uncertain     = tmgdate[20] == '1'

    # TMG modifier → Gramps modifier
    _MOD = {
        '0': _Date.MOD_BEFORE,
        '1': _Date.MOD_ABOUT,    # "Say"
        '2': _Date.MOD_ABOUT,    # "Circa"
        '3': _Date.MOD_NONE,     # Exact
        '4': _Date.MOD_AFTER,
        '5': _Date.MOD_RANGE,    # Between … and
        '6': _Date.MOD_RANGE,    # "Or" — closest Gramps equivalent
        '7': _Date.MOD_SPAN,     # From … to
    }
    modifier = _MOD.get(modifier_code, _Date.MOD_NONE)
    quality  = _Date.QUAL_ESTIMATED if (modifier_code == '1' or uncertain) else _Date.QUAL_NONE

    dt = _Date()
    if modifier in (_Date.MOD_RANGE, _Date.MOD_SPAN):
        y2, m2, d2 = _ymd(tmgdate[11:19])
        dt.set(quality, modifier, _Date.CAL_GREGORIAN,
               (d1, m1, y1, False, d2, m2, y2, False))
    else:
        dt.set(quality, modifier, _Date.CAL_GREGORIAN, (d1, m1, y1, False))

    return dt


def import_events(database, tmg_dataset):
    """Import all TMG events, excluding 'Note'-type tags (handled by import_notes)."""
    LOG.info("TMG events import: dataset %s", tmg_dataset)

    # Collect etype numbers for "Note" tag — those are imported as Notes, not Events
    note_etypes = set()
    with tmgTagTypes:
        for record in tmgTagTypes:
            if record.dsid == tmg_dataset and record.etypename.strip() == 'Note':
                note_etypes.add(record.etypenum)

    LOG.debug("Note etypes excluded from events: %s", note_etypes)
    skipped_notes = 0
    no_type = 0
    tmg_events = {}
    with tmgEvents:
        for record in tmgEvents:
            if record.dsid == tmg_dataset:
                if record.etype in note_etypes:
                    skipped_notes += 1
                    continue  # handled by import_notes
                eventtype = tag_type_name(database, record.etype, tmg_dataset)
                if not eventtype:
                    no_type += 1
                eventdate = tmg_date_to_gramps_date(record.edate)
                tmg_events[record.recno] = (
                    eventtype,
                    record.per1,
                    record.per2,
                    eventdate,
                    record.placenum,
                    record.efoot.rstrip(),
                )

    LOG.info("Events read: %s (skipped %s note-type, %s with unrecognised type) for dataset %s",
             len(tmg_events), skipped_notes, no_type, tmg_dataset)
    from gramps.gen.lib import EventType

    event_handle_map = {}  # {tmg_recno: (gramps_handle, per1, per2, placenum)}
    with DbTxn("Add Events", database) as tran:
        for tmgevent_id, tmgevent_val in tmg_events.items():
            eventtype, per1, per2, eventdate, placenum, eventmemo = tmgevent_val
            try:
                event = Event()

                if eventtype:
                    et = EventType()
                    et.set(eventtype)
                    event.set_type(et)

                if eventdate:
                    event.set_date_object(eventdate)

                # place handles are linked in link_event_places() after import_places()
                if eventmemo:
                    event.set_description(_strip_tmg_codes(eventmemo))

                database.add_event(event, tran)
                event_handle_map[tmgevent_id] = (event.get_handle(), per1, per2, placenum)

            except Exception as exc:
                LOG.warning("Failed to import event %s: %s", tmgevent_id, exc)

    LOG.info("Imported %s events for dataset %s", len(event_handle_map), tmg_dataset)
    return event_handle_map


#------------------------------------------------------------------------
# TMG import pipeline wiring
#------------------------------------------------------------------------

def tmg_import_pipeline(database, tmg_dataset, user, sqzfilename=None):
    """Run dataset import stages in correct order."""
    LOG.info("TMG import pipeline begin for dataset %s", tmg_dataset)

    place_handle_map = import_places(database, tmg_dataset)
    event_handle_map = import_events(database, tmg_dataset)
    link_event_places(database, event_handle_map, place_handle_map)
    per_no_map = import_people(database, tmg_dataset)
    link_person_events(database, per_no_map, event_handle_map)
    import_notes(database, tmg_dataset, per_no_map)
    import_families(database, tmg_dataset, per_no_map, event_handle_map)
    repo_handle_map = import_repositories(database, tmg_dataset, per_no_map)
    source_handle_map = import_sources(database, tmg_dataset, repo_handle_map)
    import_citations(database, tmg_dataset, source_handle_map, event_handle_map, per_no_map)
    import_media(database, sqzfilename, tmg_dataset, user,
                 per_no_map=per_no_map, event_handle_map=event_handle_map,
                 source_handle_map=source_handle_map, place_handle_map=place_handle_map)

    LOG.info("TMG import pipeline complete for dataset %s", tmg_dataset)


def import_notes(database, tmg_dataset, per_no_map=None):
    """Import TMG 'Note' tag-type events as Gramps person notes.

    In TMG, etype 'Note' (tag abbrev 'nt') stores free-text notes in the
    efoot memo field.  They are not true events so we convert them to Gramps
    Note objects and attach them to the owning person.
    """
    LOG.info("TMG import notes: dataset %s", tmg_dataset)
    if not per_no_map:
        return

    note_etypes = set()
    with tmgTagTypes:
        for record in tmgTagTypes:
            if record.dsid == tmg_dataset and record.etypename.strip() == 'Note':
                note_etypes.add(record.etypenum)

    if not note_etypes:
        LOG.debug("No 'Note' tag type found for dataset %s", tmg_dataset)
        return

    imported = 0
    skipped_empty = 0
    skipped_no_person = 0
    with DbTxn("Add Notes", database) as tran:
        with tmgEvents:
            for record in tmgEvents:
                if record.dsid != tmg_dataset:
                    continue
                if record.etype not in note_etypes:
                    continue
                note_text = _strip_tmg_codes((record.efoot or '').strip())
                if not note_text:
                    skipped_empty += 1
                    continue
                person_handle = per_no_map.get(record.per1)
                if not person_handle:
                    LOG.debug("No person for note per1=%s recno=%s",
                              record.per1, record.recno)
                    skipped_no_person += 1
                    continue
                note = Note(note_text)
                note.set_type(NoteType.PERSON)
                database.add_note(note, tran)
                person = database.get_person_from_handle(person_handle)
                person.add_note(note.get_handle())
                database.commit_person(person, tran)
                imported += 1

    LOG.info("Imported %s notes, skipped %s empty, %s with no person mapping for dataset %s",
             imported, skipped_empty, skipped_no_person, tmg_dataset)


def link_person_events(database, per_no_map, event_handle_map):
    """Add EventRef(PRIMARY) on each Person for their individual (non-couple) events.

    Couple events (per2 > 0) are attached to the Family by import_families;
    individual events (per2 == 0) must be linked here so Gramps can display
    birth dates, death dates, etc. on person views.
    """
    if not event_handle_map or not per_no_map:
        return

    linked = 0
    skipped_couple = 0
    unresolved_per1 = 0
    with DbTxn("Link Person Events", database) as tran:
        for _, (ev_handle, per1, per2, *_) in event_handle_map.items():
            if per2:
                skipped_couple += 1
                continue  # couple event — handled by import_families
            person_handle = per_no_map.get(per1)
            if not person_handle:
                LOG.debug("No person handle for per1=%s", per1)
                unresolved_per1 += 1
                continue
            person = database.get_person_from_handle(person_handle)
            eref = EventRef()
            eref.set_reference_handle(ev_handle)
            eref.set_role(EventRoleType.PRIMARY)
            person.add_event_ref(eref)
            # Explicitly mark as birth or death ref so Gramps pedigree/list
            # views can find the date via get_birth_ref()/get_death_ref().
            # Without this, get_birth_or_fallback() skips BIRTH events
            # (its fallback only covers BAPTISM/CHRISTEN, not BIRTH itself).
            ev = database.get_event_from_handle(ev_handle)
            if ev:
                if ev.get_type() == EventType.BIRTH:
                    person.set_birth_ref(eref)
                elif ev.get_type() == EventType.DEATH:
                    person.set_death_ref(eref)
            database.commit_person(person, tran)
            linked += 1

    LOG.info("Linked %s individual events to persons "
             "(%s couple events deferred to families, %s per1 unresolved)",
             linked, skipped_couple, unresolved_per1)


def import_families(database, tmg_dataset, per_no_map, event_handle_map=None):
    LOG.info("TMG import families: dataset %s", tmg_dataset)

    if not per_no_map:
        LOG.warning("No person map provided; skipping families")
        return

    # Step 1: classify each ptype etypenum as 'father', 'mother', or 'parent'
    # by reading tag names from tmgTagTypes.  Names start with Father/Mother/Parent.
    ptype_role = {}   # {etypenum: 'father'|'mother'|'parent'}
    ptype_name = {}   # {etypenum: short tag name} for ChildRefType selection
    with tmgTagTypes:
        for record in tmgTagTypes:
            if record.dsid != tmg_dataset:
                continue
            name = record.etypename.strip()
            num  = record.etypenum
            if name.startswith('Father'):
                ptype_role[num] = 'father'
                ptype_name[num] = name
            elif name.startswith('Mother'):
                ptype_role[num] = 'mother'
                ptype_name[num] = name
            elif name.startswith('Parent'):
                ptype_role[num] = 'parent'
                ptype_name[num] = name

    def _child_ref_type(tag_name):
        """Map a TMG tag name to a Gramps ChildRefType."""
        n = tag_name.lower()
        if 'bio' in n:
            return ChildRefType.BIRTH
        if 'ado' in n:
            return ChildRefType.ADOPTED
        if 'ste' in n or 'step' in n:
            return ChildRefType.STEPCHILD
        if 'fst' in n or 'fos' in n:
            return ChildRefType.FOSTER
        return ChildRefType.UNKNOWN

    # Step 2: read all parent-child records, routing each to father/mother bucket
    # per child.  child_fathers/child_mothers: {child_id: [(parent_id, crt), ...]}
    # pnotes: {(child_id, parent_id): note_text} — from pnote memo field
    child_fathers = {}
    child_mothers = {}
    pnotes = {}

    with tmgParentChildRelationships:
        for record in tmgParentChildRelationships:
            if record.dsid != tmg_dataset:
                continue
            parent_id = record.parent
            child_id  = record.child
            ptype     = record.ptype
            if not parent_id or not child_id:
                continue
            role = ptype_role.get(ptype)
            if role is None:
                LOG.debug("Unknown ptype %s for parent %s child %s", ptype, parent_id, child_id)
                continue
            crt = _child_ref_type(ptype_name.get(ptype, ''))
            is_primary = bool(record.primary)
            note_text = (record.pnote or '').strip()
            if note_text:
                pnotes[(child_id, parent_id)] = note_text
            if role == 'father':
                child_fathers.setdefault(child_id, []).append((parent_id, crt, is_primary))
            elif role == 'mother':
                child_mothers.setdefault(child_id, []).append((parent_id, crt, is_primary))
            else:  # 'parent' — assign by gender of parent person
                person_handle = per_no_map.get(parent_id)
                if person_handle:
                    p = database.get_person_from_handle(person_handle)
                    if p.get_gender() == Person.MALE:
                        child_fathers.setdefault(child_id, []).append((parent_id, crt, is_primary))
                    else:
                        child_mothers.setdefault(child_id, []).append((parent_id, crt, is_primary))

    # Sort each child's parent lists so primary=True entries come first.
    # This ensures fathers[0]/mothers[0] in Step 3 is the primary parent.
    for lst in child_fathers.values():
        lst.sort(key=lambda x: not x[2])
    for lst in child_mothers.values():
        lst.sort(key=lambda x: not x[2])

    LOG.info("Collected father records: %s, mother records: %s",
             sum(len(v) for v in child_fathers.values()),
             sum(len(v) for v in child_mothers.values()))

    # Step 3: group children by (father_id|None, mother_id|None) pairs.
    # The primary pair (first father + first mother) is one Family.
    # Each additional father creates an extra (extra_father, None) family entry,
    # and each additional mother creates an extra (None, extra_mother) family entry.
    # This covers children with multiple fathers or mothers (step/adoptive parents).
    # family_groups: {(father_id|None, mother_id|None): [(child_id, father_crt, mother_crt), ...]}
    family_groups = {}

    all_children = set(child_fathers) | set(child_mothers)
    for child_id in all_children:
        fathers = child_fathers.get(child_id, [])
        mothers = child_mothers.get(child_id, [])

        # Primary family: first father + first mother (already sorted primary-first)
        father_id  = fathers[0][0] if fathers else None
        mother_id  = mothers[0][0] if mothers else None
        father_crt = fathers[0][1] if fathers else ChildRefType.UNKNOWN
        mother_crt = mothers[0][1] if mothers else ChildRefType.UNKNOWN
        family_groups.setdefault((father_id, mother_id), []).append(
            (child_id, father_crt, mother_crt))

        # Secondary fathers → each gets their own (father, None) family
        for extra_father_id, extra_crt, _ in fathers[1:]:
            family_groups.setdefault((extra_father_id, None), []).append(
                (child_id, extra_crt, ChildRefType.UNKNOWN))

        # Secondary mothers → each gets their own (None, mother) family
        for extra_mother_id, extra_crt, _ in mothers[1:]:
            family_groups.setdefault((None, extra_mother_id), []).append(
                (child_id, ChildRefType.UNKNOWN, extra_crt))

    # Step 4: build couple-event lookup from the event map.
    # Events with per2 > 0 involve two people; key by frozenset so order doesn't matter.
    # Also derive FamilyRelType per couple: MARRIED if any event is a Marriage,
    # otherwise UNKNOWN.
    couple_events = {}  # {frozenset({per1, per2}): [event_handle, ...]}
    couple_rel    = {}  # {frozenset({per1, per2}): FamilyRelType}
    if event_handle_map:
        for _, (ev_handle, per1, per2, *_) in event_handle_map.items():
            if per2:
                key = frozenset((per1, per2))
                couple_events.setdefault(key, []).append(ev_handle)
                # Any couple event → at least UNMARRIED; upgrade to MARRIED if applicable
                ev = database.get_event_from_handle(ev_handle)
                if ev and ev.get_type() == EventType.MARRIAGE:
                    couple_rel[key] = FamilyRelType.MARRIED
                elif key not in couple_rel:
                    couple_rel[key] = FamilyRelType.UNMARRIED
    LOG.info("Couple events available for linking: %s", sum(len(v) for v in couple_events.values()))

    # Step 5: create Family objects, attach couple events, update back-references
    families_created = 0
    events_linked = 0
    with DbTxn("Add Families", database) as tran:
        for (father_id, mother_id), children in family_groups.items():
            try:
                father_handle = per_no_map.get(father_id) if father_id else None
                mother_handle = per_no_map.get(mother_id) if mother_id else None

                if not father_handle and not mother_handle:
                    LOG.debug("No mapped handles for family (%s, %s)", father_id, mother_id)
                    continue

                family = Family()
                if father_handle:
                    family.set_father_handle(father_handle)
                if mother_handle:
                    family.set_mother_handle(mother_handle)

                for child_id, father_crt, mother_crt in children:
                    child_handle = per_no_map.get(child_id)
                    if not child_handle:
                        continue
                    child_ref = ChildRef()
                    child_ref.set_reference_handle(child_handle)
                    child_ref.set_father_relation(father_crt)
                    child_ref.set_mother_relation(mother_crt)
                    for parent_id in (father_id, mother_id):
                        note_text = pnotes.get((child_id, parent_id))
                        if note_text:
                            note = Note(note_text)
                            note.set_type(NoteType.GENERAL)
                            database.add_note(note, tran)
                            child_ref.add_note(note.get_handle())
                    family.add_child_ref(child_ref)

                # Attach any couple events (marriage, divorce, etc.) for this pair
                # and set FamilyRelType based on whether a marriage event exists
                if father_id and mother_id:
                    couple_key = frozenset((father_id, mother_id))
                    for ev_handle in couple_events.get(couple_key, []):
                        eref = EventRef()
                        eref.set_reference_handle(ev_handle)
                        eref.set_role(EventRoleType.FAMILY)
                        family.add_event_ref(eref)
                        events_linked += 1
                    rel = couple_rel.get(couple_key, FamilyRelType.UNKNOWN)
                    family.set_relationship(FamilyRelType(rel))

                database.add_family(family, tran)
                family_handle = family.get_handle()
                families_created += 1

                # Back-references: parents need family_handle, children need parent_family_handle
                for handle in (father_handle, mother_handle):
                    if handle:
                        person = database.get_person_from_handle(handle)
                        person.add_family_handle(family_handle)
                        database.commit_person(person, tran)

                for child_id, *_ in children:
                    child_handle = per_no_map.get(child_id)
                    if child_handle:
                        child = database.get_person_from_handle(child_handle)
                        child.add_parent_family_handle(family_handle)
                        database.commit_person(child, tran)

            except Exception as exc:
                LOG.warning("Failed to import family (%s, %s): %s", father_id, mother_id, exc)

    LOG.info("Linked %s couple events across %s families for dataset %s",
             events_linked, families_created, tmg_dataset)

    # Step 6: childless couples — couples that have couple events but no children
    # in _f.dbf get no entry in family_groups, so they need a separate pass.
    existing_couples = {frozenset((f, m)) for f, m in family_groups if f and m}
    childless_created = 0
    childless_events = 0
    with DbTxn("Add Childless Couple Families", database) as tran:
        for couple_key, ev_handles in couple_events.items():
            if couple_key in existing_couples:
                continue  # already has a family from the parent-child pass
            if len(couple_key) != 2:
                continue  # shouldn't happen, but guard against
            per1_id, per2_id = tuple(couple_key)
            handle1 = per_no_map.get(per1_id)
            handle2 = per_no_map.get(per2_id)
            if not handle1 or not handle2:
                continue

            # Assign father/mother by gender; fall back to per1=father if unknown
            p1 = database.get_person_from_handle(handle1)
            p2 = database.get_person_from_handle(handle2)
            if p1.get_gender() == Person.FEMALE:
                father_handle, mother_handle = handle2, handle1
            elif p2.get_gender() == Person.FEMALE:
                father_handle, mother_handle = handle1, handle2
            else:
                # Both unknown or both male — put per1 in father slot
                father_handle, mother_handle = handle1, handle2

            family = Family()
            family.set_father_handle(father_handle)
            family.set_mother_handle(mother_handle)
            rel = couple_rel.get(couple_key, FamilyRelType.UNKNOWN)
            family.set_relationship(FamilyRelType(rel))

            for ev_handle in ev_handles:
                eref = EventRef()
                eref.set_reference_handle(ev_handle)
                eref.set_role(EventRoleType.FAMILY)
                family.add_event_ref(eref)
                childless_events += 1

            database.add_family(family, tran)
            family_handle = family.get_handle()
            childless_created += 1

            for handle in (father_handle, mother_handle):
                person = database.get_person_from_handle(handle)
                person.add_family_handle(family_handle)
                database.commit_person(person, tran)

    LOG.info("Imported %s childless couple families (%s events linked) for dataset %s",
             childless_created, childless_events, tmg_dataset)

    LOG.info("Imported %s families for dataset %s", families_created + childless_created, tmg_dataset)
    return


def _repo_type_from_name(name):
    """Guess a RepositoryType from the repository name."""
    n = name.lower()
    if any(x in n for x in ('.com', '.org', '.net', '.gov', 'online', 'website',
                             'ancestry', 'familysearch', 'rootsweb', 'findmypast',
                             'myheritage', 'genealogy.com')):
        return RepositoryType.WEBSITE
    if any(x in n for x in ('archive', 'archives', 'record office', 'records office',
                             'pro ', 'public record', 'national archive')):
        return RepositoryType.ARCHIVE
    if any(x in n for x in ('library', 'atheneum', 'athenaeum', 'bibliotheque')):
        return RepositoryType.LIBRARY
    if 'cemetery' in n or 'graveyard' in n:
        return RepositoryType.CEMETERY
    if 'church' in n or 'parish' in n:
        return RepositoryType.CHURCH
    return RepositoryType.LIBRARY  # sensible default


def _url_from_name(name):
    """Extract a URL string if the repository name contains a domain."""
    import re as _re
    # Match bare domains like "ancestry.com" or "www.familysearch.org"
    m = _re.search(r'\b((?:www\.)?[\w-]+\.(?:com|org|net|gov|uk|co\.uk))\b',
                   name, _re.IGNORECASE)
    if m:
        domain = m.group(1).lower()
        if not domain.startswith('www.'):
            domain = 'www.' + domain
        return 'https://' + domain
    return None


def import_repositories(database, tmg_dataset, per_no_map=None):
    LOG.info("TMG import repositories: dataset %s", tmg_dataset)

    repo_handle_map = {}  # {tmg_recno: gramps_handle}
    imported = 0
    with DbTxn("Add Repositories", database) as tran:
        with tmgRepositories:
            for record in tmgRepositories:
                if record.dsid != tmg_dataset:
                    continue
                try:
                    repo = Repository()
                    name = (record.name or '').strip()
                    abbrev = (record.abbrev or '').strip()
                    if not name:
                        name = abbrev
                    repo.set_name(name)
                    repo.set_type(RepositoryType(_repo_type_from_name(name)))

                    url_str = _url_from_name(name)
                    if url_str:
                        url = Url()
                        url.set_path(url_str)
                        url.set_type(UrlType(UrlType.WEB_HOME))
                        repo.add_url(url)

                    extra_lines = []
                    if abbrev and abbrev != name:
                        extra_lines.append(f"Abbreviation: {abbrev}")
                    rperno = getattr(record, 'rperno', 0) or 0
                    if rperno and per_no_map and per_no_map.get(rperno):
                        extra_lines.append(f"Contact person (TMG#): {rperno}")

                    note_text = _strip_tmg_codes((record.rnote or '').strip())
                    if extra_lines:
                        note_text = '\n'.join(extra_lines) + ('\n' + note_text if note_text else '')
                    if note_text:
                        note = Note(note_text)
                        note.set_type(NoteType.GENERAL)
                        database.add_note(note, tran)
                        repo.add_note(note.get_handle())

                    database.add_repository(repo, tran)
                    repo_handle_map[record.recno] = repo.get_handle()
                    imported += 1
                except Exception as exc:
                    LOG.warning("Failed to import repository recno=%s: %s", record.recno, exc)

    LOG.info("Imported %s repositories for dataset %s", imported, tmg_dataset)
    return repo_handle_map


def import_sources(database, tmg_dataset, repo_handle_map=None):
    LOG.info("TMG import sources: dataset %s", tmg_dataset)

    # Build repo-link index: {majnum: [(rnumber, reference)]}
    repo_links = {}
    with tmgSourceRepositoryLinks:
        for r in tmgSourceRepositoryLinks:
            if r.dsid != tmg_dataset:
                continue
            ref = (r.reference or '').strip()
            repo_links.setdefault(r.mnumber, []).append((r.rnumber, ref))

    # Source component element names: {recno: '[ELEMENT NAME]'}
    # The info field stores values positionally: split('$!&')[i] -> recno i+1
    _src_elements = {}
    with tmgSourceComponents:
        for r in tmgSourceComponents:
            _src_elements[r.recno] = r.element.strip()

    # Elements whose values map to Gramps author field
    _AUTHOR_ELEMS = {
        '[AUTHOR]', '[COMPILER]', '[EDITOR]', '[AGENCY]',
        '[INFORMANT]', '[INTERVIEWER]', '[PHOTOGRAPHER]',
        '[READER]', '[SPEAKER]',
    }

    source_handle_map = {}  # {tmg_majnum: gramps_handle}
    imported = 0
    skipped_inactive = 0
    with DbTxn("Add Sources", database) as tran:
        with tmgSources:
            for record in tmgSources:
                if record.dsid != tmg_dataset:
                    continue
                if not record.mactive:
                    skipped_inactive += 1
                    continue
                try:
                    source = Source()

                    title = _strip_tmg_codes((record.title or '').strip())
                    source.set_title(title or '(untitled)')

                    abbrev = (record.abbrev or '').strip()
                    if abbrev:
                        source.set_abbreviation(abbrev)

                    # info field: values stored positionally, split by '$!&'
                    # index i (0-based) -> element recno i+1 in tmgSourceComponents
                    info_raw = (record.info or '')
                    info_pairs = []
                    for i, val in enumerate(info_raw.split('$!&')):
                        val = val.strip()
                        if val:
                            label = _src_elements.get(i + 1, f'Field{i + 1}')
                            info_pairs.append((label, val))

                    author_vals = [v for e, v in info_pairs if e in _AUTHOR_ELEMS]
                    if author_vals:
                        source.set_author('; '.join(author_vals))

                    pub_pairs = [(e, v) for e, v in info_pairs if e not in _AUTHOR_ELEMS]
                    if pub_pairs:
                        pub_text = '\n'.join(
                            f"{e.strip('[]')}: {v}" for e, v in pub_pairs
                        )
                        source.set_publication_info(pub_text)

                    # text, fform, sform, bform → notes
                    note_fields = [
                        ('Source text',        record.text),
                        ('Footnote form',      record.fform),
                        ('Short footnote',     record.sform),
                        ('Bibliography form',  record.bform),
                        ('Reminders',          record.reminders),
                    ]
                    for label, raw in note_fields:
                        cleaned = _strip_tmg_codes((raw or '').strip())
                        if cleaned:
                            note = Note(f"{label}:\n{cleaned}")
                            note.set_type(NoteType.GENERAL)
                            database.add_note(note, tran)
                            source.add_note(note.get_handle())

                    # Attach repositories
                    if repo_handle_map:
                        for rnumber, call_number in repo_links.get(record.majnum, []):
                            repo_handle = repo_handle_map.get(rnumber)
                            if not repo_handle:
                                continue
                            repo_ref = RepoRef()
                            repo_ref.set_reference_handle(repo_handle)
                            if call_number:
                                repo_ref.set_call_number(call_number)
                            repo_ref.set_media_type(SourceMediaType(SourceMediaType.UNKNOWN))
                            source.add_repo_reference(repo_ref)

                    database.add_source(source, tran)
                    source_handle_map[record.majnum] = source.get_handle()
                    imported += 1
                except Exception as exc:
                    LOG.warning("Failed to import source majnum=%s: %s", record.majnum, exc)

    LOG.info("Imported %s sources, skipped %s inactive for dataset %s",
             imported, skipped_inactive, tmg_dataset)
    return source_handle_map


def import_citations(database, tmg_dataset, source_handle_map=None,
                     event_handle_map=None, per_no_map=None):
    LOG.info("TMG import citations: dataset %s", tmg_dataset)

    if not source_handle_map:
        LOG.warning("No source map; skipping citations")
        return

    # name recno -> per_no (to attach N-type citations to the person)
    name_recno_to_per = {}
    with tmgNames:
        for r in tmgNames:
            if r.dsid == tmg_dataset:
                name_recno_to_per[r.recno] = r.nper

    # f recno -> child per_no (to attach F-type citations to the child person)
    f_recno_to_child = {}
    with tmgParentChildRelationships:
        for r in tmgParentChildRelationships:
            if r.dsid == tmg_dataset:
                f_recno_to_child[r.recno] = r.child

    # TMG sure code -> Gramps confidence level
    from gramps.gen.lib import Citation as _Cit
    _SURE_MAP = {
        '3': _Cit.CONF_VERY_HIGH,
        '2': _Cit.CONF_HIGH,
        '1': _Cit.CONF_NORMAL,
        '0': _Cit.CONF_LOW,
    }

    def _confidence(record):
        for field in ('sdsure', 'snsure', 'sssure', 'spsure', 'sfsure'):
            val = (getattr(record, field, None) or '').strip()
            if val in _SURE_MAP:
                return _SURE_MAP[val]
        return _Cit.CONF_NORMAL

    # Build citation objects and group by target object
    target_citations = {}  # {(stype, refrec): [citation_handle]}

    imported = 0
    skipped_excluded = 0
    skipped_no_source = 0
    with DbTxn("Add Citations", database) as tran:
        with tmgCitations:
            for record in tmgCitations:
                if record.dsid != tmg_dataset:
                    continue
                if record.exclude:
                    skipped_excluded += 1
                    continue
                source_handle = source_handle_map.get(record.majsource)
                if not source_handle:
                    skipped_no_source += 1
                    continue
                try:
                    citation = _Cit()
                    citation.set_reference_handle(source_handle)

                    page = _strip_tmg_codes((record.subsource or '').strip())
                    if not page:
                        page = (record.citref or '').strip()
                    if page:
                        citation.set_page(page)

                    citation.set_confidence_level(_confidence(record))

                    memo = _strip_tmg_codes((record.citmemo or '').strip())
                    if memo:
                        note = Note(memo)
                        note.set_type(NoteType.GENERAL)
                        database.add_note(note, tran)
                        citation.add_note(note.get_handle())

                    database.add_citation(citation, tran)
                    key = (record.stype, record.refrec)
                    target_citations.setdefault(key, []).append(citation.get_handle())
                    imported += 1
                except Exception as exc:
                    LOG.warning("Failed to import citation recno=%s: %s", record.recno, exc)

    LOG.info("Created %s citation objects, skipped %s excluded, %s with no source match "
             "for dataset %s", imported, skipped_excluded, skipped_no_source, tmg_dataset)

    # Attach citations to their target objects
    attached = 0
    attached_by_type = {'E': 0, 'N': 0, 'F': 0}
    with DbTxn("Attach Citations", database) as tran:
        for (stype, refrec), cite_handles in target_citations.items():
            try:
                if stype == 'E' and event_handle_map:
                    entry = event_handle_map.get(refrec)
                    if not entry:
                        continue
                    ev_handle = entry[0]
                    obj = database.get_event_from_handle(ev_handle)
                    if obj:
                        for h in cite_handles:
                            obj.add_citation(h)
                        database.commit_event(obj, tran)
                        attached += len(cite_handles)
                        attached_by_type['E'] += len(cite_handles)

                elif stype == 'N' and per_no_map:
                    per_no = name_recno_to_per.get(refrec)
                    if per_no is None:
                        continue
                    person_handle = per_no_map.get(per_no)
                    if not person_handle:
                        continue
                    obj = database.get_person_from_handle(person_handle)
                    if obj:
                        for h in cite_handles:
                            obj.add_citation(h)
                        database.commit_person(obj, tran)
                        attached += len(cite_handles)
                        attached_by_type['N'] += len(cite_handles)

                elif stype == 'F' and per_no_map:
                    child_per_no = f_recno_to_child.get(refrec)
                    if child_per_no is None:
                        continue
                    person_handle = per_no_map.get(child_per_no)
                    if not person_handle:
                        continue
                    obj = database.get_person_from_handle(person_handle)
                    if obj:
                        for h in cite_handles:
                            obj.add_citation(h)
                        database.commit_person(obj, tran)
                        attached += len(cite_handles)
                        attached_by_type['F'] += len(cite_handles)

            except Exception as exc:
                LOG.warning("Failed to attach citation stype=%s refrec=%s: %s",
                            stype, refrec, exc)

    LOG.info("Attached %s citations (%s to events, %s to names, %s to family records)",
             attached, attached_by_type['E'], attached_by_type['N'], attached_by_type['F'])


def import_places(database, tmg_dataset):
    LOG.info("TMG import places: dataset %s", tmg_dataset)

    # Part type id → label (City, State, Country, …)
    part_type_names = {}
    with tmgPlacePartType:
        for r in tmgPlacePartType:
            part_type_names[r.type] = r.value.strip()

    # Place dictionary: uid → text value
    place_dict = {}
    with tmgPlaceDictionary:
        for r in tmgPlaceDictionary:
            place_dict[r.uid] = r.value.strip()

    # Part value index: place_recno → [(part_type_id, uid)]
    ppv_index = {}
    with tmgPlacePartValue:
        for r in tmgPlacePartValue:
            if r.dsid == tmg_dataset:
                ppv_index.setdefault(r.recno, []).append((r.type, r.uid))

    # TMG part type id → Gramps PlaceType (most specific wins)
    _PART_TO_GRAMPS_TYPE = {
        'Country':           PlaceType.COUNTRY,
        'State':             PlaceType.STATE,
        'County':            PlaceType.COUNTY,
        'City':              PlaceType.CITY,
        'Detail':            PlaceType.STREET,
        'Addressee':         PlaceType.BUILDING,
    }
    # Geographic parts that go into the place name (in display order)
    _GEO_ORDER = ['Addressee', 'Detail', 'City', 'County', 'State', 'Country']
    # Parts that go into a note instead
    _NOTE_PARTS = {'Postal', 'Phone', 'Temple'}

    place_handle_map = {}
    imported = 0
    skipped_empty = 0
    with DbTxn("Add Places", database) as tran:
        with tmgPlaces:
            for record in tmgPlaces:
                if record.dsid != tmg_dataset:
                    continue
                try:
                    parts = ppv_index.get(record.recno, [])
                    # Map type_id → text value
                    part_map = {}
                    for type_id, uid in parts:
                        label = part_type_names.get(type_id, f'type{type_id}')
                        value = place_dict.get(uid, '')
                        if value:
                            part_map[label] = value

                    # Build place name from geographic parts in display order
                    geo_parts = [part_map[k] for k in _GEO_ORDER if k in part_map]
                    place_name = ', '.join(geo_parts)
                    if not place_name:
                        place_name = record.shortplace.strip() if record.shortplace else ''
                    if not place_name:
                        skipped_empty += 1
                        continue  # skip empty places

                    # Determine most specific PlaceType (first match in specificity order)
                    place_type = PlaceType.UNKNOWN
                    for label in _GEO_ORDER:
                        if label in part_map and label in _PART_TO_GRAMPS_TYPE:
                            place_type = _PART_TO_GRAMPS_TYPE[label]
                            break

                    place = Place()
                    pname = PlaceName()
                    pname.set_value(place_name)
                    place.set_name(pname)
                    place.set_type(PlaceType(place_type))

                    # Extra info → note
                    note_lines = []
                    for label in sorted(_NOTE_PARTS):
                        if label in part_map and label != 'Latitude/Longitude':
                            note_lines.append(f"{label}: {part_map[label]}")
                    comment = _strip_tmg_codes((record.comment or '').strip())
                    if comment:
                        note_lines.append(comment)
                    if note_lines:
                        note = Note('\n'.join(note_lines))
                        note.set_type(NoteType.GENERAL)
                        database.add_note(note, tran)
                        place.add_note(note.get_handle())

                    database.add_place(place, tran)
                    place_handle_map[record.recno] = place.get_handle()
                    imported += 1
                except Exception as exc:
                    LOG.warning("Failed to import place recno=%s: %s", record.recno, exc)

    LOG.info("Imported %s places, skipped %s with no resolvable name for dataset %s",
             imported, skipped_empty, tmg_dataset)
    return place_handle_map


def link_event_places(database, event_handle_map, place_handle_map):
    """Set the place handle on each event that has a placenum."""
    if not event_handle_map or not place_handle_map:
        return
    linked = 0
    unresolved_place = 0
    with DbTxn("Link Event Places", database) as tran:
        for _, (ev_handle, _, _, placenum) in event_handle_map.items():
            if not placenum:
                continue
            place_handle = place_handle_map.get(placenum)
            if not place_handle:
                unresolved_place += 1
                continue
            event = database.get_event_from_handle(ev_handle)
            if not event:
                continue
            event.set_place_handle(place_handle)
            database.commit_event(event, tran)
            linked += 1
    LOG.info("Linked %s events to places, %s placenum references unresolved",
             linked, unresolved_place)


def import_media(database, sqzfilename, tmg_dataset, user,
                 per_no_map=None, event_handle_map=None,
                 source_handle_map=None, place_handle_map=None):
    LOG.info("TMG import media: sqz %s", sqzfilename)
    if not sqzfilename:
        return

    import zipfile, mimetypes
    from gramps.gen.lib import Media, MediaRef

    my_media_path = media_path(database)
    media_dir = os.path.splitext(os.path.basename(sqzfilename))[0] + ".media"
    target_dir = os.path.join(my_media_path, media_dir)
    os.makedirs(target_dir, exist_ok=True)

    # Extract media files from SQZ and build basename -> path map
    extracted = {}  # {basename_lower: relative_path_from_media_base}
    try:
        with zipfile.ZipFile(sqzfilename) as zf:
            for entry in zf.infolist():
                name = entry.filename
                if any(name.lower().endswith(ext) for ext in (
                        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
                        '.tif', '.tiff', '.pdf', '.mp3', '.wav',
                        '.mp4', '.avi', '.wmv', '.mov')):
                    basename = os.path.basename(name)
                    dest = os.path.join(target_dir, basename)
                    if not os.path.exists(dest):
                        with zf.open(entry) as src, open(dest, 'wb') as dst:
                            dst.write(src.read())
                    rel = os.path.join(media_dir, basename)
                    extracted[basename.lower()] = rel
    except Exception as exc:
        LOG.warning("Failed to extract media from SQZ: %s", exc)

    LOG.info("Extracted %s media files to %s", len(extracted), target_dir)

    # exhibit_xname → best-guess filename (strip trailing punctuation/spaces)
    def _find_file(ifilename, vfilename, xname):
        for candidate in (ifilename, vfilename):
            if candidate and candidate.strip():
                bn = os.path.basename(candidate.strip()).lower()
                if bn in extracted:
                    return extracted[bn]
        # try matching xname against extracted filenames
        if xname:
            norm = xname.strip().rstrip(';').strip().lower()
            for bn, rel in extracted.items():
                stem = os.path.splitext(bn)[0].lower()
                if stem == norm or norm.startswith(stem) or stem.startswith(norm[:10]):
                    return rel
        return None

    # Exhibits matched to a file → media_handle_map
    # Extracted files not claimed by any exhibit → standalone Media objects
    media_handle_map = {}  # {idexhibit: media_handle}
    claimed_files = set()  # rel_paths already used by an exhibit
    imported = 0
    with DbTxn("Add Media", database) as tran:
        with tmgExhibits:
            for record in tmgExhibits:
                if record.dsid != tmg_dataset:
                    continue
                try:
                    xname = (record.xname or '').strip().rstrip(';').strip()
                    ifile = (record.ifilename or '').strip()
                    vfile = (record.vfilename or '').strip()

                    rel_path = _find_file(ifile, vfile, xname)
                    # Skip exhibits with no resolvable file — an empty path
                    # causes Gramps to resolve it as the media base directory,
                    # which crashes the metadata viewer gramplet.
                    if not rel_path:
                        LOG.debug("No file for exhibit %s %r — skipping",
                                  record.idexhibit, xname)
                        continue

                    claimed_files.add(rel_path)
                    media = Media()
                    media.set_description(xname or os.path.basename(rel_path))
                    media.set_path(rel_path)
                    mime, _ = mimetypes.guess_type(rel_path)
                    if mime:
                        media.set_mime_type(mime)

                    caption = (record.caption or '').strip()
                    descript = _strip_tmg_codes((record.descript or '').strip())
                    note_text = '\n'.join(filter(None, [caption, descript]))
                    if note_text:
                        note = Note(note_text)
                        note.set_type(NoteType.GENERAL)
                        database.add_note(note, tran)
                        media.add_note(note.get_handle())

                    database.add_media(media, tran)
                    media_handle_map[record.idexhibit] = media.get_handle()
                    imported += 1
                except Exception as exc:
                    LOG.warning("Failed to import exhibit idexhibit=%s: %s",
                                record.idexhibit, exc)

        # Standalone Media objects for extracted files not matched to any exhibit
        for rel_path in sorted(extracted.values()):
            if rel_path in claimed_files:
                continue
            try:
                media = Media()
                media.set_path(rel_path)
                media.set_description(os.path.splitext(os.path.basename(rel_path))[0])
                mime, _ = mimetypes.guess_type(rel_path)
                if mime:
                    media.set_mime_type(mime)
                database.add_media(media, tran)
                imported += 1
            except Exception as exc:
                LOG.warning("Failed to create standalone media %s: %s", rel_path, exc)

    LOG.info("Imported %s media objects for dataset %s", imported, tmg_dataset)

    # Link media objects to their target objects
    linked = 0
    with DbTxn("Link Media", database) as tran:
        with tmgExhibits:
            for record in tmgExhibits:
                if record.dsid != tmg_dataset:
                    continue
                media_handle = media_handle_map.get(record.idexhibit)
                if not media_handle:
                    continue
                try:
                    mref = MediaRef()
                    mref.set_reference_handle(media_handle)

                    targets = []
                    if record.id_person and per_no_map:
                        h = per_no_map.get(record.id_person)
                        if h:
                            obj = database.get_person_from_handle(h)
                            if obj:
                                targets.append((obj, database.commit_person))
                    if record.id_event and event_handle_map:
                        entry = event_handle_map.get(record.id_event)
                        if entry:
                            obj = database.get_event_from_handle(entry[0])
                            if obj:
                                targets.append((obj, database.commit_event))
                    if record.id_source and source_handle_map:
                        h = source_handle_map.get(record.id_source)
                        if h:
                            obj = database.get_source_from_handle(h)
                            if obj:
                                targets.append((obj, database.commit_source))
                    if record.id_place and place_handle_map:
                        h = place_handle_map.get(record.id_place)
                        if h:
                            obj = database.get_place_from_handle(h)
                            if obj:
                                targets.append((obj, database.commit_place))

                    for obj, commit_fn in targets:
                        obj.add_media_reference(mref)
                        commit_fn(obj, tran)
                        linked += 1
                except Exception as exc:
                    LOG.warning("Failed to link exhibit idexhibit=%s: %s",
                                record.idexhibit, exc)

    LOG.info("Linked %s media references", linked)


#-------------------

def on_changed(selection):
    # Get the selected Dataset row
    (model, iter) = selection.get_selected()
    # print value selected
    LOG.debug("Selected TMG Data Set %s %s", model[iter][0], model[iter][1])
    selecteddataset = int(model[iter][0])

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
        LOG.warning("Create a New Family Tree to import your TMG Backup into.")
        user.notify_error(
            _("TMG import failed"),
            _("The current Family Tree is not empty.\n\n"
              "Please create a new empty Family Tree before importing "
              "a TMG backup file."))
        return
    #print("Current Family Tree is empty! database.get_total() = ",
    #      database.get_total())

    sqzfilename = os.path.normpath(sqzfilename)
    basefiledir = os.path.dirname(sqzfilename)

    ######check if SQZ contains a valid TMG PJC file
    if sqz_pjc_exist(sqzfilename):
        #Create temporary folder for everything to work in
        # create temp folder for all extracted files & folders
        with tempfile.TemporaryDirectory() as tmpdirname:
            # extract files from SQZ
            extractsqz(sqzfilename, tmpdirname)

            #Find folder location of PJC file
            pjcfilelocation = find_file_ext(".PJC", tmpdirname)

            #Initialize
            project = TmgProject(pjcfilelocation)

            # Check PJC version is for TMG 9.02 or newer (PJCVERSION = 11.0)
            # and continue (For the TMG Program Version; generally subtract 1
            # from the PjcVersion number)
            try:
                pjcverresult = project.version()
            except (KeyError, ValueError) as exc:
                LOG.error("Cannot read PJC version: %s", exc)
                user.notify_error(
                    _("TMG import failed"),
                    _("The TMG backup file could not be read: "
                      "PJC version information is missing or unreadable.\n\n"
                      "Please ensure you are using a backup created by "
                      "TMG 9.02 or later (PjcVersion >= 11.0)."))
                return
            LOG.info("PJC version: %s", pjcverresult)
            if pjcverresult >= MIN_PJC_VERSION:
                LOG.info("TMG 9.02 or greater project backup")
            else:
                LOG.warning("TMG backup is PJC version %s (TMG 9.01 or earlier) — "
                            "import aborted", pjcverresult)
                user.notify_error(
                    _("TMG version not supported"),
                    _("This backup was created with an older version of TMG "
                      "(PjcVersion %(ver)s, equivalent to TMG 9.01 or earlier).\n\n"
                      "Please upgrade your TMG project to version 9.05 and "
                      "create a new backup, then import again.\n\n"
                      "See: https://gramps-project.org/wiki/index.php/"
                      "Addon:TMGimporter#Before_Import_From_TMG_Backup_file")
                    % {'ver': pjcverresult})
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
            LOG.debug("only_has_one_dataset() = %s", only_has_one_dataset())
            # check if running from cli (see: importgedcom.py)
            if not only_has_one_dataset() and user.uistate:
                LOG.debug("GUI running: showing dataset selection dialog")
                top = Glade()
                liststore = top.get_object('liststore1')
                # Add list of Datasets from TMG Project
                datasetchoice = datasets()
                LOG.debug("All datasets: %s", datasets())
                for datasetrow in datasetchoice.items():
                    liststore.append((str(datasetrow[1][0]),
                                      str(datasetrow[1][1])))
                # Which row is selected in the list
                treeview1 = top.get_object('treeview1')
                treeview1.get_selection().connect("changed", on_changed)
                window = top.get_object('tmgimporterwindow')
                dialog = top.toplevel
                dialog.set_transient_for(user.uistate.window)
                #print(dir(dialog))
                dialog.show_all()
                #dialog.run()
                #tmg_dataset = selecteddataset

                dialog.destroy()

                # select first dataset in a multidataset backup if on cli
                #only_first_dataset()
                #user_dsid = input("Selected TMG file has multiple datasets. "
                #                  "Please select one to import? ")
                #print("You selected dataset = ", user_dsid)
                # select the first dsid number from the dataset table
                #tmg_dataset = datasetchoice[int(user_dsid)][0]
            elif only_has_one_dataset():
                LOG.debug("Only one dataset found")
                # if true get the dsid of the dataset
                # not alway "1" especially when you delete and renumber
                # datasets like myself
                # {1: (1, 'blank / My Data Set', False, True)}
                # use first dataset in (D.dbf) eg
                datasetchoice = datasets()
                user_dsid = 0  # only choice
                # select the dsid number from the dataset table
                #tmg_dataset = datasetchoice[int(user_dsid)][0]
            else:
                #No dataset available then stop
                LOG.warning("No TMG datasets available!")
                user.notify_error(
                    _("TMG import failed"),
                    _("No datasets were found in this TMG backup file.\n\n"
                      "The backup may be corrupt or empty."))
                return
###############################################################################
            #Process TMG Project for import
            #------------------------------------------------------
            # determine dataset id if it has not been set by GUI selection
            if 'tmg_dataset' not in locals() or tmg_dataset is None:
                if only_has_one_dataset():
                    tmg_dataset = only_first_dataset()
                else:
                    tmg_dataset = only_first_dataset()
                    LOG.warning("Multiple datasets found; defaulting to dataset %s", tmg_dataset)

            LOG.info("Starting TMG import pipeline for dataset %s", tmg_dataset)
            try:
                tmg_import_pipeline(database, tmg_dataset, user, sqzfilename)
            except Exception:
                LOG.exception("TMG import pipeline failed")
                raise

            #------------------------------------------------------

    else:
        LOG.error("Invalid TMG backup file: %s", sqzfilename)
        user.notify_error(
            _("TMG import failed"),
            _("%(filename)s does not appear to be a valid TMG backup file.\n\n"
              "The file must be a TMG backup archive (*.SQZ) containing "
              "a project configuration file (.PJC).\n\n"
              "Ensure the file was created by TMG version 5.x or later.") %
            {'filename': sqzfilename})
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
    try:
        zip = zipfile.ZipFile(sqzfiletocheck)
    except (zipfile.BadZipFile, OSError) as exc:
        LOG.error("Cannot open SQZ file %s: %s", sqzfiletocheck, exc)
        return False
    pjcfile = zip.namelist()
    validtmgfile = None
    for x in pjcfile:
        # Check backup contains valid Project Config or Version control file
        # *.VER - Version Control File (v0.x to v1.2a)
        # *.TMG - Version Control File (v2.0 to v4.0d)
        # *.PJC - TMG Project Configuration File (v5.0 to v9.05)
        if(x.endswith('.PJC') or x.endswith('.pjc') or
           x.endswith('.tmg') or x.endswith('.VER')):
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
        LOG.error('Did not find %s in zip file', sqzfiletocheck)
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
        # Copy DBF & FPT files to lowercase in temp folder
        #Minimal files need by TMG Importer
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
            if(name.lower().endswith(fileext2find.lower())):
                LOG.debug("Found file: %s", os.path.abspath(os.path.join(root, name)))
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
    for filename in os.listdir(pjcfolder):
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
            LOG.debug("Creating media directory: %s", tmpdir_path)
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
        #
        #  Note that the PJC file contains the default mediapath stored in
        #   [Advanced][ImageDirectory=...]
        #  if more than one dataset is involved check each files Dataset ID is
        #  valid before extracting
        #
        #archive = tarfile.open(name)
        #for tarinfo in archive:
        #    archive.extract(tarinfo, tmpdir_path)
        #archive.close()
        pass
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


"The Master Genealogist (TMG) Backup File 'SQZ' reader and extracter"


#-------------------------------------------------------------------------
#
# TmgExtractSQZ function
#
#-------------------------------------------------------------------------
def TmgExtractSQZ(tmgsqzfilename):
    """
    Open a TMG SQZ file

    test sqz

    then extract all the files to a temp directory/location
    python namedtemp directory?
    """
    LOG.debug("TmgExtractSQZ: %s", tmgsqzfilename)

    # Open the TMG SQZ file as readonly
    try:
        # Test sqz file is a valid zipfile
        if zipfile.is_zipfile(tmgsqzfilename):
            LOG.debug("Is zipfile: %s", zipfile.is_zipfile(tmgsqzfilename))
            with zipfile.ZipFile(tmgsqzfilename, 'r') as tmgsqz:
                # Read the SQZ files filenames and paths

                tmgsqzfilenames = tmgsqz.namelist()
                #print("namelist", tmgsqzfilenames)
                LOG.debug("SQZ contains %s files", len(tmgsqzfilenames))

                # Check a TMG "Version Control File"(*.pjc/*.ver/*.tmg)
                # files exist in the SQZ
                # Early TMG versions used *.VER
                # TMG v4.x used *.TMG
                # TMG v5.x and higher use *.PJC
                for filename in tmgsqzfilenames:
                    if filename.endswith('.pjc') or filename.endswith('.PJC'):
                        tmgprojectfilename = filename
                        LOG.debug("PJC file: %s", tmgprojectfilename)
                    elif (filename.endswith('.tmg') or
                          filename.endswith('.TMG')):
                        # Present a notification message to Projects with
                        # (*.ver/*.tmg)
                        # eg:TMG v4 and earlier. That tmgimport only supports
                        # tmg versions 5.x to 9.x
                        tmgprojectfilenameold = filename
                        LOG.warning("Unsupported old TMG backup (.tmg): %s", tmgprojectfilenameold)
                        return
                    elif (filename.endswith('.ver') or
                          filename.endswith('.VER')):
                        # Present a notification message to Projects with
                        # (*.ver/*.tmg)
                        # eg:TMG v4 and earlier. That tmgimport only supports
                        # tmg versions 5.x to 9.x
                        tmgprojectfilenameevenolder = filename
                        LOG.warning("Unsupported very old TMG backup (.ver): %s", tmgprojectfilenameevenolder)
                        return
                    else:
                        LOG.error("Unrecognised TMG project version control file")
                        return

                # Extract the found (*.pjc)  to a temporary location

                # Read the (*.pjc) contents and report TMG version it was
                # created with along with some other information.

                pjccontents = StringIO(tmgsqz.read(tmgprojectfilename))
                LOG.debug("Reading PJC: %s", tmgprojectfilename)

                # PjcVersion=10.0
                # For the TMG Program Version; subtract 1 from the PjcVersion
                # number
                for line in pjccontents:
                    if line.startswith("PjcVersion=") > 0:
                        pjcversionraw = line

                LOG.debug("pjcversionraw: %s", pjcversionraw)
                pjcversionraw2 = pjcversionraw.rsplit('\r\n')
                LOG.debug("pjcversionraw2: %s", pjcversionraw2)
                pjcversionraw3 = pjcversionraw2[0].rsplit('=')
                LOG.debug("pjcversionraw3: %s", pjcversionraw3)
                pjcversion = pjcversionraw3[1]
                pjcversion = int(float(pjcversion) - 1)
                LOG.debug("TMG pjc version: %s", pjcversion)

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
            LOG.error("%s is not a TMG SQZ file or was created in TMG version 4.x or earlier", tmgsqzfilename)
            return
    except IOError:
        return
#------------------------------------------------------------------------
#
#  TMG Backup File 'SQZ' reader and extracter
#  END
#------------------------------------------------------------------------
