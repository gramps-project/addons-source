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

"Import from TMG (The Master Genealogist) Projects"

#TODO Merge into libtmg.py
# and have gramps....importtmg.py  import the function to read the sqz

"The Master Genealogist (TMG) Backup File 'SQZ' reader and extracter"

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import zipfile    #used to read sqz
import sys
from StringIO import StringIO   # used to read sqz

#------------------------------------------------------------------------
#
# Set up logging
#
#------------------------------------------------------------------------
import logging
LOG = logging.getLogger(".TMGImport")

#-------------------------------------------------------------------------
#
# importData
#
#-------------------------------------------------------------------------
def TmgExtractSQZ(tmgsqzfilename):  #TODO split into separate functions
    """
    Open a TMG SQZ file
    
    test sqz
    
    then extract all the files to a temp directory/location python namedtemp directory?
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

                # Check a TMG "Version Control File"(*.pjc/*.ver/*.tmg) files exist in the SQZ
                # Early TMG versions used *.VER
                # TMG v4.x used *.TMG
                # TMG v5.x and higher use *.PJC
                for filename in tmgsqzfilenames:
                    if filename.endswith('.pjc') or filename.endswith('.PJC'):
                        tmgprojectfilename = filename
                        print("tmgprojectfilename:", tmgprojectfilename)
                    elif filename.endswith('.tmg') or filename.endswith('.TMG'):
                        # Present a notification message to Projects with (*.ver/*.tmg) 
                        # eg:TMG v4 and earlier. That tmgimport only supports tmg versions 5.x to 9.x
                        tmgprojectfilenameold = filename
                        print("tmgprojectfilename old:", tmgprojectfilenameold)
                        return
                    elif filename.endswith('.ver') or filename.endswith('.VER'):
                        # Present a notification message to Projects with (*.ver/*.tmg) 
                        # eg:TMG v4 and earlier. That tmgimport only supports tmg versions 5.x to 9.x
                        tmgprojectfilenameevenolder = filename
                        print("tmgprojectfilename even older:", tmgprojectfilenameevenolder)
                        return
                    else:
                        print("Are you sure this is a tmgprojectfilename? if so contact me.")
                        return

                # Extract the found (*.pjc)  to a temporary location
                
                # Read the (*.pjc) contents and report TMG version it was created with
                # along with some other information.
                
                pjccontents = StringIO(tmgsqz.read(tmgprojectfilename))
                print(tmgprojectfilename, ':')
                
                # PjcVersion=10.0
                # For the TMG Program Version; subtract 1 from the PjcVersion number
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
                
                # Present a drop down box to select only one of the TMG "Data Sets" to be imported.
                # (I believe Gramps can only have one family tree open at a time, 
                #  and muliple dataset can not be shown in the list views eglike tmgs 1:23, 2:13)
                
                # Test the TMG SQZ for Internal exhibits 
                # http://tmg.reigelridge.com/exhibits.htm
                # Mention that: John Cardinal's TMG Utility will 
                # convert internal exhibits to external...see http://www.johncardinal.com/tmgutil/
                # In TMG Utility, try the Other->Export Data option and select Exhibit Log;
                # after you've chosen where to save it, you'll be prompted;
                # http://www.johncardinal.com/tmgutil/exportimages.htm#task1
                
        else:
            # Display an informational popup
            # http://www.whollygenes.com/forums201/index.php?/topic/14299-opening-old-sqz-files/?p=57594
            # Early TMG versions used the FoxPro SQZ file as a backup archive 
            # and this is not a ZIP file.
            # If the file came from TMG prior to v5, in a trial version of TMG you should 
            # try import, not restore. File / Import
            # Select 'The Master Genealogist v4.x or earlier BACKUP (*.SQZ)'.
            # That may or may not work.
            # If the SQZ came from an early version of TMG, you might need to talk to 
            # Whollygenes  Support and they will want to examine the file.
            # There are also other genealogy databases that used the .SQZ file extension: 
            # Family Gathering, Roots IV, Roots V, Ultimate Family Tree, Visual Roots.
            print(tmgsqzfilename, "is not a TMG SQZ file or \
                  was created in TMG version 4.x or earlier")
            return
    except IOError:
        return
    

