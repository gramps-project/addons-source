#! /usr/bin/env python

import glob
import os
import sys
from optparse import OptionParser, OptionGroup


if sys.platform == 'win32':    
      
    # GetText Win 32 obtained from http://gnuwin32.sourceforge.net/packages/gettext.htm
    # ....\gettext\bin\msgmerge.exe needs to be on the path
    
    msginitCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msginit.exe')
    msgmergeCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgmerge.exe')
    msgfmtCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'msgfmt.exe')
    xgettextCmd = os.path.join('C:', 'Program Files(x86)', 'gettext', 'bin', 'xgettext.exe')
    
    pythonCmd = os.path.join(sys.prefix, 'bin', 'python.exe')
    
    # GNU tools
    
    sedCmd = os.path.join('C:', 'Program Files(x86)', 'sed.exe')
    mkdirCmd = os.path.join('C:', 'Program Files(x86)', 'mkdir.exe')
    tarCmd = os.path.join('C:', 'Program Files(x86)', 'tar.exe')
    
elif sys.platform == 'linux2' or os.name == 'darwin':
    
    msginitCmd = 'msginit'
    msgmergeCmd = 'msgmerge'
    msgfmtCmd = 'msgfmt'
    xgettextCmd = 'xgettext'
    
    pythonCmd = os.path.join(sys.prefix, 'bin', 'python')
    
    sedCmd = 'sed'
    mkdirCmd = 'mkdir'
    tarCmd = 'tar'
    
GNU = [sedCmd, mkdirCmd, tarCmd]
    
    
if "GRAMPSPATH" in os.environ:
    GRAMPSPATH = os.environ["GRAMPSPATH"]
else:
    GRAMPSPATH = "../../../.."

if not os.path.isdir(GRAMPSPATH + "/po"):
    raise ValueError("Where is GRAMPSPATH/po: '%s/po'? Use 'GRAMPSPATH=path python make.py ...'" % GRAMPSPATH)


def tests():
    """
    Testing installed programs.
    We made tests (-t flag) by displaying versions of tools if properly
    installed. Cannot run all commands without 'gettext' and 'python'.
    """
    
    try:
        print("\n====='msginit'=(create your translation)================\n")
        os.system('''%(program)s -V''' % {'program': msginitCmd})
    except:
        print('Please, install %(program)s for creating your translation' % {'program': msginitCmd})
        
    
    try:
        print("\n====='msgmerge'=(merge our translation)================\n")
        os.system('''%(program)s -V''' % {'program': msgmergeCmd})
    except:
        print('Please, install %(program)s for updating your translation' % {'program': msgmergeCmd})
        
    try:
        print("\n==='msgfmt'=(format our translation for installation)==\n")
        os.system('''%(program)s -V''' % {'program': msgfmtCmd})
    except:
        print('Please, install %(program)s for checking your translation' % {'program': msgfmtCmd})
            
    try:
        print("\n===='xgettext' =(generate a new template)==============\n")
        os.system('''%(program)s -V''' % {'program': xgettextCmd})
    except:
        print('Please, install %(program)s for generating a new template' % {'program': xgettextCmd})
    
    try:
        print("\n=================='python'=============================\n")
        os.system('''%(program)s -V''' % {'program': pythonCmd})
    except:
        print('Please, install python')
     
    for program in GNU:
        try:
            print("\n=================='%s'=============================\n" % program)
            os.system('''%s --help''' % program)
        except:
            print('Please, install or set path for GNU tool: %s' % program)
        
    
def main():
    """
    The utility for handling lxml addon.
    """
    
    parser = OptionParser( 
                         description='This specific script build lxml addon', 
                         usage='%prog [options]'
                         )
                         
    translating = OptionGroup(
                          parser, 
                          "Translations Options", 
                          "Everything around translations for lxml addon."
                          )   
    parser.add_option_group(translating)
    
    building = OptionGroup(
                          parser, 
                          "Build Options", 
                          "Everything around lxml package."
                          )   
    parser.add_option_group(building)
    
    parser.add_option("-t", "--test",
			  action="store_true", dest="test", default=False,
			  help="test if programs are properly installed")
                                       
    translating.add_option("-i", "--init",
			  action="store_true", dest="init", default=False,
			  help="create the environment")
    translating.add_option("-u", "--update",
			  action="store_true", dest="update", default=False,
			  help="update the translation")
              
    building.add_option("-c", "--compile",
			  action="store_true", dest="compilation", default=False,
			  help="compile translation files for generating lxml package")
    building.add_option("-b", "--build",
			  action="store_true", dest="build", default=False,
			  help="build lxml package")
    building.add_option("-r", "--clean",
			  action="store_true", dest="clean", default=False,
			  help="remove files generated by building process")
    
    (options, args) = parser.parse_args()
    
    if options.test:
        tests()
       
    if options.init:
        init(args)
        
    if options.update:
        update(args)
        
    if options.compilation:
        compilation()
        
    if options.build:
        build()
        
    if options.clean:
        clean()
      
        
def versioning():
    """
    Update gpr.py version
    """
    
    f = open('lxmlGramplet.gpr.py', "r")
    lines = [file.strip() for file in f]
    f.close() 
    
    upf = open('lxmlGramplet.gpr.py', "w")
    
    for line in lines:
        if ((line.lstrip().startswith("version")) and 
            ("=" in line)):
            print("orig = %s" % line.rstrip())
            
            line, stuff = line.rsplit(",", 1)
            line = line.rstrip()
            pos = line.index("version")
            
            indent = line[0:pos]
            var, gtv = line[pos:].split('=', 1)
            lyst = version(gtv.strip()[1:-1])
            lyst[2] += 1
            
            newv = ".".join(map(str, lyst))
            newline = "%sversion = '%s'," % (indent, newv)
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
    
    if not args:
        os.system('''%(mkdir)s -p "po"''' % {'mkdir': mkdirCmd}
                 )
        template()
        
    if not os.path.isfile('''po/template.pot'''):
        template()

    if len(args) > 0:
        os.system('''%(mkdir)s -p "locale"''' % {'mkdir': mkdirCmd}
                 )
        for arg in args:
            if os.path.isfile('''po/%s-local.po''' % arg):
                print('''"po/%s-local.po" already exists!''' % arg)
            else:
                os.system('''%(msginit)s --locale=%(arg)s ''' 
                          '''--input="po/template.pot" '''
                          '''--output="po/%(arg)s-local.po"'''
                          % {'msginit': msginitCmd, 'arg': arg} 
                          )
                print('''You can now edit "po/%s-local.po"''' % arg)


def template():
    """
    Generates the template.pot for the lxml addon.
    """
    
    os.system('''xgettext --language=Python --keyword=_ --keyword=N_'''
              ''' --from-code=UTF-8 -o "po/template.pot" *.py''' 
              % {'xgettext': xgettextCmd}
             )
    os.system('''%(sed)s -i 's/charset=CHARSET/charset=UTF-8/' '''
              '''"po/template.pot"''' % {'sed': sedCmd}
             )
    
    
def update(args):
    """
    Updates po/x-local.po with the latest translations.
    """ 
        
    if not args:
        os.system('''%(mkdir)s -p "po"''' % {'mkdir': mkdirCmd}
                 )
        template()

    if len(args) > 0:
        if not os.path.isfile('''po/template.pot'''):
            template()
            
        os.system('''%(mkdir)s -p "locale"''' % {'mkdir': mkdirCmd}
                 )
                 
        for arg in args:
            if os.path.isfile('''po/%s-local.po''' % arg):
                
                # Retrieve updated data for locale
                
                os.system('''%(msginit)s --locale=%(arg)s ''' 
                          '''--input="po/template.pot" '''
                          '''--output="po/%(arg)s.po"'''
                          % {'msginit': msginitCmd, 'arg': arg} 
                          )
            else:
                init([arg])
                        
            memory(arg)
            
            
    # TODO: merge back

def memory(arg):
    """
    Translation memory for Gramps (own dictionary: msgid/msgstr)
    """
    
    if not os.path.isfile('''po/%s.po''' % arg):
        os.system('''%(msginit)s --locale=%(arg)s ''' 
                  '''--input="po/template.pot" '''
                  '''--output="po/%(arg)s.po"'''
                  % {'msginit': msginitCmd, 'arg': arg} 
                 )
    
    # Start with Gramps main PO file
    # entries for others addons are missing
    
    locale_po_files = "%(GRAMPSPATH)s/po/%(arg)s.po" % {'GRAMPSPATH': GRAMPSPATH, 'arg': arg}
    
    # Merge global dict with a temp file
    
    if os.path.isfile(locale_po_files):
        print('Merge temp data: "po/%(arg)s.po with %(global)s"' % {'global': locale_po_files, 'arg': arg})
        os.system('''%(msgmerge)s %(global)s po/%(arg)s.po -o po/%(arg)s.po'''
                  % {'msgmerge': msgmergeCmd, 'global': locale_po_files, 'arg': arg} 
                 )
                 
    
def compilation():
    """
    Compile translations
    """
    
    for po in glob.glob(os.path.join('po', '*-local.po')):
        f = os.path.basename(po[:-3])
        mo = os.path.join('locale', f[:-6], 'LC_MESSAGES/', 'gramps.mo')
        directory = os.path.dirname(mo)
        if not os.path.exists(directory):
            os.makedirs(directory)
        os.system('%s po/%s.po -o %s' % (msgfmtCmd, f, mo)
                 )
        print(directory, f[:-6])
           
               
def build():
    """
    Build ../../download/AddonDirectory.addon.tgz
    """
        
    compilation()
    versioning()
    
    files = []
    files += glob.glob('''lxmlGramplet.py''')
    files += glob.glob('''lxmlGramplet.gpr.py''')
    files += glob.glob('''grampsxml.dtd''')
    files += glob.glob('''grampsxml.rng''')
    files += glob.glob('''lxml.css''')
    files += glob.glob('''query_html.xsl''')
    files += glob.glob('''locale/*/LC_MESSAGES/*.mo''')
    files_str = " ".join(files)
    os.system('''%(mkdir)s -p ../../download ''' % {'mkdir': mkdirCmd}
             )
    os.system('''%(tar)s cfz "../../download/lxml.addon.tgz" %(files_list)s''' 
              % {'tar': tarCmd, 'files_list': files_str}
              )
    
    
def clean():
    """
    Remove created files
    """
    pass  
     
     
if __name__ == "__main__":
	main()
