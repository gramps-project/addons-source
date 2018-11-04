#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make.py for Gramps addons.

Examples:
   python make.py gramps42 init AddonDirectory

      Creates the initial directories for the addon.

   python make.py gramps42 init AddonDirectory fr

      Creates the initial empty AddonDirectory/po/fr-local.po file
      for the addon.

   python make.py gramps42 update AddonDirectory fr

      Updates AddonDirectory/po/fr-local.po with the latest
      translations.

   python make.py gramps42 build AddonDirectory

      Build ../download/AddonDirectory.addon.tgz

   python make.py gramps42 build all

      Build ../download/*.addon.tgz

   python make.py gramps42 compile AddonDirectory
   python make.py gramps42 compile all

      Compiles AddonDirectory/po/*-local.po and puts the resulting
      .mo file in AddonDirectory/locale/*/LC_MESSAGES/addon.mo

   python make.py gramps42 listing AddonDirectory
   python make.py gramps42 listing all

   python make.py gramps42 dist-clean
   python make.py gramps42 dist-clean AddonDirectory
   python make.py gramps42 clean
   python make.py gramps42 clean AddonDirectory
"""
import shutil
import glob
import sys
import os
import tarfile

if "GRAMPSPATH" in os.environ:
    GRAMPSPATH = os.environ["GRAMPSPATH"]
else:
    GRAMPSPATH = "../../.."

if (("LANGUAGE" not in os.environ) or
    (not os.environ["LANGUAGE"].startswith("en"))):
    raise ValueError("LANGUAGE should explicitly be english; Use 'LANGUAGE=en_US.UTF-8 python make.py...' or similar")
else:
    print("make.py: LANGUAGE is %s... good!" % os.environ["LANGUAGE"])

gramps_version = sys.argv[1]

command = sys.argv[2]
if len(sys.argv) >= 4:
    addon = sys.argv[3]

def system(scmd, **kwargs):
    """
    Replace and call system with scmd.
    """
    cmd = r(scmd, **kwargs)
    #print(cmd)
    os.system(cmd)

def echo(scmd, **kwargs):
    """
    Replace and echo.
    """
    cmd = r(scmd, **kwargs)
    print(cmd)

def r(scmd, **kwargs):
    """
    Replace scmd with variables from kwargs, or globals.
    """
    keywords = globals()
    keywords.update(kwargs)
    cmd = scmd % keywords
    return cmd

def mkdir(dirname):
    """
    Create a directory, if doesn't already exists.
    Note: os.system("mkdir ...") cannot be used on Windows (mkdir mismatches with integrated cmd.exe command)
    """
    dirname = r(dirname)
    if (os.path.isdir(dirname)): return
    os.makedirs(dirname)

def increment_target(filenames):
    for filename in filenames:
        fp = open(filename, "r", encoding="utf-8")
        newfp = open("%s.new" % filename, "w", encoding="utf-8", newline='')
        for line in fp:
            if ((line.lstrip().startswith("version")) and
                ("=" in line)):
                #print("orig = %s" % line.rstrip())
                line, stuff = line.rsplit(",", 1)
                line = line.rstrip()
                pos = line.index("version")
                indent = line[0:pos]
                var, gtv = line[pos:].split('=', 1)
                lyst = version(gtv.strip()[1:-1])
                lyst[2] += 1
                newv = ".".join(map(str, lyst))
                newline = "%sversion = '%s',\n" % (indent, newv)
                newfp.write(newline)
            else:
                newfp.write(line)
        fp.close()
        newfp.close()
        os.remove(filename)
        os.rename("%s.new" % filename, filename)


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


def cleanup(addon_dir):
    """
    An OS agnostic cleanup routine
    """
    patterns = ['%s/*~' % addon_dir,
                '%s/po/*~' % addon_dir,
                '%s/po/template.pot' % addon_dir,
                '%s/po/*-global.po' % addon_dir,
                '%s/po/*-temp.po' % addon_dir,
                '%s/*.pyc' % addon_dir,
                '%s/*.pyo' % addon_dir]
    for pat in patterns:
        for file_ in glob.glob(pat):
            os.remove(file_)
    shutil.rmtree('%s/locale' % addon_dir, ignore_errors=True)


def do_tar(inc_files):
    """
    An OS agnostic tar creation that uses only Python libs
    inc_files is a list of filenames
    """
    if not inc_files:
        print("***Nothing to build! %s" % addon)
        exit()

    def tar_filt(tinfo):
        tinfo.uname = tinfo.gname = 'gramps'
        return tinfo
    mkdir(r("../addons/%(gramps_version)s/download"))
    increment_target(glob.glob(r('''%(addon)s/*gpr.py''')))
    tar = tarfile.open(r("../addons/%(gramps_version)s/download/"
                         "%(addon)s.addon.tgz"), mode='w:gz',
                       encoding='utf-8')
    for inc_fil in inc_files:
        inc_fil = inc_fil.replace("\\", "/")
        tar.add(inc_fil, filter=tar_filt)
    tar.close()


if command == "clean":
    if len(sys.argv) == 3:
        for addon in [name for name in os.listdir(".")
                      if os.path.isdir(name) and not name.startswith(".")]:
            cleanup(addon)
    else:
        cleanup(addon)
elif command == "init":
    # # Get all of the strings from the addon and create template.po:
    # #intltool-extract --type=gettext/glade *.glade
    if len(sys.argv) == 4:
        mkdir(r("%(addon)s/po"))
        mkdir("%(addon)s/locale")
        system('''intltool-extract --type=gettext/glade "%(addon)s"/*.glade''')
        if sys.argv[3] == "Form":
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_be.xml"''')
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_ca.xml"''')
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_dk.xml"''')
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_fr.xml"''')
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_gb.xml"''')
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_pl.xml"''')
            system('''intltool-extract --type=gettext/xml "%(addon)s/form_us.xml"''')
        else:
            system('''intltool-extract --type=gettext/xml "%(addon)s"/*.xml''')
        system('''xgettext --language=Python --keyword=_ --keyword=N_'''
               ''' -o "%(addon)s/po/template.pot" "%(addon)s"/*.py ''')
        system('''xgettext -j --keyword=_ --keyword=N_'''
               ''' -o "%(addon)s/po/template.pot" '''
               '''"%(addon)s"/*.glade.h''')
        system('''xgettext -j --keyword=_ --keyword=N_'''
               ''' --from-code=UTF-8 -o "%(addon)s/po/template.pot" '''
               '''"%(addon)s"/*.xml.h''')
        system('''sed -i 's/charset=CHARSET/charset=UTF-8/' '''
               '''"%(addon)s/po/template.pot"''')
    elif len(sys.argv) > 4:
        locale = sys.argv[4]
        # make a copy for locale
        if os.path.isfile(r('''%(addon)s/po/%(locale)s-local.po''')):
            raise ValueError(r('''%(addon)s/po/%(locale)s-local.po''') +
                             " already exists!")
        system('''msginit --locale=%(locale)s '''
               '''--input="%(addon)s/po/template.pot" '''
               '''--output="%(addon)s/po/%(locale)s-local.po"''')
        echo('''You can now edit "%(addon)s/po/%(locale)s-local.po"''')
    else:
        raise AttributeError("init what?")
elif command == "update":
    locale = sys.argv[4]
    # Update the template file:
    if not os.path.isfile(r('''%(addon)s/po/template.pot''')):
        raise ValueError(r('''%(addon)s/po/template.pot'''
                           ''' is missing!\n  run '''
                           '''./make.py %(gramps_version)s init %(addon)s'''))
    # Check existing translation
    if not os.path.isfile(r('''%(addon)s/po/%(locale)s-local.po''')):
        raise ValueError(r('''%(addon)s/po/%(locale)s-local.po'''
                           ''' is missing!\n run '''
                           '''./make.py %(gramps_version)s init %(addon)s %(locale)s'''))
    # Retrieve updated data for locale:
    system('''msginit --locale=%(locale)s '''
               '''--input="%(addon)s/po/template.pot" '''
               '''--output="%(addon)s/po/%(locale)s.po"''')
    # Merge existing local translation with last data:
    system('''msgmerge --no-fuzzy-matching %(addon)s/po/%(locale)s-local.po '''
           '''%(addon)s/po/%(locale)s.po'''
           ''' -o %(addon)s/po/%(locale)s-local.po''')
    # Start with Gramps main PO file:
    if not os.path.isdir(GRAMPSPATH + "/po"):
        raise ValueError("Where is GRAMPSPATH/po: '%s/po'? Use 'GRAMPSPATH=path python make.py gramps50 update'" % GRAMPSPATH)
    locale_po_files = [r("%(GRAMPSPATH)s/po/%(locale)s.po")]
    # Next, get all of the translations from other addons:
    for module in [name for name in os.listdir(".") if os.path.isdir(name)]:
        # skip the addon we are updating:
        if module == addon:
            continue
        po_file = r("%(module)s/po/%(locale)s-local.po", module=module)
        if os.path.isfile(po_file):
            locale_po_files.append(po_file)
    # Concat those together:
    system('''msgcat --use-first %(list)s '''
           '''-o "%(addon)s/po/%(locale)s-global.po"''',
           list=" ".join(['''"%s"''' % name for name in locale_po_files]))
    # Merge the local and global:
    #locale_local = r("%(module)s/po/%(locale)s-local.po", module=module)
    #if os.path.isfile(locale_local):
    system('''msgmerge --no-fuzzy-matching -U "%(addon)s/po/%(locale)s-global.po" '''
           '''"%(addon)s/po/%(locale)s-local.po" ''')
    # Get all of the addon strings out of the catalog:
    system('''msggrep --location=%(addon)s/* '''
           '''"%(addon)s/po/%(locale)s-global.po" '''
           '''--output-file="%(addon)s/po/%(locale)s-temp.po"''')
    # Finally, add back any updates to the local version:
    system('''msgcat --use-first '''
           '''"%(addon)s/po/%(locale)s-temp.po" '''
           '''"%(addon)s/po/%(locale)s-local.po" '''
           '''-o "%(addon)s/po/%(locale)s-local.po.2" ''')
    system('''cp "%(addon)s/po/%(locale)s-local.po" '''
           '''"%(addon)s/po/%(locale)s-local.po.1" ''')
    system('''cp "%(addon)s/po/%(locale)s-local.po.2" '''
           '''"%(addon)s/po/%(locale)s-local.po" ''')
    system('''rm -v "%(addon)s/po/%(locale)s-local.po.1" '''
           '''"%(addon)s/po/%(locale)s-local.po.2" ''')
    # # Done!
    echo('''\nYou can edit "%(addon)s/po/%(locale)s-local.po"''')
elif command in ["compile"]:
    if addon == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
        for addon in dirs:
            for po in glob.glob(r('''%(addon)s/po/*.po''')):
                locale = os.path.basename(po[:-9])
                mkdir("%(addon)s/locale/%(locale)s/LC_MESSAGES/")
                system('''msgfmt %(po)s '''
                       '''-o "%(addon)s/locale/%(locale)s/LC_MESSAGES/addon.mo"''')
    else:
        for po in glob.glob(r('''%(addon)s/po/*.po''')):
            locale = os.path.basename(po[:-9])
            mkdir("%(addon)s/locale/%(locale)s/LC_MESSAGES/")
            system('''msgfmt %(po)s '''
                   '''-o "%(addon)s/locale/%(locale)s/LC_MESSAGES/addon.mo"''')
elif command == "build":
    if addon == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
        # Compile all:
        for addon in dirs:
            for po in glob.glob(r('''%(addon)s/po/*.po''')):
                locale = os.path.basename(po[:-9])
                mkdir("%(addon)s/locale/%(locale)s/LC_MESSAGES/")
                system('''msgfmt %(po)s '''
                       '''-o "%(addon)s/locale/%(locale)s/LC_MESSAGES/addon.mo"''')
        # Build all:
        for addon in dirs:
            if os.path.isfile(r('''%(addon)s/setup.py''')):
                system('''cd %s; python setup.py --build''' % r('''%(addon)s'''))
                continue
            patts = [r('''%(addon)s/*.py'''), r('''%(addon)s/*.glade'''),
                     r('''%(addon)s/*.xml'''), r('''%(addon)s/*.txt'''),
                     r('''%(addon)s/locale/*/LC_MESSAGES/*.mo''')]
            if os.path.isfile(r('''%(addon)s/MANIFEST''')):
                patts.extend(open(r('''%(addon)s/MANIFEST'''),
                                  "r").read().split())
            files = []
            for patt in patts:
                files.extend(glob.glob(patt))
            if not files:
                # git doesn't remove empty folders when switching branchs
                continue
            do_tar(files)
    else:
        for po in glob.glob(r('''%(addon)s/po/*.po''')):
                locale = os.path.basename(po[:-9])
                mkdir("%(addon)s/locale/%(locale)s/LC_MESSAGES/")
                system('''msgfmt %(po)s '''
                       '''-o "%(addon)s/locale/%(locale)s/LC_MESSAGES/addon.mo"''')
        patts = [r('''%(addon)s/*.py'''), r('''%(addon)s/*.glade'''),
                 r('''%(addon)s/*.xml'''), r('''%(addon)s/*.txt'''),
                 r('''%(addon)s/locale/*/LC_MESSAGES/*.mo''')]
        if os.path.isfile(r('''%(addon)s/MANIFEST''')):
            patts.extend(open(r('''%(addon)s/MANIFEST'''),
                              "r").read().split())
        files = []
        for patt in patts:
            files.extend(glob.glob(patt))
        do_tar(files)
elif command == "manifest-check":
    import re
    for tgz in glob.glob(r("../addons/%(gramps_version)s/download/*.tgz")):
        files = tarfile.open(tgz).getnames()
        for file in files:
            if not any([
                    re.match(".*\.py$", file),
                    re.match(".*\.txt$", file),
                    re.match(".*\.glade$", file),
                    re.match(".*\.xml$", file),
                    re.match(".*locale/.*/LC_MESSAGES/.*.mo", file),
            ]
            ):
                print("Need to add", file, "in", tgz)
elif command == "unlist":
    # Get all languages from all addons:
    cmd_arg = addon
    languages = set(['en'])
    for addon in [file for file in glob.glob("*") if os.path.isdir(file)]:
        for po in glob.glob(r('''%(addon)s/po/*-local.po''')):
            length= len(po)
            locale = po[length-11:length-9]
            locale_path, locale = po.rsplit(os.sep, 1)
            languages.add(locale[:-9])
    for lang in languages:
        lines = []
        fp = open(r("../addons/%(gramps_version)s/listings/") + ("addons-%s.txt" % lang), "r", encoding="utf-8")
        for line in fp:
            if cmd_arg + ".addon.tgz" not in line:
                lines.append(line)
            else:
                print("unlisting", line)
        fp.close()
        fp = open(r("../addons/%(gramps_version)s/listings/") +
                  ("addons-%s.txt" % lang), "w", encoding="utf-8", newline='')
        for line in lines:
            fp.write(line)
        fp.close()
elif command == "fix":
    # Get all languages from all addons:
    languages = set(['en'])
    for addon in [file for file in glob.glob("*") if os.path.isdir(file)]:
        for po in glob.glob(r('''%(addon)s/po/*-local.po''')):
            length= len(po)
            locale = po[length-11:length-9]
            locale_path, locale = po.rsplit(os.sep, 1)
            languages.add(locale[:-9])
    for lang in languages:
        addons = {}
        fp = open(r("../addons/%(gramps_version)s/listings/") + ("addons-%s.txt" % lang), "r", encoding="utf-8")
        for line in fp:
            dictionary = eval(line)
            if dictionary["i"] in addons:
                print(lang, "Repeated addon ID:", dictionary["i"])
            else:
                addons[dictionary["i"]] = dictionary
        fp.close()
        fp = open(r("../addons/%(gramps_version)s/listings/") +
                  ("addons-%s.txt" % lang), "w", encoding="utf-8", newline='')
        for p in sorted(addons.values(), key=lambda p: (p["t"], p["i"])):
            plugin = {"n": p["n"].replace("'", "\\'"),
                      "i": p["i"].replace("'", "\\'"),
                      "t": p["t"].replace("'", "\\'"),
                      "d": p["d"].replace("'", "\\'"),
                      "v": p["v"].replace("'", "\\'"),
                      "g": p["g"].replace("'", "\\'"),
                      "z": p["z"].replace("'", "\\'"),
            }
            print("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin, file=fp)
        fp.close()
elif command == "check":
    from gramps.gen.plug import make_environment, PTYPE_STR
    from gramps.gen.const import GRAMPS_LOCALE as glocale
    def register(ptype, **kwargs):
        global plugins
        kwargs["ptype"] = PTYPE_STR[ptype] # need to take care of translated types
        plugins.append(kwargs)
    # get current build numbers from English listing
    fp_in = open(r("../addons/%(gramps_version)s/listings/addons-en.txt"), "r", encoding="utf-8")
    addons = {}
    for line in fp_in:
        dictionary = eval(line)
        if dictionary["i"] in addons:
            print("Repeated addon ID:", dictionary["i"])
        else:
            addons[dictionary["i"]] = dictionary
    # go through all gpr's, check their build versions
    for gpr in glob.glob(r('''*/*.gpr.py''')):
        local_gettext = glocale.get_addon_translator(
            gpr, languages=["en", "en.UTF-8"]).gettext
        plugins = []
        with open(gpr.encode("utf-8", errors="backslashreplace")) as f:
            code = compile(f.read(),
                           gpr.encode("utf-8", errors="backslashreplace"),
                           'exec')
            exec(code, make_environment(_=local_gettext),
                 {"register": register})
        for p in plugins:
            gpr_version = p.get("version", None)
            id = p.get("id", None)
            if id not in addons:
                print("Missing in listing:", id)
            else:
                add_version = addons[id]["v"]
                if gpr_version != add_version:
                    print("Different versions:", id, gpr_version, add_version)
                    # if number diff from gpr, report it
elif command == "listing":
    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ['GRAMPS_RESOURCES'] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment, PTYPE_STR
    except ImportError:
        raise ValueError("Where is GRAMPSPATH: '%s'? Use 'GRAMPSPATH=path python make.py gramps50 listing'" % GRAMPSPATH)
    def register(ptype, **kwargs):
        global plugins
        kwargs["ptype"] = PTYPE_STR[ptype] # need to take care of translated types
        plugins.append(kwargs)
    cmd_arg = addon
    # first, get a list of all of the possible languages
    if cmd_arg == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
    else:
        dirs = [addon]
    # Make the locale for for any local languages for Addon:
    for addon in dirs:
        for po in glob.glob(r('''%(addon)s/po/*-local.po''')):
            # Compile
            locale = os.path.basename(po[:-9])
            mkdir("%(addon)s/locale/%(locale)s/LC_MESSAGES/")
            system('''msgfmt %(po)s '''
                   '''-o "%(addon)s/locale/%(locale)s/LC_MESSAGES/addon.mo"''')
    # Get all languages from all addons:
    languages = set(['en'])
    for addon in [file for file in glob.glob("*") if os.path.isdir(file)]:
        for po in glob.glob(r('''%(addon)s/po/*-local.po''')):
            length= len(po)
            locale = po[length-11:length-9]
            locale_path, locale = po.rsplit(os.sep, 1)
            languages.add(locale[:-9])
    # next, create/edit a file for all languages listing plugins
    for lang in languages:
        print("Building listing for '%s'..." % lang)
        listings = []
        for addon in dirs:
            for gpr in glob.glob(r('''%(addon)s/*.gpr.py''')):
                # Make fallback language English (rather than current LANG)
                local_gettext = glocale.get_addon_translator(
                    gpr, languages=[lang, "en.UTF-8"]).gettext
                plugins = []
                with open(gpr.encode("utf-8", errors="backslashreplace")) as f:
                    code = compile(f.read(),
                                   gpr.encode("utf-8", errors="backslashreplace"),
                                   'exec')
                    exec(code, make_environment(_=local_gettext),
                         {"register": register})
                for p in plugins:
                    tgz_file = "%s.addon.tgz" % gpr.split(os.sep, 1)[0]
                    tgz_exists = os.path.isfile(r("../addons/%(gramps_version)s/download/") + tgz_file)
                    if p.get("include_in_listing", True) and tgz_exists:
                        plugin = {"n": p["name"].replace("'", "\\'"),
                                  "i": p["id"].replace("'", "\\'"),
                                  "t": p["ptype"].replace("'", "\\'"),
                                  "d": p["description"].replace("'", "\\'"),
                                  "v": p["version"].replace("'", "\\'"),
                                  "g": p["gramps_target_version"].replace("'", "\\'"),
                                  "z": (tgz_file),
                                  }
                        listings.append(plugin)
                    else:
                        print("   ignoring '%s'" % (p["name"]))
        # Write out new listing:
        if cmd_arg == "all":
            # Replace it!
            fp = open(r("../addons/%(gramps_version)s/listings/") +
                      ("addons-%s.txt" % lang), "w", encoding="utf-8",
                      newline='')
            for plugin in sorted(listings, key=lambda p: (p["t"], p["i"])):
                print("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin, file=fp)
            fp.close()
        elif not os.path.isfile(r("../addons/%(gramps_version)s/listings/") + ("addons-%s.txt" % lang)):
            fp_out = open(r("../addons/%(gramps_version)s/listings/") +
                          ("addons-%s.txt" % lang), "w", encoding="utf-8",
                          newline='')
            for plugin in sorted(listings, key=lambda p: (p["t"], p["i"])):
                print("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin, file=fp_out)
            fp_out.close()
        else:
            # just update the lines from these addons:
            for plugin in sorted(listings, key=lambda p: (p["t"], p["i"])):
                already_added = []
                fp_in = open(r("../addons/%(gramps_version)s/listings/") + ("addons-%s.txt" % lang), "r", encoding="utf-8")
                fp_out = open(r("../addons/%(gramps_version)s/listings/") +
                              ("addons-%s.new" % lang), "w", encoding="utf-8",
                              newline='')
                added = False
                for line in fp_in:
                    dictionary = eval(line)
                    if ("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s'}""" % dictionary) in already_added:
                        continue
                    if cmd_arg + ".addon.tgz" in line and plugin["t"] == dictionary["t"] and not added:
                        #print("UPDATED")
                        print("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin, file=fp_out)
                        added = True
                        already_added.append("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s'}""" % plugin)
                    elif ((plugin["t"], plugin["i"]) < (dictionary["t"], dictionary["i"])) and not added:
                        #print("ADDED in middle")
                        print("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin, file=fp_out)
                        added = True
                        print(line, end="", file=fp_out)
                        already_added.append("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s'}""" % plugin)
                    else:
                        print(line, end="", file=fp_out)
                        already_added.append("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s'}""" % dictionary)
                if not added:
                    if ("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin) not in already_added:
                        #print("ADDED at end")
                        print("""{"t":'%(t)s',"i":'%(i)s',"n":'%(n)s',"v":'%(v)s',"g":'%(g)s',"d":'%(d)s',"z":'%(z)s'}""" % plugin, file=fp_out)
                fp_in.close()
                fp_out.close()
                shutil.move(r("../addons/%(gramps_version)s/listings/") + ("addons-%s.new" % lang), r("../addons/%(gramps_version)s/listings/") +("addons-%s.txt" % lang))

else:
    raise AttributeError("unknown command")
