#!/usr/bin/python
# -*- coding: utf-8 -*-

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

"""
setup.py for Gramps addons.

Examples: 
   python setup.py -i or --init AddonDirectory

      Creates the initial directories for the addon.

   python setup.py -i or --init AddonDirectory fr

      Creates the initial empty AddonDirectory/po/fr-local.po file
      for the addon.

   python setup.py -u or --update AddonDirectory fr

      Updates AddonDirectory/po/fr-local.po with the latest
      translations.

   python setup.py -b or --build AddonDirectory

      Build ../download/AddonDirectory.addon.tgz

   python setup.py -b or --build ALL

      Build ../download/*.addon.tgz

   python setup.py -c or --compile AddonDirectory
   python setup.py -c or --compile ALL

      Compiles AddonDirectory/po/*-local.po and puts the resulting
      .mo file in AddonDirectory/locale/*/LC_MESSAGES/addon.mo

   python3 setup.py -l or --listing AddonDirectory
   python3 setup.py -l or --listing all

   python setup.py -c or --clean AddonDirectory
   python setup.py -c or --clean ALL
"""

import shutil
import glob
import os
import sys
from argparse import ArgumentParser

ADDONS = sorted([name for name in os.listdir('.')
                if os.path.isdir(name) and not name.startswith('.')])

ALL_ADDONS = ADDONS.append('ALL')

LINGUAS = ( # translation template
    'en',
    'bg',
    'ca',
    'cs',
    'da',
    'de',
    'es',
    'en_GB',
    'fi',
    'fr',
    'he',
    'hr',
    'hu',
    'it',
    'ja',
    'lt',
    'mk',
    'nb',
    'nl',
    'nn',
    'pl',
    'pt_BR',
    'pt_PT',
    'ru',
    'sk',
    'sl',
    'sq',
    'sv',
    'uk',
    'vi',
    'zh_CN',
    )

ALL_LINGUAS = ADDONS.append('all')

if sys.platform == 'win32':

    # GetText Win 32 obtained from http://gnuwin32.sourceforge.net/packages/gettext.htm
    # ....\gettext\bin\msgmerge.exe needs to be on the path

    msginitCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                              'bin', 'msginit.exe')
    msgmergeCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                               'bin', 'msgmerge.exe')
    msgfmtCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                             'bin', 'msgfmt.exe')
    msgcatCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                             'bin', 'msgcat.exe')
    msggrepCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                              'bin', 'msggrep.exe')
    msgcmpCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                             'bin', 'msgcmp.exe')
    msgattribCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                                'bin', 'msgattrib.exe')
    xgettextCmd = os.path.join('C:', 'Program Files(x86)', 'gettext',
                               'bin', 'xgettext.exe')

    pythonCmd = os.path.join(sys.prefix, 'bin', 'python.exe')

    # GNU tools
    # see http://gnuwin32.sourceforge.net/packages.html

    sedCmd = os.path.join('C:', 'Program Files(x86)', 'sed.exe')  # sed
    mkdirCmd = os.path.join('C:', 'Program Files(x86)', 'mkdir.exe')  # CoreUtils
    rmCmd = os.path.join('C:', 'Program Files(x86)', 'rm.exe')  # CoreUtils
    tarCmd = os.path.join('C:', 'Program Files(x86)', 'tar.exe')  # tar
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

    print("ERROR: unknown system, don't know commands")
    sys.exit(0)

GNU = [sedCmd, mkdirCmd, rmCmd, tarCmd]


def tests():
    """
    Testing installed programs.
    We made tests (-t flag) by displaying versions of tools if properly
    installed. Cannot run all commands without 'gettext' and 'python'.
    """

    try:
        print("""
====='msginit'=(create your translation)===============
""")
        os.system('%(program)s -V' % {'program': msginitCmd})
    except:
        raise ValueError('Please, install %(program)s for creating your translation'
                          % {'program': msginitCmd})

    try:
        print("""
====='msgmerge'=(merge your translation)===============
""")
        os.system('%(program)s -V' % {'program': msgmergeCmd})
    except:
        raise ValueError('Please, install %(program)s for updating your translation'
                          % {'program': msgmergeCmd})

    try:
        print("""
=='msgfmt'=(format your translation for installation)==
""")
        os.system('%(program)s -V' % {'program': msgfmtCmd})
    except:
        raise ValueError('Please, install %(program)s for checking your translation'
                          % {'program': msgfmtCmd})

    try:
        print("""
==='msgcat'=(concate translations)=====================
""")
        os.system('%(program)s -V' % {'program': msgcatCmd})
    except:
        raise ValueError('Please, install %(program)s for concating translations'
                          % {'program': msgcatCmd})

    try:
        print("""
===='msggrep'==(extract messages from catalog)=========
""")
        os.system('%(program)s -V' % {'program': msggrepCmd})
    except:
        raise ValueError('Please, install %(program)s for extracting messages'
                          % {'program': msggrepCmd})

    try:
        print("""
===='msgcmp'==(compare two gettext files)===============
""")
        os.system('%(program)s -V' % {'program': msgcmpCmd})
    except:
        raise ValueError('Please, install %(program)s for comparing gettext files'
                          % {'program': msgcmpCmd})

    try:
        print("""
===='msgattrib'==(list groups of messages)=============
""")
        os.system('%(program)s -V' % {'program': msgattribCmd})
    except:
        raise ValueError('Please, install %(program)s for listing groups of messages'
                          % {'program': msgattribCmd})

    try:
        print("""
===='xgettext' =(generate a new template)==============
""")
        os.system('%(program)s -V' % {'program': xgettextCmd})
    except:
        raise ValueError('Please, install %(program)s for generating a new template'
                          % {'program': xgettextCmd})

    try:
        print("""
=================='python'=============================
""")
        os.system('%(program)s -V' % {'program': pythonCmd})
    except:
        raise ValueError('Please, install python')

    for program in GNU:
        try:
            print("""
=================='%s'=============================
"""
                  % program)
            os.system('%s --version' % program)
        except:
            raise ValueError('Please, install or set path for GNU tool: %s'
                              % program)


def main():
    """
    The utility for handling addon.
    """

    parser = \
        ArgumentParser(description='This specific script build addon',
                       add_help=True, version='0.1.4')

    #parser.add_argument('addon', choices=ADDONS)

    parser.add_argument('lang', nargs='?', const=LINGUAS,
                        default='en')

    # parser.add_argument("-t", "--test",
    # action="store_true", dest="test", default=True,
    # help="test if programs are properly installed")

    translating = parser.add_argument_group('Translations Options',
            'Everything around translations for addon.')
    building = parser.add_argument_group('Build Options',
            'Everything around package.')

    translating.add_argument(
        '-i',
        '--init',
        choices=ALL_ADDONS,
        dest='init',
        default=False,
        help='create the environment',
        )
    translating.add_argument(
        '-u',
        '--update',
        choices=ALL_ADDONS,
        dest='update',
        default=False,
        help='update the translation',
        )

    building.add_argument(
        '-c',
        '--compile',
        choices=ALL_ADDONS,
        dest='compilation',
        default=False,
        help='compile translation files for generating package',
        )
    building.add_argument(
        '-b',
        '--build',
        choices=ALL_ADDONS,
        dest='build',
        default=False,
        help='build package',
        )
    building.add_argument(
        '-l',
        '--listing',
        choices=ALL_LINGUAS,
        dest='listing',
        default=False,
        help='list packages',
        )
    building.add_argument(
        '-r',
        '--clean',
        choices=ALL_ADDONS,
        dest='clean',
        default=False,
        help='remove files generated by building process',
        )

    if len(sys.argv) == 2:
        m = "Run 'setup.py --help en' or 'setup.py -h en'\n"
        parser.exit(message = m)

    if not 2 < len(sys.argv) < 5:
        m1 = 'Wrong number of arguments: %s \n' % len(sys.argv)
        parser.exit(message = m1)
    else:
        try:
            args = parser.parse_args()
        except AssertionError:
            m = 'Wrong argument: %s \n' % sys.argv
            l = '  lang available: %s \n' % str(ALL_LINGUAS)
            a = '  addon available: %s \n' % ALL_ADDONS
            parser.exit(message = m + l + a)

    # if args.test:
        # tests()

    if args.init:
        print(parser.parse_args())
        if args.init not in ADDONS:
            m1 = 'Wrong argument: %s \nTry "setup.py -i {addon_name} {lang}"!\n' % sys.argv
            parser.exit(message = m1)
        else:
            if args.lang == 'en':
                pass
            else:
                init(args.init, args.lang)

    if args.update:
        print(parser.parse_args())
        if args.update not in ADDONS:
            m1 = 'Wrong argument: %s \nTry "setup.py -u {addon_name} {lang}"!\n' % sys.argv
            parser.exit(message = m1)
        else:
            update(args.update, args.lang)

    if args.compilation:
        print(parser.parse_args())
        if args.compilation == "ALL":
            compilation_all(args.compilation)
        elif args.compilation == "all":
            m1 = 'Wrong argument: %s \nTry "setup.py -c ALL"!\n' % sys.argv
            parser.exit(message = m1)
        else:
            compilation(args.compilation)

    if args.build:
        print(parser.parse_args())
        if args.build == "ALL":
            build_all(args.build)
        elif args.build == "all":
            m1 = 'Wrong argument: %s \nTry "setup.py -b ALL"!\n' % sys.argv
            parser.exit(message = m1)
        else:
            build(args.build)

    if args.listing:
        print(parser.parse_args())
        if args.listing != False:
            if args.listing == "all":
                listing_all(args.lang)
            elif args.listing == "ALL":
                m1 = 'Wrong argument: %s \nTry "setup.py -l all"!\n' % sys.argv
                parser.exit(message = m1)
            else:
                sys.path.insert(3, args.listing)
                is_listing(sys.argv[2])
        else:
            m2 = 'Wrong argument: %s \n' % sys.argv
            parser.exit(message = m2)

    if args.clean:
        print(parser.parse_args())
        if args.clean == "ALL":
            clean_all(args.clean)
        elif args.clean == "all":
            m1 = 'Wrong argument: %s \nTry "setup.py -r ALL"!\n' % sys.argv
            parser.exit(message = m1)
        else:
            clean(args.clean)


def versioning(addon):
    """
    Update gpr.py version
    """

    gprs = glob.glob('''%(addon)s/*gpr.py''' % {'addon': addon})
    if len(gprs) > 0:
        for gpr in gprs:
            f = open(gpr, 'r')
            lines = [file.strip() for file in f]
            f.close()
            upf = open(gpr, 'w')

            for line in lines:
                if line.lstrip().startswith('version') and '=' in line:
                    print('orig %s' % line.rstrip())

                    (line, stuff) = line.rsplit(',', 1)
                    line = line.rstrip()
                    pos = line.index('version')

                    indent = line[0:pos]
                    (var, gtv) = line[pos:].split('=', 1)
                    lyst = version(gtv.strip()[1:-1])
                    lyst[2] += 1

                    newv = '.'.join(map(str, lyst))
                    newline = "%sversion = '%s'," % (indent, newv)
                    print('new %s' % newline.rstrip())
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

    return [myint(x or '0') for x in (sversion + '..').split('.')][0:3]


def init(ADDON, LANG):
    """
    Creates the initial empty po/x-local.po file and generates the 
    template.pot for the addon.
    """

    template(ADDON)

    os.system('%(mkdir)s -pv "%(addon)s/po"' % {'mkdir': mkdirCmd,
              'addon': ADDON})

    if os.path.isfile('%(addon)s/po/%(lang)s-local.po'
                      % {'addon': ADDON, 'lang': LANG}):
        print('"%(addon)s/po/%(lang)s-local.po" already exists!'
              % {'addon': ADDON, 'lang': LANG})
    else:
        os.system('%(msginit)s --locale=%(lang)s --input="%(addon)s/po/template.pot" --output="%(addon)s/po/%(lang)s-local.po"'
                   % {'msginit': msginitCmd, 'addon': ADDON,
                  'lang': LANG})
        print('You can now edit "%(addon)s/po/%(lang)s-local.po"!'
              % {'addon': ADDON, 'lang': LANG})


def template(ADDON):
    """
    Generates the template.pot for the addon.
    """

    os.system('%(xgettext)s --language=Python --keyword=_ --keyword=N_ --from-code=UTF-8 -o "%(addon)s/po/template.pot" %(addon)s/*.py'
               % {'xgettext': xgettextCmd, 'addon': ADDON})

    if os.path.isfile('%(addon)s/placecompletion.glade'
                      % {'addon': ADDON}):
        os.system('%(xgettext)s --add-comments -j -L Glade --from-code=UTF-8 -o "%(addon)s/po/template.pot" %(addon)s/*.glade'
                   % {'xgettext': xgettextCmd, 'addon': ADDON})

    if os.path.isfile('%s/census.xml' % ADDON):
        xml(ADDON)
        os.system('%(xgettext)s --keyword=N_ --add-comments -j --from-code=UTF-8 -o "%(addon)s/po/template.pot" %(addon)s/*.xml.h'
                   % {'xgettext': xgettextCmd, 'addon': ADDON})

    os.system('%(sed)s -i "s/charset=CHARSET/charset=UTF-8/" "%(addon)s/po/template.pot"'
               % {'sed': sedCmd, 'addon': ADDON})


def xml(ADDON):
    """
    Experimental alternative to 'intltool-extract' for 'census.xml'.
    """

    from xml.etree import ElementTree

    tree = ElementTree.parse('%s/census.xml' % ADDON)
    root = tree.getroot()

    catalog = open('%(addon)s/%(addon)s.xml.h' % {'addon': ADDON}, 'w')

    for key in root.iter('_attribute'):
        catalog.write('char *s = N_("%s");\n' % key.text)

    catalog.close()

    root.clear()


def update(ADDON, LANG):
    """
    Updates po/x-local.po with the latest translations.
    """

    template(ADDON)

    os.system('%(mkdir)s -pv "%(addon)s/po"' % {'mkdir': mkdirCmd,
              'addon': ADDON})

    # create a temp header file (time log)

    temp(ADDON, LANG)

    # create the locale-local.po file

    init(ADDON, LANG)

    # create a temp header file (time log)

    temp(ADDON, LANG)

    # merge data from previous translation to the temp one

    print('Merge "%(addon)s/po/%(lang)s.po" with "%(addon)s/po/%(lang)s-local.po":'
           % {'addon': ADDON, 'lang': LANG})

    os.system('%(msgmerge)s %(addon)s/po/%(lang)s-local.po %(addon)s/po/%(lang)s.po -o %(addon)s/po/%(lang)s.po --no-location -v'
               % {'msgmerge': msgmergeCmd, 'addon': ADDON,
              'lang': LANG})

    memory(ADDON, LANG)

    # like template (msgid) with last message strings (msgstr)

    print('Merge "%(addon)s/po/%(lang)s.po" with "po/template.pot":'
          % {'addon': ADDON, 'lang': LANG})

    os.system('%(msgmerge)s -U %(addon)s/po/%(lang)s.po %(addon)s/po/template.pot -v'
               % {'msgmerge': msgmergeCmd, 'addon': ADDON,
              'lang': LANG})

    # only used messages (need) and merge back

    print('Move content to "po/%s-local.po".' % LANG)

    os.system('%(msgattrib)s --no-obsolete %(addon)s/po/%(lang)s.po -o %(addon)s/po/%(lang)s-local.po'
               % {'msgattrib': msgattribCmd, 'addon': ADDON,
              'lang': LANG})

    # remove temp locale.po file

    os.system('%(rm)s -rf -v %(addon)s/po/%(lang)s.po' % {'rm': rmCmd,
              'addon': ADDON, 'lang': LANG})

    print('You can now edit "%(addon)s/po/%(lang)s-local.po"!'
          % {'addon': ADDON, 'lang': LANG})


def temp(addon, lang):
    """
    Generate a temp file for header (time log) and Translation Memory
    """

    os.system('%(msginit)s --locale=%(lang)s --input="%(addon)s/po/template.pot" --output="%(addon)s/po/%(lang)s.po" --no-translator'
               % {'msginit': msginitCmd, 'addon': addon, 'lang': lang})


def memory(addon, lang):
    """
    Translation memory for Gramps (own dictionary: msgid/msgstr)
    """

    if 'GRAMPSPATH' in os.environ:
        GRAMPSPATH = os.environ['GRAMPSPATH']
    else:
        GRAMPSPATH = '../../../..'

    if not os.path.isdir(GRAMPSPATH + '/po'):
        raise ValueError("Where is GRAMPSPATH/po: '%s/po'? Use 'GRAMPSPATH=path python setup.py ...'"
                          % GRAMPSPATH)

    # Get all of the addon strings out of the catalog

    os.system('%(msggrep)s --location=*/* %(addon)s/po/template.pot --output-file=%(addon)s/po/%(lang)s-temp.po'
               % {'msggrep': msggrepCmd, 'addon': addon, 'lang': lang})

    # start with Gramps main PO file

    locale_po_files = '%(GRAMPSPATH)s/po/%(lang)s.po' \
        % {'GRAMPSPATH': GRAMPSPATH, 'addon': addon, 'lang': lang}

    # concat global dict as temp file

    if os.path.isfile(locale_po_files):
        print('Concat temp data: "%(addon)s/po/%(lang)s.po" with "%(global)s".'
               % {'global': locale_po_files, 'addon': addon,
              'lang': lang})

        os.system('%(msgcat)s --use-first %(addon)s/po/%(lang)s.po %(global)s -o %(addon)s/po/%(lang)s.po --no-location'
                   % {
            'msgcat': msgcatCmd,
            'global': locale_po_files,
            'addon': addon,
            'lang': lang,
            })
        os.system('%(msgcmp)s -m --use-fuzzy --use-untranslated %(addon)s/po/%(lang)s.po %(global)s'
                   % {
            'msgcmp': msgcmpCmd,
            'global': locale_po_files,
            'addon': addon,
            'lang': lang,
            })

    if os.path.isfile('%(addon)s/po/%(lang)s-temp.po'
                      % {'addon': addon, 'lang': lang}):
        print('Concat temp data: "%(addon)s/po/%(lang)s.po" with "%(addon)s/po/%(lang)s-temp.po".'
               % {'addon': addon, 'lang': lang})

        os.system('%(msgcat)s --use-first %(addon)s/po/%(lang)s.po %(addon)s/po/%(lang)s-temp.po -o %(addon)s/po/%(lang)s.po --no-location'
                   % {'msgcat': msgcatCmd, 'addon': addon,
                  'lang': lang})

        print('Remove temp "%(addon)s/po/%(lang)s-temp.po".'
              % {'addon': addon, 'lang': lang})

        os.system('%(rm)s -rf -v %(addon)s/po/%(lang)s-temp.po'
                  % {'rm': rmCmd, 'addon': addon, 'lang': lang})


def compilation(addon):
    """
    Compile translations
    """

    non_empty = glob.glob(os.path.join(addon, 'po', '*-local.po'))

    if len(non_empty) > 0:
        os.system('%(mkdir)s -pv "%(addon)s/locale"' % {'mkdir': mkdirCmd,
                  'addon': addon})

        for po in non_empty:
            f = os.path.basename(po[:-3])
            mo = os.path.join(addon, 'locale', f[:-6], 'LC_MESSAGES',
                              'addon.mo')
            directory = os.path.dirname(mo)
            if not os.path.exists(directory):
                os.makedirs(directory)
            os.system('%(msgfmtCmd)s %(addon)s/po/%(lang)s.po -o %(build)s'
                      % {
                'msgfmtCmd': msgfmtCmd,
                'addon': addon,
                'lang': f,
                'build': mo,
                })


def compilation_all(ADDON):
    """
    Compile all translations
    """
    
    for addon in ADDONS:
        if addon == 'ALL':
            continue
        compilation(addon)


def build(addon):
    """
    Build ../download/{ADDON}.addon.tgz
    """
    
    compilation(addon)
    versioning(addon)
    files = []
    files += glob.glob('''%s/*.py''' % addon)
    files += glob.glob('''%s/locale/*/LC_MESSAGES/*.mo''' % addon)
    files += glob.glob('''%s/*.glade''' % addon)
    files += glob.glob('''%s/*.xml''' % addon)
    files_str = ' '.join(files)
    os.system('%(mkdir)s -pv ../download/%(addon)s '
                % {'mkdir': mkdirCmd, 'addon': addon})
    os.system('%(tar)s cfzv "../download/%(addon)s.addon.tgz" %(files_list)s'
                % {'tar': tarCmd, 'files_list': files_str,
                'addon': addon})
    os.system('rmdir ../download/%(addon)s '
                % {'addon': addon})


def build_all(ADDON):
    """
    Build all ../download/*.addon.tgz
    """
    
    for addon in ADDONS:
        if addon == 'ALL':
            continue
        build(addon)
        

def is_listing(LANG):
    """
    Listing files ../listing/{lang}.fr
    """

    if 'GRAMPSPATH' in os.environ:
        GRAMPSPATH = os.environ['GRAMPSPATH']
    else:
        GRAMPSPATH = '../../../..'

    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ['GRAMPS_RESOURCES'] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment, PTYPE_STR
    except ImportError:
        raise ValueError("Where is 'GRAMPSPATH' or 'GRAMPS_RESOURCES'?")

    def register(ptype, **kwargs):
        global plugins
        kwargs['ptype'] = PTYPE_STR[ptype] # related to gramps translations
        plugins.append(kwargs)

    cmd_arg = LANG

    # Make the locale for for any local languages for Addon:

    for addon in ADDONS:
        for po in glob.glob('%(addon)s/po/*-local.po' % {'addon': addon}):

            # Compile

            locale = os.path.basename(po[:-9])
            os.system('mkdir -p "%(addon)s/locale/%(locale)s/LC_MESSAGES/"' 
                          % {'addon': addon, 'locale': locale})
            os.system('msgfmt %(po)s -o "%(addon)s/locale/%(locale)s/LC_MESSAGES/addon.mo"' 
                          % {'po': po, 'addon': addon, 'locale': locale})

    # Get all languages from all addons:

    languages = set(['en'])
    for addon in [file for file in glob.glob('*')
                  if os.path.isdir(file)]:
        for po in glob.glob('%(addon)s/po/*-local.po' % {'addon': addon}):
            length = len(po)
            locale = po[length - 11:length - 9]
            (locale_path, locale) = po.rsplit('/', 1)
            languages.add(locale[:-9])

    # next, create/edit a file for all languages listing plugins

    for lang in languages:
        print("----Building listing for '%s'..." % lang)
        listings = []
        for addon in ADDONS:
            for gpr in glob.glob('%(addon)s/*.gpr.py' % {'addon': addon}):

                print(gpr)

                # Make fallback language English (rather than current LANG)

                local_gettext = glocale.get_addon_translator(gpr,
                        languages=[lang, 'en.UTF-8']).gettext
                plugins = []
                with open(gpr.encode('utf-8', errors='backslashreplace'
                          )) as f:
                    code = compile(f.read(), gpr.encode('utf-8',
                                   errors='backslashreplace'), 'exec')

                    #exec(code, make_environment(_=local_gettext),
                         #{"register": register})

                for p in plugins:
                    tgz_file = '%s.addon.tgz' % gpr.split('/', 1)[0]
                    tgz_exists = os.path.isfile('../download/'
                            + tgz_file)
                    if p.get('include_in_listing', True) and tgz_exists:
                        plugin = {
                            'n': repr(p['name']),
                            'i': repr(p['id']),
                            't': repr(p['ptype']),
                            'd': repr(p['description']),
                            'v': repr(p['version']),
                            'g': repr(p['gramps_target_version']),
                            'z': repr(tgz_file),
                            }
                        listings.append(plugin)
                    else:
                        print("   ignoring '%s'" % p['name'])

def listing(LANG):
    """
    Listing files ../listing/{lang}.fr
    """

    if 'GRAMPSPATH' in os.environ:
        GRAMPSPATH = os.environ['GRAMPSPATH']
    else:
        GRAMPSPATH = '../../../..'

    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ['GRAMPS_RESOURCES'] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment, PTYPE_STR
    except ImportError:
        raise ValueError("Where is 'GRAMPSPATH' or 'GRAMPS_RESOURCES'?")

    LOCALE = glocale.get_language_list()

    compilation_all('ALL')

    listings = []
    need = False

    # change the method

    fp = open('../listings/addons-%s.txt' % LANG, 'w')

    for addon in sorted(ADDONS):

        tgz_file = '%s.addon.tgz' % addon
        tgz_exists = os.path.isfile('../download/' + tgz_file)
        gprs = glob.glob('%(addon)s/*gpr.py' % {'addon': addon})
        for gpr in gprs:
            gpr_file = gpr
            print(gpr_file, gprs)
            gpr_exists = os.path.isfile(gpr_file)

        mo_file = "%s/locale/%s/LC_MESSAGES/addon.mo" % (addon, LANG)
        mo_exists = os.path.isfile(mo_file)

        if tgz_exists and gpr_exists:
            gpr = open(gpr_file.encode('utf-8',
                       errors='backslashreplace'))

            plug = dict([file.strip(), None] for file in gpr
                        if file.strip())

            name = ident = ptype = description = version = target = ''

            if mo_exists:
                LANGUAGE = LANG +".UTF-8"
            else:
                LANGUAGE = os.environ['LANGUAGE']

            # print(plug)

            for p in plug:

                # print(repr(p))

                if repr(p).startswith("'register("):
                    ptype = p.replace("register(", "")
                    ptype = ptype.replace(",", "")

                    # incomplete dirty hack!

                    print(glocale._get_translation(), LANG+".UTF-8")

                    if LANG != LOCALE[0]:
                        # mixup between LOCALE[0] and 'en' (avoid corruption)
                        # need 'en.UTF-8' !
                        local_gettext = glocale.get_addon_translator(gpr_file, languages=[LANGUAGE]).ugettext
                        #return
                    else:
                        local_gettext = glocale.get_addon_translator(gpr_file, languages=[LANG, "en"]).ugettext
                        ptype = make_environment(_ = local_gettext)[ptype]

                    # need to match translations build by Gramps program

                    try:
                        ptype = PTYPE_STR[ptype]
                    except:
                        # fallback and corruption with LOCALE[0]
                        print(' wrong PTYPE: %s' % ptype)
                        print(local_gettext('Tool')) # always corrupted by the locale
                        print("LANGUAGE='%(language)s', LANG='%(lang)s'" % {'language': os.environ['LANGUAGE'], 'lang': os.environ['LANG']})
                        return

                if not (repr(p).startswith("'include_in_listing = False,"
                        ) or repr(p).startswith("'status = UNSTABLE,")):
                    need = True
                else:
                    print("Ignoring: '%s'" % addon)

                if repr(p).startswith("'id") or repr(p).startswith('"id'
                        ):
                    ident = p.replace('id', '')
                    ident = ident.replace('=', '')
                    ident = ident.replace(',', '')
                    ident = ident.strip()
                    #ident = repr(ident)

                if repr(p).startswith("'name") \
                    or repr(p).startswith('"name'):
                    name = p.replace('name', '')
                    name = name.replace('=', '')
                    name = name.replace(',', '')
                    name = name.strip()
                    name = name.replace('_(', '')
                    name = name.replace(')', '')
                    name = name.replace('"', '')
                    name = glocale._get_translation().ugettext(name)
                    try:
                        if name == local_gettext(name):
                            print(addon, name, local_gettext(name))
                        name = repr(local_gettext(name))
                    except:
                        print('Cannot use local_gettext on', repr(p))
                    # ugly workaround for name_accell (Export GEDCOM Extensions)
                    name = name.replace('_accell   ', '')
                    name = name.replace('(GED2', '(GED2)')

                if repr(p).startswith("'description"):
                    description = p.replace('description', '')
                    description = description.replace('=', '')
                    description = description.replace(',', '')
                    description = description.strip()
                    description = description.replace('_(', '')
                    description = description.replace(')', '')
                    description = description.replace('"', '')
                    description = glocale._get_translation().ugettext(description)
                    try:
                        if description == local_gettext(description):
                            print(addon, description, local_gettext(description))
                        description = repr(local_gettext(description))
                    except:
                        print('Cannot use local_gettext on', repr(p))

                if repr(p).startswith('"version'):
                    version = p.replace('version', '')
                    version = version.replace('=', '')
                    version = version.replace(',', '')
                    version = version.replace("'", "")
                    version = version.replace('"', '')
                    version = version.strip()
                    version = repr(version)

            # workaround #7395~c38994
            if description == '':
                description = "''"
                print(description, addon)

            if need:
                plugin = {
                    'n': name,
                    'i': ident,
                    't': repr(ptype),
                    'd': description,
                    'v': version,
                    'g': "'4.2'",
                    'z': repr(tgz_file),
                    }

                #if name or ident or version or target == "":
                    #print(plugin)

                fp.write('{"t":%(t)s,"i":%(i)s,"n":%(n)s,"v":%(v)s,"g":%(g)s,"d":%(d)s,"z":%(z)s}\n'
                          % plugin)

                # print(plugin)

                listings.append(plugin)

        # for plugin in sorted(listings, key=lambda p: p["z"]):
            # fp.write('{"t":%(t)s,"i":%(i)s,"n":%(n)s,"v":%(v)s,"g":%(g)s,"d":%(d)s,"z":%(z)s}\n' % plugin)

    fp.close()

    #clean_all('ALL')


def listing_all(LANG):
    """
    Remove created files for all addons
    """
    
    for lang in LINGUAS:
        if lang == 'all':
            continue
        else:
            if lang in os.environ['LANGUAGE']:
                is_listing(lang)
            else:
                print(lang, os.environ['LANGUAGE'])


def clean(addon):
    """
    Remove created files
    """

    os.system('%(rm)s -rfv %(addon)s/*~ %(addon)s/po/*~ %(addon)s/po/template.pot %(addon)s/locale %(addon)s/*.pyc %(addon)s/*.pyo %(addon)s/xml.h '
               % {'rm': rmCmd, 'addon': addon})


def clean_all(ADDON):
    """
    Remove created files for all addons
    """
    
    for addon in ADDONS:
        if addon == 'ALL':
            continue
        clean(addon)


if __name__ == '__main__':
    main()
