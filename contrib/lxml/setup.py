# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank
# Copyright (C) 2012  Jerome Rapinat
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

#! /usr/bin/env python

import glob
import os
import sys
from argparse import ArgumentParser

ADDON = 'lxmlGramplet'

ALL_LINGUAS=["en", # translation template
             "all", # all entries
             "bg",
             "ca",
             "cs",
             "da",
             "de",
             "es",
             "fi",
             "fr",
             "he",
             "hr",
             "hu",
             "it",
             "ja",
             "lt",
             "nb",
             "nl",
             "nn",
             "pl",
             "pt_BR",
             "pt_PT",
             "ru",            
             "sk",
             "sl",
             "sq",
             "sv",           
             "uk",
             "vi",
             "zh_CN",
             ]

if sys.platform == 'win32':    
      
    # GetText Win 32 obtained from http://gnuwin32.sourceforge.net/packages/gettext.htm
    # ....\gettext\bin\msgmerge.exe needs to be on the path
    
    msginitCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msginit.exe')
    msgmergeCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgmerge.exe')
    msgfmtCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgfmt.exe')
    msgcatCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgcat.exe')
    msggrepCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msggrep.exe')
    msgcmpCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgcmp.exe')
    msgattribCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgattrib.exe')
    xgettextCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'xgettext.exe')
    
    pythonCmd = os.path.join(sys.prefix, 'bin', 'python.exe')
    
    # GNU tools
    # see http://gnuwin32.sourceforge.net/packages.html
    
    sedCmd = os.path.join('C:', 'Program Files(x86)', 'sed.exe') # sed
    mkdirCmd = os.path.join('C:', 'Program Files(x86)', 'mkdir.exe') # CoreUtils
    rmCmd = os.path.join('C:', 'Program Files(x86)', 'rm.exe') # CoreUtils
    tarCmd = os.path.join('C:', 'Program Files(x86)', 'tar.exe') # tar
    
elif sys.platform in ['linux2', 'darwin', 'cygwin']:
    
    msginitCmd = 'msginit'
    msgmergeCmd = 'msgmerge'
    msgfmtCmd = 'msgfmt'
    msgcatCmd = 'msgcat'
    msggrepCmd = 'msggrep'
    msgcmpCmd = 'msgcmp'
    msgattribCmd = 'msgattrib'
    xgettextCmd = 'xgettext'
    
    pythonCmd = os.path.join(sys.prefix, 'bin', 'python')
    
    sedCmd = 'sed'
    mkdirCmd = 'mkdir'
    rmCmd = 'rm'
    tarCmd = 'tar'
    
else:
    print ("ERROR: unknown system, don't know msgmerge, ... commands")
    sys.exit(0)
    
GNU = [sedCmd, mkdirCmd, rmCmd, tarCmd]
    

def tests():
    """
    Testing installed programs.
    We made tests (-t flag) by displaying versions of tools if properly
    installed. Cannot run all commands without 'gettext' and 'python'.
    """
    
    try:
        print("\n====='msginit'=(create your translation)===============\n")
        os.system('''%(program)s -V''' % {'program': msginitCmd})
    except:
        raise ValueError('Please, install %(program)s for creating your translation' % {'program': msginitCmd})
    
    try:
        print("\n====='msgmerge'=(merge your translation)===============\n")
        os.system('''%(program)s -V''' % {'program': msgmergeCmd})
    except:
        raise ValueError('Please, install %(program)s for updating your translation' % {'program': msgmergeCmd})
        
    try:
        print("\n=='msgfmt'=(format your translation for installation)==\n")
        os.system('''%(program)s -V''' % {'program': msgfmtCmd})
    except:
        raise ValueError('Please, install %(program)s for checking your translation' % {'program': msgfmtCmd})
    
    try:
        print("\n==='msgcat'=(concate translations)=====================\n")
        os.system('''%(program)s -V''' % {'program': msgcatCmd})
    except:
        raise ValueError('Please, install %(program)s for concating translations' % {'program': msgcatCmd})
    
    try:
        print("\n===='msggrep'==(extract messages from catalog)=========\n")
        os.system('''%(program)s -V''' % {'program': msggrepCmd})
    except:
        raise ValueError('Please, install %(program)s for extracting messages' % {'program': msggrepCmd})

    try:
        print("\n===='msgcmp'==(compare two gettext files)===============\n")
        os.system('''%(program)s -V''' % {'program': msgcmpCmd})
    except:
        raise ValueError('Please, install %(program)s for comparing gettext files' % {'program': msgcmpCmd})
        
    try:
        print("\n===='msgattrib'==(list groups of messages)=============\n")
        os.system('''%(program)s -V''' % {'program': msgattribCmd})
    except:
        raise ValueError('Please, install %(program)s for listing groups of messages' % {'program': msgattribCmd})
        
    try:
        print("\n===='xgettext' =(generate a new template)==============\n")
        os.system('''%(program)s -V''' % {'program': xgettextCmd})
    except:
        raise ValueError('Please, install %(program)s for generating a new template' % {'program': xgettextCmd})
    
    try:
        print("\n=================='python'=============================\n")
        os.system('''%(program)s -V''' % {'program': pythonCmd})
    except:
        raise ValueError('Please, install python')
     
    for program in GNU:
        try:
            print("\n=================='%s'=============================\n" % program)
            os.system('''%s --version''' % program)
        except:
            raise ValueError('Please, install or set path for GNU tool: %s' % program)
        
    
def main():
    """
    The utility for handling lxml addon.
    """
    
    parser = ArgumentParser( 
                         description='This specific script build lxml addon', 
                         )
                         
    parser.add_argument("-t", "--test",
			  action="store_true", dest="test", default=True,
			  help="test if programs are properly installed")
              
    translating = parser.add_argument_group(
                                           "Translations Options", 
                                           "Everything around translations for lxml addon."
                                           )
    building = parser.add_argument_group(
                                        "Build Options", 
                                        "Everything around lxml package."
                                        )
                                           
    translating.add_argument("-i", dest="init", default=False,
              choices=ALL_LINGUAS,
			  help="create the environment")
    translating.add_argument("-u", dest="update", default=False,
              choices=ALL_LINGUAS,
			  help="update the translation")
              
    building.add_argument("-c", "--compile",
			  action="store_true", dest="compilation", default=False,
			  help="compile translation files for generating lxml package")
    building.add_argument("-b", "--build",
			  action="store_true", dest="build", default=False,
			  help="build lxml package")
    building.add_argument("-r", "--clean",
			  action="store_true", dest="clean", default=False,
			  help="remove files generated by building process")
    
    args = parser.parse_args()
    
    if args.test:
        tests()
       
    if args.init:
        if sys.argv[2:] == ['all']:
            sys.argv[2:] = ALL_LINGUAS
        init(sys.argv[2:])
        
    if args.update:
        if sys.argv[2:] == ['all']:
            sys.argv[2:] = ALL_LINGUAS
        update(sys.argv[2:])
        
    if args.compilation:
        compilation()
        
    if args.build:
        build()
        
    if args.clean:
        clean()
        
        
def versioning():
    """
    Update gpr.py version
    """
    
    f = open('%s.gpr.py' % ADDON, "r")
    lines = [file.strip() for file in f]
    f.close() 
    
    upf = open('%s.gpr.py' % ADDON, "w")
    
    for line in lines:
        if ((line.lstrip().startswith("version")) and 
            ("=" in line)):
            print("orig %s" % line.rstrip())
            
            line, stuff = line.rsplit(",", 1)
            line = line.rstrip()
            pos = line.index("version")
            
            indent = line[0:pos]
            var, gtv = line[pos:].split('=', 1)
            lyst = version(gtv.strip()[1:-1])
            lyst[2] += 1
            
            newv = ".".join(map(str, lyst))
            newline = "%sversion = '%s'," % (indent, newv)
            print("new %s" % newline.rstrip())
            upf.write('%s\n' % newline)
        else:
            upf.write('%s\n' % line)
    upf.close()
        
        
def myint(s):
    """
    Protected version of int()
    """
    try:
        v = int(s)
    except:
        v = s
    return v
        
        
def version(sversion):
    """
    Return the tuple version of a string version.
    """
    return [myint(x or "0") for x in (sversion + "..").split(".")][0:3]
       
                
def init(args):
    """
    Creates the initial empty po/x-local.po file and generates the 
    template.pot for the lxml addon.
    """    
    
    os.system('''%(mkdir)s -pv "po"''' % {'mkdir': mkdirCmd})
    
    template()

    if len(args) > 0:
        for arg in args:
            if os.path.isfile('''po/%s-local.po''' % arg):
                print('''"po/%s-local.po" already exists!''' % arg)
            else:
                os.system('''%(msginit)s --locale=%(arg)s ''' 
                          '''--input="po/template.pot" '''
                          '''--output="po/%(arg)s-local.po"'''
                          % {'msginit': msginitCmd, 'arg': arg} 
                          )
                print('''You can now edit "po/%s-local.po"!''' % arg)


def template():
    """
    Generates the template.pot for the lxml addon.
    """
    
    os.system('''%(xgettext)s --language=Python --keyword=_ --keyword=N_'''
              ''' --from-code=UTF-8 -o "po/template.pot" *.py''' 
              % {'xgettext': xgettextCmd}
             )
             
    if os.path.isfile('%s.glade' % ADDON):
        os.system('''%(xgettext)s --add-comments -j -L Glade '''
                  '''--from-code=UTF-8 -o "po/template.pot" *.glade'''
                  % {'xgettext': xgettextCmd}
                 )
    
    if os.path.isfile('%s.xml' % ADDON):         
        xml()
        os.system('''%(xgettext)s --keyword=N_ --add-comments -j'''
                  ''' --from-code=UTF-8 -o "po/template.pot" xml.h''' 
                  % {'xgettext': xgettextCmd}
                  )
                                      
    os.system('''%(sed)s -i 's/charset=CHARSET/charset=UTF-8/' '''
              '''"po/template.pot"''' % {'sed': sedCmd}
             )
             

def xml():
    """
    Experimental alternative to 'intltool-extract' for 'census.xml'.
    """
    
    # in progress ...
    from xml.etree import ElementTree
    
    tree = ElementTree.parse('census.xml')
    root = tree.getroot()
       
    '''
    <?xml version="1.0" encoding="UTF-8"?>
    <censuses>
        <census id='UK1841' title='1841 UK Census' date='6 Jun 1841'>
            <heading>
                <_attribute>City or Borough</_attribute>
            </heading>
            <heading>
                <_attribute>Parish or Township</_attribute>
            </heading>
            <column>
                <_attribute>Name</_attribute>
                <size>25</size>
            </column>
            <column>
                <_attribute>Age</_attribute>
                <size>5</size>
            </column>
        
    char *s = N_("City or Borough");
    
    template.pot:
    msgid "City or Borough"
    '''
    
    catalog = open('xml.h', 'w')
    
    for key in root.iter('_attribute'):
        catalog.write('char *s = N_("%s");\n' % key.text)
        
    catalog.close()
        
    root.clear()
    
    
def update(args):
    """
    Updates po/x-local.po with the latest translations.
    """ 
        
    os.system('''%(mkdir)s -pv "po"''' % {'mkdir': mkdirCmd})
    
    template()
                 
    if len(args) > 0:                
        for arg in args:
                        
            if os.path.isfile('''po/%s-local.po''' % arg):
                
                # create a temp header file (time log)
                
                temp(arg)
                
            else:
                
                # create the locale-local.po file
                
                init([arg])
                
                # create a temp header file (time log)
                
                temp(arg)
                
            # merge data from previous translation to the temp one
            
            print('Merge "po/%(arg)s.po" with "po/%(arg)s-local.po":' % {'arg': arg})
    
            os.system('''%(msgmerge)s po/%(arg)s-local.po po/%(arg)s.po'''
                      ''' -o po/%(arg)s.po --no-location -v'''
                      % {'msgmerge': msgmergeCmd, 'arg': arg} 
                      )
                        
            memory(arg)
            
            # like template (msgid) with last message strings (msgstr)
            
            print('Merge "po/%s.po" with "po/template.pot":' % arg)
            
            os.system('''%(msgmerge)s -U po/%(arg)s.po'''
                      ''' po/template.pot -v'''
                      % {'msgmerge': msgmergeCmd, 'arg': arg} 
                      )
                      
            # only used messages (need) and merge back
            
            print('Move content to "po/%s-local.po".' % arg)
            
            os.system('''%(msgattrib)s --no-obsolete'''
                      ''' po/%(arg)s.po -o po/%(arg)s-local.po'''
                      % {'msgattrib': msgattribCmd, 'arg': arg} 
                      )
            
            # remove temp locale.po file
            
            os.system('''%(rm)s -rf -v po/%(arg)s.po'''
                      % {'rm': rmCmd, 'arg': arg}
                      ) 
                      
            print('''You can now edit "po/%s-local.po"!''' % arg)
                      
            
def temp(arg):
    """
    Generate a temp file for header (time log) and Translation Memory
    """
    
    os.system('''%(msginit)s --locale=%(arg)s ''' 
              '''--input="po/template.pot" '''
              '''--output="po/%(arg)s.po" --no-translator'''
              % {'msginit': msginitCmd, 'arg': arg} 
              )
    
            
def memory(arg):
    """
    Translation memory for Gramps (own dictionary: msgid/msgstr)
    """
    
    if "GRAMPSPATH" in os.environ:
        GRAMPSPATH = os.environ["GRAMPSPATH"]
    else:
        GRAMPSPATH = "../../../.."

    if not os.path.isdir(GRAMPSPATH + "/po"):
        raise ValueError("Where is GRAMPSPATH/po: '%s/po'? Use 'GRAMPSPATH=path python setup.py ...'" % GRAMPSPATH)
                               
    # Get all of the addon strings out of the catalog
        
    os.system('''%(msggrep)s --location=../*'''
              ''' po/template.pot --output-file=po/%(arg)s-temp.po'''
              % {'msggrep': msggrepCmd, 'arg': arg} 
              )
    
    # start with Gramps main PO file
    
    locale_po_files = "%(GRAMPSPATH)s/po/%(arg)s.po" % {'GRAMPSPATH': GRAMPSPATH, 'arg': arg}
    
    # concat global dict as temp file
    
    if os.path.isfile(locale_po_files):
        print('Concat temp data: "po/%(arg)s.po" with "%(global)s".' % {'global': locale_po_files, 'arg': arg})
            
        os.system('''%(msgcat)s --use-first po/%(arg)s.po'''
                  ''' %(global)s -o po/%(arg)s.po --no-location'''
                  % {'msgcat': msgcatCmd, 'global': locale_po_files, 'arg': arg} 
                  )
        os.system('''%(msgcmp)s -m --use-fuzzy --use-untranslated'''
                  ''' po/%(arg)s.po %(global)s'''
                  % {'msgcmp': msgcmpCmd, 'global': locale_po_files , 'arg': arg} 
                  )
                
    if os.path.isfile('po/%s-temp.po' % arg):
        print('Concat temp data: "po/%(arg)s.po" with "po/%(arg)s-temp.po".' % {'arg': arg})
                  
        os.system('''%(msgcat)s --use-first po/%(arg)s.po'''
                  ''' po/%(arg)s-temp.po -o po/%(arg)s.po --no-location'''
                  % {'msgcat': msgcatCmd, 'arg': arg} 
                  )
                  
        print('''Remove temp "po/%s-temp.po".''' % arg)
            
        os.system('''%(rm)s -rf -v po/%(arg)s-temp.po'''
                  % {'rm': rmCmd, 'arg': arg}
                 )
                                  
    
def compilation():
    """
    Compile translations
    """
    
    os.system('''%(mkdir)s -pv "locale"''' % {'mkdir': mkdirCmd})
    
    for po in glob.glob(os.path.join('po', '*-local.po')):
        f = os.path.basename(po[:-3])
        mo = os.path.join('locale', f[:-6], 'LC_MESSAGES', 'addon.mo')
        directory = os.path.dirname(mo)
        if not os.path.exists(directory):
            os.makedirs(directory)
        os.system('%s po/%s.po -o %s' % (msgfmtCmd, f, mo)
                 )
           
               
def build():
    """
    Build ../../download/AddonDirectory.addon.tgz
    """
        
    compilation()
    versioning()
    
    files = []
    files += glob.glob('''%s.py''' % ADDON)
    files += glob.glob('''%s.gpr.py''' % ADDON)
    files += glob.glob('''grampsxml.dtd''')
    files += glob.glob('''grampsxml.rng''')
    files += glob.glob('''grampsxml.xsd''')
    files += glob.glob('''lxml.css''')
    files += glob.glob('''query_html.xsl''')
    files += glob.glob('''locale/*/LC_MESSAGES/*.mo''')
    files += glob.glob('''*.glade''')
    files += glob.glob('''*.xml''')
    files_str = " ".join(files)
    os.system('''%(mkdir)s -pv ../../download ''' % {'mkdir': mkdirCmd}
             )
    os.system('''%(tar)s cfzv "../../download/%(addon)s.addon.tgz" %(files_list)s''' 
              % {'tar': tarCmd, 'files_list': files_str, 'addon': ADDON}
              )
    
    
def clean():
    """
    Remove created files
    """
    
    os.system('''%(rm)s -rfv '''
              '''*~ '''
              '''po/*~ '''
              '''po/template.pot '''
              '''locale '''
              '''*.pyc '''
              '''*.pyo '''
              '''xml.h '''
              % {'rm': rmCmd}
              ) 
    
     
if __name__ == "__main__":
	main()
