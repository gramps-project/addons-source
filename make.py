#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make.py for Gramps addons.

Examples:
   python3 make.py gramps42 init AddonDirectory

      Creates the initial directories for the addon.

   python3 make.py gramps42 init AddonDirectory fr

      Creates the initial empty AddonDirectory/po/fr-local.po file
      for the addon.

   python3 make.py gramps42 update AddonDirectory fr

      Updates AddonDirectory/po/fr-local.po with the latest
      translations.

   python3 make.py gramps42 build AddonDirectory

      Build ../download/AddonDirectory.addon.tgz

   python3 make.py gramps42 build all

      Build ../download/*.addon.tgz

   python3 make.py gramps42 compile AddonDirectory
   python3 make.py gramps42 compile all

      Compiles AddonDirectory/po/*-local.po and puts the resulting
      .mo file in AddonDirectory/locale/*/LC_MESSAGES/addon.mo

   python3 make.py gramps42 listing AddonDirectory
   python3 make.py gramps42 listing all

   python3 make.py gramps42 clean
   python3 make.py gramps42 clean AddonDirectory

   python3 make.py gramps42 as-needed
       Builds the tgz for only addons that have changed, then recreates
       the listings and does cleanup

   python3 make.py gramps60 aggregate-pot
       Aggregates all `template.pot` files into a single `po/addons.pot` file.
       Strings that are already in `gramps.pot` are excluded.

   python3 make.py gramps60 extract-po
       Extracts strings from the aggregated `po/{lang}.po` files into the
       `{lang}-local.po` files for each addon.
"""
import configparser
import shutil
import glob
import sys
import os
import tarfile
import json
from xml.etree import ElementTree
from subprocess import call, Popen, PIPE

CONFIG_FILE = "make.ini"
config = {}                         # configuration file content

def system(scmd, **kwargs):
    """
    Replace and call system with scmd.
    """
    cmd = r(scmd, **kwargs)
    # print(cmd)
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
    Note: os.system("mkdir ...") cannot be used on Windows
    (mkdir mismatches with integrated cmd.exe command)
    """
    dirname = r(dirname)
    if os.path.isdir(dirname):
        return
    os.makedirs(dirname)

def get_config():
    global config

    try:
        if not config:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
    except configparser.Error as ce:
        print(f"? {ce}")
        exit(1)

def get_user_info():
    global config

    dflt = config["DEFAULT"]
    user = os.environ["USER"]
    user_name = f"{user}"
    user_email = f"{user}@example.com"
    if not dflt:
        dflt = {}
        dflt["user"] = user
        dflt["user_name"] = user_name
        dflt["user_email"] = user_email
    else:
        user = dflt["user"] if "user" in dflt else user
        user_name = dflt["user_name"] if "user_name" in dflt else user_name
        user_email = dflt["user_email"] if "user_email" in dflt else user_email
    
    config["DEFAULT"]["user"] = user
    config["DEFAULT"]["user_name"] = user_name
    config["DEFAULT"]["user_email"] = user_email
    return user, user_name, user_email

def get_maintainer_info():
    global config

    dflt = config["DEFAULT"]
    maint = os.environ["USER"]
    maint_name = f"{maint}"
    maint_email = f"{maint}@example.com"
    if not dflt:
        dflt = {}
        dflt["maintainer"] = maint
        dflt["maintainer_name"] = maint_name
        dflt["maintainer_email"] = maint_email
    else:
        maint = dflt["maintainer"] if "maintainer" in dflt else maint
        maint_name = dflt["maintainer_name"] if "maintainer_name" in dflt else maint_name
        maint_email = dflt["maintainer_email"] if "maintainer_email" in dflt else maint_email

    config["DEFAULT"]["maintainer"] = maint
    config["DEFAULT"]["maintainer_name"] = maint_name
    config["DEFAULT"]["maintainer_email"] = maint_email
    return maint, maint_name, maint_email

def check_installation():
    cmds = {"gh": "See https://githib.com/cli/cli for installation",
            "git": "Please install git with your package manager.",
    }
    missing = False
    for ii in cmds.keys():
        if shutil.which(ii):
            continue
        missing = True
        print(f"? Could not find the '{ii}' command")
        print(f"  {cmds[ii]}")
    if missing:
        exit(1)

def increment_target(filenames):
    """increment the version number in the gpr file"""
    for filename in filenames:
        oldfp = open(filename, "r", encoding="utf-8")
        newfp = open("%s.new" % filename, "w", encoding="utf-8", newline="")
        for line in oldfp:
            if (line.lstrip().startswith("version")) and ("=" in line):
                # print("orig = %s" % line.rstrip())
                line, stuff = line.rsplit(",", 1)
                line = line.rstrip()
                pos = line.index("version")
                indent = line[0:pos]
                var, gtv = line[pos:].split("=", 1)
                lyst = version(gtv.strip()[1:-1])
                lyst[2] += 1
                newv = ".".join(map(str, lyst))
                newline = "%sversion = '%s',\n" % (indent, newv)
                newfp.write(newline)
            else:
                newfp.write(line)
        oldfp.close()
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


def get_all_languages():
    """
    Return a list of all languages from all addons.
    """
    languages = set(["en"])
    for addon in [file for file in glob.glob("*") if os.path.isdir(file)]:
        for po in glob.glob(f"{addon}/po/*-local.po"):
            length = len(po)
            locale = po[length - 11 : length - 9]
            locale_path, locale = po.rsplit(os.sep, 1)
            languages.add(locale[:-9])
    return languages


def cleanup(addon_dir):
    """
    An OS agnostic cleanup routine
    """
    patterns = [
        "%s/*~" % addon_dir,
        "%s/po/*~" % addon_dir,
        #'%s/po/template.pot' % addon_dir,
        "%s/po/*-global.po" % addon_dir,
        "%s/po/*-temp.po" % addon_dir,
        "%s/po/??.po" % addon_dir,
        "%s/po/?????.po" % addon_dir,
        "%s/*.pyc" % addon_dir,
        "%s/*.pyo" % addon_dir,
    ]
    for pat in patterns:
        for file_ in glob.glob(pat):
            os.remove(file_)
    shutil.rmtree("%s/locale" % addon_dir, ignore_errors=True)


def do_tar(inc_files):
    """
    An OS agnostic tar creation that uses only Python libs
    inc_files is a list of filenames
    """
    if not inc_files:
        print("***Nothing to build! %s" % addon)
        exit()

    def tar_filt(tinfo):
        """make group and user names = 'gramps'"""
        tinfo.uname = tinfo.gname = "gramps"
        return tinfo

    mkdir(f"../addons/{gramps_version}/download")
    increment_target(glob.glob(f"{addon}/*gpr.py"))
    tar = tarfile.open(
        f"../addons/{gramps_version}/download/{addon}.addon.tgz",
        mode="w:gz",
        encoding="utf-8",
    )
    for inc_fil in inc_files:
        inc_fil = inc_fil.replace("\\", "/")
        tar.add(inc_fil, filter=tar_filt)
    tar.close()


def compile_addon(addon):
    """
    Compile a single addon.
    """
    for po in glob.glob(f"{addon}/po/*.po"):
        locale = os.path.basename(po[:-9])
        mkdir(f"{addon}/locale/{locale}/LC_MESSAGES/")
        system(f'msgfmt {po} -o "{addon}/locale/{locale}/LC_MESSAGES/addon.mo"')


def build_addon(addon):
    """
    Compile and build a single addon.
    """
    compile_addon(addon)

    if os.path.isfile(f"{addon}/setup.py"):
        system(f"cd {addon}; python3 setup.py --build")
        return

    patts = [
        f"{addon}/*.py",
        f"{addon}/*.glade",
        f"{addon}/*.xml",
        f"{addon}/*.txt",
        f"{addon}/locale/*/LC_MESSAGES/*.mo",
    ]
    if os.path.isfile(f"{addon}/MANIFEST"):
        patts.extend(open(f"{addon}/MANIFEST", "r").read().split())
    files = []
    for patt in patts:
        files.extend(glob.glob(patt))
    if files:
        do_tar(files)


def check_gramps_path(command):
    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ["GRAMPS_RESOURCES"] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment
    except ImportError:
        print(
            "Where is Gramps: '%s'? Use "
            "'GRAMPSPATH=path python3 make.py %s %s'"
            % (os.path.abspath(GRAMPSPATH), gramps_version, command)
        )
        exit()


def strip_header(po_file):
    """
    Strip the header off a `po` file and return its contents.
    """
    header = True
    out_file = ""
    if not os.path.isfile(po_file):
        return out_file
    with open(po_file, "r", encoding="utf-8") as in_file:
        for line in in_file:
            if not header:
                out_file += line
            if line == "\n":
                header = False
    return out_file


def aggregate_pot():
    """
    Aggregate the template files for all addons into a single file without
    strings that are already present in core Gramps.
    """
    f = open("po/template.pot", "w")
    f.close()

    args = ["xgettext", "-F", "-j", "-o", "po/template.pot"]
    args.extend(glob.glob("*/po/template.pot"))
    call(args)

    gramps_pot = os.path.join(GRAMPSPATH, "po/gramps.pot")
    args = ["msgcomm", "po/template.pot", gramps_pot]
    args.extend(["--unique"])
    args.extend(["-o", "po/unique.pot"])
    call(args)

    args = ["msgcomm", "po/template.pot", "po/unique.pot"]
    args.extend(["--more-than", "1"])
    args.extend(["-o", "po/addons.pot"])
    call(args)

    os.remove("po/template.pot")
    os.remove("po/unique.pot")


def extract_po(addon):
    """
    Extract the Weblate translations for a single addon.
    """
    po_dir = os.path.join(addon, "po")
    pot = os.path.join(po_dir, "template.pot")
    if not os.path.exists(pot):
        return
    for lang in get_all_languages():
        # print (lang)
        po = os.path.join(po_dir, f"{lang}-local.po")
        if os.path.exists(f"po/{lang}.po"):
            old_file = strip_header(po)
            args = ["msgmerge", f"po/{lang}.po", pot]
            args.extend(["--for-msgfmt"])
            args.extend(["--no-fuzzy-matching"])
            args.extend(["-o", po])
            call(args)
            new_file = strip_header(po)

            # Remove files that only consist of a header.
            if not new_file:
                os.remove(po)

            # Restore files that only have changes to the header.
            if new_file and old_file == new_file:
                args = ["git", "restore", po]
                call(args)

def usage():
    """
    what are my options?
    """
    print(f"usage: {sys.argv[0]} <version> <command> [<options>]")
    print("where:")
    print("    <version>    => Gramps maintenance branch name: one of")
    print("                    {gramps42 | gramps50 } gramps51 | gramps52 | gramps60}" )
    print("    <command>    => one of the following, with their <options>:")
    print()
    print("        as-needed:")
    print("            build packages (tgz files) for only those addons that have")
    print("            changed, then rebuild listings files, and do some cleanup.")
    print()
    print("        aggregate-pot:")
    print("            aggregates all 'template.pot' files into a single 'po/addons.pot'")
    print("            file. Strings already in 'gramps.pot' are excluded.")
    print()
    print("        build {<addon> | all}:")
    print("            build a specific adddon package if named and put it in")
    print("            addons/Addon/Addon.addon.tgz; or, if 'all' used, build")
    print("            a package for all existing addons.")
    print()
    print("        clean [<addon>]:")
    print("            remove unneeded local files, typically used before")
    print("            making commits; if <addon> is used, clean that specific")
    print("            addon, otherwise clean all addons.")
    print()
    print("        compile {<addon> | all}:")
    print("            compile AddOn/po/*-local.po files for the named addon")
    print("            and put the output .mo file in AddOn/locale/*/LC_MESSAGES/addon.mo;")
    print("            or, if 'all' is used, do the same thing for all addons.")
    print()
    print("        extract-po:")
    print("            extract strings from the aggregated 'po/<lang>.po' files")
    print("            into the '<lang>-local.po' files for each addon.")
    print()
    print("        {-h | --help | help}:")
    print("            print out this help message")
    print()
    print("        init <addon> [<lang>]:")
    print("            create a new addon working directory (use a name in")
    print("            in camel case); if <lang> is given, create an empty")
    print("            translation file (e.g., for 'fr', AddOn/po/fr-local.po)")
    print()
    print("        listing {<addon> | all}:")
    print("            create or update the <version>/listings/*.json files for")
    print("            the languages supported by the named addonput; or, if 'all'")
    print("            is used, do the same thing for all addons.")
    print()
    print("        manifest-check:")
    print("            verify that the manifest files for all addons are correct.")
    print()
    print("        unlist <addon>:")
    print("            remove the named addon from all language listings files.")
    print()
    print("        update <addon> <lang>:")
    print("            update the adddon with the latest translations for that")
    print("            language (e.g., for 'fr', AddOn/po/fr-local.po)")
    print("            in camel case); if <lang> is given, create an empty")
    print()
    print("        workspace <addon> <path>:")
    print("            create a directory tree at <path> with all gramps")
    print("            development source trees (gramps, addons-source, addons)")
    print("            needed to develop a new addon; additionally, create the")
    print("            AddOn source directory called <addon>, and add to it the")
    print("            basic AddOn.py, AddOn.grp.py, MANIFEST, and localization")
    print("            files that are required.")


def init_command(command, path, target_addon):
    # Get all of the strings from the addon and create template.po:
    pwd = os.environ["PWD"]
    os.chdir(path)
    if target_addon == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
    else:
        dirs = [os.path.join(path, target_addon)]
    if (command == "init" and len(sys.argv) == 4) or \
       (command == "workspace" and len(sys.argv) == 5):
        plugins = []
        try:
            sys.path.insert(0, GRAMPSPATH)
            os.environ["GRAMPS_RESOURCES"] = os.path.abspath(GRAMPSPATH)
            from gramps.gen.plug import make_environment
        except ImportError:
            print(
                "Where is Gramps: '%s'? Use "
                "'GRAMPSPATH=path python3 make.py %s init'"
                % (os.path.abspath(GRAMPSPATH), gramps_version)
            )

        def register(ptype, **kwargs):
            kwargs["ptype"] = ptype
            plugins.append(kwargs)

        for addonpath in dirs:
            addon = os.path.basename(addonpath)
            fnames = glob.glob("%s/*.py" % addon)
            if not fnames:
                continue
            # check if we need to initialize based on listing
            listed = False
            for gpr in glob.glob(f"{addon}/*.gpr.py"):
                plugins = []
                with open(gpr.encode("utf-8", errors="backslashreplace")) as f:
                    code = compile(
                        f.read(), gpr.encode("utf-8", errors="backslashreplace"), "exec"
                    )
                    exec(
                        code,
                        make_environment(_=lambda x: x),
                        {"register": register, "build_script": True},
                    )
                for p in plugins:
                    if p.get("include_in_listing", True):
                        listed = True  # got at least one listable plugin
            if not listed:
                continue  # skip this one if not listed

            where = os.path.join(addon, "po")
            os.makedirs(where, exist_ok=True)
            fnames = " ".join(glob.glob(f"{addon}/*.py"))
            system(
                f"xgettext --language=Python --keyword=_ --keyword=N_"
                f" --from-code=UTF-8"
                f' -o "{addon}/po/template.pot" {fnames} '
            )
            fnames = " ".join(glob.glob("%s/*.glade" % addon))
            if fnames:
                system(
                    "xgettext -j --add-comments -L Glade "
                    f'--from-code=UTF-8 -o "{addon}/po/template.pot" '
                    f"{fnames}"
                )

            # scan for xml files and get translation text where the tag
            # starts with an '_'.  Create a .h file with the text strings
            fnames = glob.glob("%s/*.xml" % addon)
            for filename in fnames:
                tree = ElementTree.parse(filename)
                root = tree.getroot()
                with open(filename + ".h", "w", encoding="utf-8") as head:
                    for key in root.iter():
                        if key.tag.startswith("_") and len(key.tag) > 1:
                            msg = key.text.replace('"', '\\"').replace("\n", "\\n")
                            txl = '_("%s")\n' % msg
                            head.write(txl)
                root.clear()
                # now append XML text to the pot
                system(
                    "xgettext -j --keyword=_ --from-code=UTF-8 "
                    f'--language=Python -o "{addon}/po/template.pot" '
                    f'"{filename}.h"'
                )
                os.remove(filename + ".h")
            # fix up the charset setting in the pot
            with open(
                "%s/po/template.pot" % addon, "r", encoding="utf-8", newline="\n"
            ) as file:
                contents = file.read()
            contents = contents.replace("charset=CHARSET", "charset=UTF-8")
            with open(
                "%s/po/template.pot" % addon, "w", encoding="utf-8", newline="\n"
            ) as file:
                file.write(contents)
    elif command == "init" and len(sys.argv) > 4:
        locale = sys.argv[4]
        # make a copy for locale
        if os.path.isfile(f"{addon}/po/{locale}-local.po"):
            raise ValueError(f'"{addon}/po/{locale}-local.po" already exists!')
        system(
            f"msginit --locale={locale} "
            f'--input="{addon}/po/template.pot" '
            f'--output="{addon}/po/{locale}-local.po"'
        )
        echo(f'You can now edit "{addon}/po/{locale}-local.po"')
    else:
        print(f"? do not know what to init in {addon}")
        exit(1)

    os.chdir(pwd)
    return

#--- main ------------------------------------------------------------
if "GRAMPSPATH" in os.environ:
    GRAMPSPATH = os.environ["GRAMPSPATH"]
else:
    GRAMPSPATH = "../../.."

#-- should probably convert to parseargs some day ....
if len(sys.argv) < 2:           # no parameters provided
    usage()
    exit(0)
elif len(sys.argv) == 2 and \
     (sys.argv[1] == "help" or sys.argv[1] == "-h" or sys.argv[1] == "--help"):
    usage()
    exit(0)

KNOWN_GRAMPS_VERSIONS = [
    "gramps42",
    "gramps50",
    "gramps51",
    "gramps52",
    "gramps60",
]

gramps_version = sys.argv[1]
if gramps_version not in KNOWN_GRAMPS_VERSIONS:
    print(f"? '{gramps_version}' is not a supported version of gramps")
    sys.exit(1)

command = sys.argv[2]
if len(sys.argv) >= 4:
    addon = sys.argv[3]

get_config()

if command == "clean":
    if len(sys.argv) == 3:
        for addon in [
            name
            for name in os.listdir(".")
            if os.path.isdir(name) and not name.startswith(".")
        ]:
            cleanup(addon)
    else:
        cleanup(addon)

elif command == "init":
    # Get all of the strings from the addon and create template.po:
    init_command(command, os.environ["PWD"], addon)

elif command == "update":
    locale = sys.argv[4]
    # Update the template file:
    if not os.path.isfile(f"{addon}/po/template.pot"):
        raise ValueError(
            f"{addon}/po/template.pot"
            " is missing!\n  run "
            f"./make.py {gramps_version} init {addon}"
        )
    # Check existing translation
    if not os.path.isfile(f"{addon}/po/{locale}-local.po"):
        raise ValueError(
            f"{addon}/po/{locale}-local.po"
            " is missing!\n run ./make.py "
            f"{gramps_version} init {addon} {locale}"
        )
    # Retrieve updated data for locale:
    system(
        f"msginit --locale={locale} "
        f'--input="{addon}/po/template.pot" '
        f'--output="{addon}/po/%(locale)s.po"'
    )
    # Merge existing local translation with last data:
    system(
        f"msgmerge --no-fuzzy-matching {addon}/po/{locale}-local.po "
        f"{addon}/po/{locale}.po"
        f' -o "{addon}/po/%(locale)s-local.po"'
    )
    # Start with Gramps main PO file:
    if not os.path.isdir(GRAMPSPATH + "/po"):
        raise ValueError(
            "Where is GRAMPSPATH/po: '%s/po'? Use"
            " 'GRAMPSPATH=path python3 make.py %s update'"
            % (GRAMPSPATH, gramps_version)
        )
    locale_po_files = [f"{GRAMPSPATH}/po/{locale}.po"]
    # Next, get all of the translations from other addons:
    for module in [name for name in os.listdir(".") if os.path.isdir(name)]:
        # skip the addon we are updating:
        if module == addon:
            continue
        po_file = f"{module}/po/{locale}-local.po"
        if os.path.isfile(po_file):
            locale_po_files.append(po_file)
    # Concat those together:
    file_list = " ".join(['''"%s"''' % name for name in locale_po_files])
    system(f'msgcat --use-first {file_list} -o "{addon}/po/{locale}-global.po"')
    # Merge the local and global:
    # locale_local = f"{module}/po/{locale}-local.po"
    # if os.path.isfile(locale_local):
    system(
        f"msgmerge --no-fuzzy-matching -U "
        f'"{addon}/po/{locale}-global.po" '
        f'"{addon}/po/{locale}-local.po" '
    )
    # Get all of the addon strings out of the catalog:
    f = open(f"{addon}/po/{locale}-temp.po", "w")
    f.close()

    system(
        f"msggrep --location={addon}/* "
        f'"{addon}/po/{locale}-global.po" '
        f'--output-file="{addon}/po/{locale}-temp.po"'
    )
    # Finally, add back any updates to the local version:
    system(
        f"msgcat --use-first "
        f'"{addon}/po/{locale}-temp.po" '
        f'"{addon}/po/{locale}-local.po" '
        f'-o "{addon}/po/{locale}-local.po.2" '
    )
    os.remove(f"{addon}/po/{locale}-local.po")
    os.rename(f"{addon}/po/{locale}-local.po.2", f"{addon}/po/{locale}-local.po")
    # # Done!
    echo(f'\nYou can edit "{addon}/po/{locale}-local.po"')

elif command == "compile":
    if addon == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
        for addon in dirs:
            compile_addon(addon)
    else:
        compile_addon(addon)

elif command == "build":
    if addon == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
        for addon in dirs:
            build_addon(addon)
    else:
        build_addon(addon)

elif command == "as-needed":
    import tempfile
    import difflib

    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ["GRAMPS_RESOURCES"] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment
    except ImportError:
        print(
            "Where is Gramps: '%s'? Use "
            "'GRAMPSPATH=path python3 make.py %s as_needed'"
            % (os.path.abspath(GRAMPSPATH), gramps_version)
        )
        exit()

    def register(ptype, **kwargs):
        global plugins
        kwargs["ptype"] = ptype
        plugins.append(kwargs)

    from filecmp import cmp

    languages = get_all_languages()
    listings = {lang: [] for lang in languages}
    if len(sys.argv) == 3 or addon == "all":
        dirs = [
            file
            for file in glob.glob("*")
            if os.path.isdir(file) and file != "__pycache__"
        ]
    else:
        dirs = [addon]
    for addon in sorted(dirs):
        todo = False
        for po in glob.glob(f"{addon}/po/*-local.po"):
            locale = os.path.basename(po[:-9])
            mkdir(f"{addon}/locale/{locale}/LC_MESSAGES/")
            system(f'msgfmt {po} -o "{addon}/locale/{locale}/LC_MESSAGES/addon.mo"')
        tgz = os.path.join(
            "..", "addons", gramps_version, "download", addon + ".addon.tgz"
        )
        patts = [
            f"{addon}/*.py",
            f"{addon}/*.glade",
            f"{addon}/*.xml",
            f"{addon}/*.txt",
            f"{addon}/locale/*/LC_MESSAGES/*.mo",
        ]
        if os.path.isfile(f"{addon}/MANIFEST"):
            patts.extend(open(f"{addon}/MANIFEST", "r").read().split())
        sfiles = []
        for patt in patts:
            sfiles.extend(glob.glob(patt))
        if not sfiles:
            # git doesn't remove empty folders when switching branchs
            continue
        try:
            archive = tarfile.open(tgz)
        except FileNotFoundError:
            print("Missing archive: %s" % addon)
            todo = True
            archive = None
        if archive:
            files = archive.getnames()
            tmpdir = tempfile.TemporaryDirectory()
            tdir = tmpdir.name
            archive.extractall(path=tdir)
            archive.close()
            for file in sfiles:
                # tar on Windows wants '/' not '\'
                _file = file.replace("\\", "/")
                if _file not in files:
                    print("Missing:         %s" % file)
                    todo = True
                    continue
                tfile = os.path.join(tdir, file)
                if os.path.isdir(file):
                    continue
                targ_diff = 0  # no difference
                if not cmp(tfile, file, shallow=False):
                    if ".gpr.py" in file:
                        with open(file) as sfil:
                            with open(tfile) as tfil:
                                diff = list(
                                    difflib.context_diff(
                                        sfil.readlines(), tfil.readlines(), n=0
                                    )
                                )
                                for line in diff:
                                    if "gramps_target_version" in line:
                                        print(
                                            "gpr differs:     %s %s" % (addon, line),
                                            end="",
                                        )
                                        targ_diff = 1  # Potential problem
                                        continue
                                    if (
                                        line.startswith("---")
                                        or line.startswith("***")
                                        or "version" in line.lower()
                                    ):
                                        continue
                                    targ_diff = 2  # just different
                    else:
                        targ_diff = 2  # just different
                if targ_diff == 0:
                    continue
                elif targ_diff == 1:
                    res = input(
                        "If gramps_target_version doesn't match, "
                        "something is wrong.\n"
                        "Do you want to continue (y/n)?"
                    )
                    if not res.lower().startswith("y"):
                        exit()
                print("Different:       %s" % file)
                todo = True
        if todo:
            # Build it.
            do_tar(sfiles)
            print("***Rebuilt:      %s" % addon)

        # Add addon to newly created listing (equivalent to 'listing all')
        for lang in languages:
            gpr_bad = False  # to flag a bad gpr
            do_list = False  # to avoid multiple pass per lang if not listing
            for gpr in glob.glob(f"{addon}/*.gpr.py"):
                # Make fallback language English (rather than current LANG)
                glocale.language = [lang]
                local_gettext = glocale.get_addon_translator(
                    gpr, languages=[lang, "en.UTF-8"]
                ).gettext
                plugins = []
                with open(gpr.encode("utf-8", errors="backslashreplace")) as f:
                    code = compile(
                        f.read(), gpr.encode("utf-8", errors="backslashreplace"), "exec"
                    )
                    exec(
                        code,
                        make_environment(_=local_gettext),
                        {"register": register, "build_script": True},
                    )
                if not plugins:
                    print("***Not Listable: %s  ('register' didn't work)" % gpr)
                    gpr_bad = True
                for p in plugins:
                    if p.get("include_in_listing", True):
                        do_list = True  # got at least one listable plugin
                        plugin = {
                            "n": p["name"],
                            "i": p["id"],
                            "t": p["ptype"],
                            "d": p["description"],
                            "v": p["version"],
                            "g": p["gramps_target_version"],
                            "s": p["status"],
                            "z": ("%s.addon.tgz" % addon),
                        }
                        if "requires_mod" in p:
                            plugin["rm"] = p["requires_mod"]
                        if "requires_gi" in p:
                            plugin["rg"] = p["requires_gi"]
                        if "requires_exe" in p:
                            plugin["re"] = p["requires_exe"]
                        if "help_url" in p:
                            plugin["h"] = p["help_url"]
                        if "audience" in p:
                            plugin["a"] = p["audience"]
                        listings[lang].append(plugin)
                        if lang == "en":
                            print("Listed:          %s" % p["name"])
                    else:
                        print("***Not Listed:   %s" % p["name"])
            if gpr_bad or not do_list:
                break
        cleanup(addon)
        if todo:  # make an updated pot file
            mkdir("%(addon)s/po")
            fnames = " ".join(glob.glob(f"{addon}/*.py"))
            system(
                "xgettext --language=Python --keyword=_ --keyword=N_"
                " --from-code=UTF-8"
                f' -o "{addon}/po/temp.pot" {fnames} '
            )
            fnames = " ".join(glob.glob(f"{addon}/*.glade"))
            if fnames:
                system(
                    "xgettext -j --add-comments -L Glade "
                    f'--from-code=UTF-8 -o "{addon}/po/temp.pot" '
                    f"{fnames}"
                )

            # scan for xml files and get translation text where the tag
            # starts with an '_'.  Create a .h file with the text strings
            fnames = glob.glob("%s/*.xml" % addon)
            for filename in fnames:
                tree = ElementTree.parse(filename)
                root = tree.getroot()
                with open(filename + ".h", "w", encoding="utf-8") as head:
                    for key in root.iter():
                        if key.tag.startswith("_") and len(key.tag) > 1:
                            msg = key.text.replace('"', '\\"').replace("\n", "\\n")
                            txl = '_("%s")\n' % msg
                            head.write(txl)
                root.clear()
                # now append XML text to the pot
                system(
                    "xgettext -j --keyword=_ --from-code=UTF-8 "
                    f'--language=Python -o "{addon}/po/temp.pot" '
                    f'"{filename}.h"'
                )
                os.remove(filename + ".h")
            if os.path.isfile(f"{addon}/po/template.pot"):
                # we do a merge so changes to header are not lost
                system(
                    "msgmerge --no-fuzzy-matching -U "
                    f"{addon}/po/template.pot "
                    f"{addon}/po/temp.pot"
                )
                os.remove(f"{addon}/po/temp.pot")
            else:
                os.rename(f"{addon}/po/temp.pot", f"{addon}/po/template.pot")
    # write out the listings
    mkdir(f"../addons/{gramps_version}/listings")
    for lang in languages:
        output = []
        for plugin in sorted(listings[lang], key=lambda p: (p["t"], p["i"])):
            output.append(plugin)
        with open(
            f"../addons/{gramps_version}/listings/" + ("addons-%s.json" % lang),
            "w",
            encoding="utf-8",
            newline="",
        ) as fp_out:
            json.dump(output, fp_out, indent=0)

elif command == "manifest-check":
    import re

    for tgz in glob.glob(f"../addons/{gramps_version}/download/*.tgz"):
        files = tarfile.open(tgz).getnames()
        for file in files:
            if not any(
                [
                    re.match(r".*\.py$", file),
                    re.match(r".*\.txt$", file),
                    re.match(r".*\.glade$", file),
                    re.match(r".*\.xml$", file),
                    re.match(".*locale/.*/LC_MESSAGES/.*.mo", file),
                ]
            ):
                print("Need to add", file, "in", tgz)

elif command == "unlist":
    # Get all languages from all addons:
    cmd_arg = addon
    languages = get_all_languages()
    for lang in languages:
        lines = []
        fp = open(
            f"../addons/{gramps_version}/listings/" + ("addons-%s.json" % lang),
            "r",
            encoding="utf-8",
        )
        for line in json.load(fp):
            if line["z"] != cmd_arg + ".addon.tgz":
                lines.append(line)
            else:
                print("unlisting", line)
        fp.close()
        fp = open(
            f"../addons/{gramps_version}/listings/" + ("addons-%s.json" % lang),
            "w",
            encoding="utf-8",
            newline="",
        )
        json.dump(lines, fp, indent=0)
        fp.close()

elif command == "check":
    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ["GRAMPS_RESOURCES"] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment
    except ImportError:
        print(
            "Where is Gramps: '%s'? Use "
            "'GRAMPSPATH=path python3 make.py %s check'"
            % (os.path.abspath(GRAMPSPATH), gramps_version)
        )
        exit()

    def register(ptype, **kwargs):
        global plugins
        kwargs["ptype"] = ptype
        plugins.append(kwargs)

    # get current build numbers from English listing
    fp_in = open(
        f"../addons/{gramps_version}/listings/addons-en.json", "r", encoding="utf-8"
    )
    addons = {}
    for line in json.load(fp_in):
        if line["i"] in addons:
            print("Repeated addon ID:", line["i"])
        else:
            addons[line["i"]] = line
    # go through all gpr's, check their build versions
    for gpr in glob.glob(f"*/*.gpr.py"):
        glocale.language = ["en"]
        local_gettext = glocale.get_addon_translator(
            gpr, languages=["en", "en.UTF-8"]
        ).gettext
        plugins = []
        with open(gpr.encode("utf-8", errors="backslashreplace")) as f:
            code = compile(
                f.read(), gpr.encode("utf-8", errors="backslashreplace"), "exec"
            )
            exec(
                code,
                make_environment(_=local_gettext),
                {"register": register, "build_script": True},
            )
        for p in plugins:
            gpr_version = p.get("version", None)
            id_ = p.get("id", None)
            if id_ not in addons:
                print("Missing in listing:", id_)
            else:
                add_version = addons[id_]["v"]
                if gpr_version != add_version:
                    print("Different versions:", id_, gpr_version, add_version)
                    # if number diff from gpr, report it

elif command == "listing":
    try:
        sys.path.insert(0, GRAMPSPATH)
        os.environ["GRAMPS_RESOURCES"] = os.path.abspath(GRAMPSPATH)
        from gramps.gen.const import GRAMPS_LOCALE as glocale
        from gramps.gen.plug import make_environment
    except ImportError:
        print(
            "Where is Gramps: '%s'? Use "
            "'GRAMPSPATH=path python3 make.py %s listing'"
            % (os.path.abspath(GRAMPSPATH), gramps_version)
        )
        exit()

    def register(ptype, **kwargs):
        global plugins
        kwargs["ptype"] = ptype
        plugins.append(kwargs)

    cmd_arg = addon
    # first, get a list of all of the possible languages
    if cmd_arg == "all":
        dirs = [file for file in glob.glob("*") if os.path.isdir(file)]
    else:
        dirs = [addon]
    # Make the locale for for any local languages for Addon:
    for addon in dirs:
        for po in glob.glob(f"{addon}/po/*-local.po"):
            # Compile
            locale = os.path.basename(po[:-9])
            mkdir(f"{addon}/locale/{locale}/LC_MESSAGES/")
            system(f'msgfmt {po} -o "{addon}/locale/{locale}/LC_MESSAGES/addon.mo"')
    languages = get_all_languages()
    # next, create/edit a file for all languages listing plugins
    for lang in languages:
        print("Building listing for '%s'..." % lang)
        listings = []
        for addon in dirs:
            for gpr in glob.glob(f"{addon}/*.gpr.py"):
                # Make fallback language English (rather than current LANG)
                glocale.language = [lang]
                local_gettext = glocale.get_addon_translator(
                    gpr, languages=[lang, "en.UTF-8"]
                ).gettext
                plugins = []
                with open(gpr.encode("utf-8", errors="backslashreplace")) as f:
                    code = compile(
                        f.read(), gpr.encode("utf-8", errors="backslashreplace"), "exec"
                    )
                    exec(
                        code,
                        make_environment(_=local_gettext),
                        {"register": register, "build_script": True},
                    )
                for p in plugins:
                    tgz_file = "%s.addon.tgz" % gpr.split(os.sep, 1)[0]
                    tgz_exists = os.path.isfile(
                        f"../addons/{gramps_version}/download/" + tgz_file
                    )
                    if p.get("include_in_listing", True) and tgz_exists:
                        plugin = {
                            "n": p["name"],
                            "i": p["id"],
                            "t": p["ptype"],
                            "d": p["description"],
                            "v": p["version"],
                            "g": p["gramps_target_version"],
                            "s": p["status"],
                            "z": (tgz_file),
                        }
                        if "requires_mod" in p:
                            plugin["rm"] = p["requires_mod"]
                        if "requires_gi" in p:
                            plugin["rg"] = p["requires_gi"]
                        if "requires_exe" in p:
                            plugin["re"] = p["requires_exe"]
                        if "help_url" in p:
                            plugin["h"] = p["help_url"]
                        if "audience" in p:
                            plugin["a"] = p["audience"]
                        listings.append(plugin)
                    else:
                        print("   ignoring '%s'" % (p["name"]))
        # Write out new listing:
        output = []
        if cmd_arg == "all":
            # Replace it!
            for plugin in sorted(listings, key=lambda p: (p["t"], p["i"])):
                output.append(plugin)
        elif not os.path.isfile(
            f"../addons/{gramps_version}/listings/" + ("addons-%s.json" % lang)
        ):
            for plugin in sorted(listings, key=lambda p: (p["t"], p["i"])):
                output.append(plugin)
        else:
            # just update the lines from these addons:
            for plugin in sorted(listings, key=lambda p: (p["t"], p["i"])):
                already_added = []
                fp_in = open(
                    f"../addons/{gramps_version}/listings/" + ("addons-%s.json" % lang),
                    "r",
                    encoding="utf-8",
                )
                added = False
                for line in json.load(fp_in):
                    if line["i"] in already_added:
                        continue
                    if (
                        cmd_arg + ".addon.tgz" == line["z"]
                        and plugin["t"] == line["t"]
                        and not added
                    ):
                        # print("UPDATED")
                        output.append(plugin)
                        added = True
                        already_added.append(line["i"])
                    elif (
                        (plugin["t"], plugin["i"]) < (line["t"], line["i"])
                    ) and not added:
                        # print("ADDED in middle")
                        output.append(plugin)
                        added = True
                        output.append(line)
                        already_added.append(line["i"])
                    else:
                        output.append(line)
                        already_added.append(line["i"])
                if not added:
                    if plugin["i"] not in already_added:
                        # print("ADDED at end")
                        output.append(plugin)
        mkdir(f"../addons/{gramps_version}/listings")
        fp_out = open(
            f"../addons/{gramps_version}/listings/" + ("addons-%s.json" % lang),
            "w",
            encoding="utf-8",
            newline="",
        )
        json.dump(output, fp_out, indent=0)

elif command == "aggregate-pot":
    check_gramps_path(command)
    aggregate_pot()

elif command == "extract-po":
    for addon in [
        file for file in glob.glob("*") if os.path.isdir(file) and file != "po"
    ]:
        print(addon)
        extract_po(addon)

elif command == "workspace":
    import subprocess

    def is_camel_case(s):
        return s != s.lower() and s != s.upper() and "_" not in s

    def addon_template(path, addon):
        addonpy = os.path.join(path, f"{addon}.py")
        if os.path.exists(addonpy):
            print(f"? {addon}.py exists, skipping step...")
        else:
            with open(addonpy, "w+") as fd:
                print(f"#/usr/bin/env python3", file=fd)
                print(f"#", file=fd)
                print(f"#   Add your code here", file=fd)
                print(f"#", file=fd)
            fd.close()

    def gpr_template(path, addon):
        global config

        addongpr = os.path.join(path, f"{addon}.gpr.py")
        if os.path.exists(addongpr):
            print(f"? {addon}.gpr.py exists, skipping step...")
        else:
            user, user_name, user_email = get_user_info()
            maint_user, maint_name, maint_email = get_maintainer_info()
            with open(addongpr, "w+") as fd:
                print(f"#", file=fd)
                print(f"#   Registration file for addon {addon}", file=fd)
                print(f"#", file=fd)
                fd.write(f"""
#
# This file has been generated for you as a starting point.
#
# You MUST edit it for it to be useful.
#

register(TOOL,                                     # change to the proper type
    id    = '{addon}',
    name  = _("{addon}"),
    description =  _("describe {addon} here."),
    version = '1.0.0',
    gramps_target_version = '6.0',
    status = STABLE,
    fname = '{addon}.py',
    # your name and email here ...
    authors = ["{user_name}"],
    authors_email = ["{user_email}"],
    # the maintainer's name and email here (can be you, of course) ...
    maintainers = ["{maint_name}"],
    maintainers_email = ["{maint_email}"],
    # change the following as needed
    category = TOOL_DBPROC,
    toolclass = '{addon}Window',
    optionclass = '{addon}Options',
    tool_modes = [TOOL_MODE_GUI],
    help_url = "Addon:{addon}Tool"
)
""")
            fd.close()

    def fork_exists(user, name):
        exists = False
        res = subprocess.run(["gh", "repo", "list"],
                             capture_output=True,
                             text=True)
        expected = user + "/" + name
        if res.stdout.find(expected):
            exists = True
        return exists

    if gramps_version < "gramps60":
        print(f"? workspace command not supported for '{gramps_version}'")
        exit(1)
    check_installation()
    user, user_name, user_email = get_user_info()
    maint, maint_name, maint_email = get_maintainer_info()

    # build the directory structure
    if len(sys.argv) < 5:
        print("? workspace requires an <addon> and a <path> name.")
        exit(1)
    path = os.path.expandvars(os.path.expanduser(sys.argv[4]))
    if os.path.exists(path):
        if os.path.isdir(path):
            print(f"workspace path '{sys.argv[4]}' already exists, reusing...")
        else:
            print(f"? workspace path '{sys.argv[4]}' already exists, but not a directory")
            exit(1)
    else:
        os.makedirs(path)

    # get the addon name; we'll need to make a directory for it later
    addon = sys.argv[3]
    if not is_camel_case(addon):
        print(f"? addon name must be camel case, not '{addon}'")
        exit(1)

    # collect a copy of the gramps source tree
    print("gather up gramps source tree...")
    where = os.path.join(path, "gramps")
    gitcmd = []
    cwd = path
    if os.path.exists(where):
        gitcmd = [
            "gh", "repo", "sync",
            "--branch", f"maintenance/{gramps_version}",
        ]
        cwd = os.path.join(cwd, "gramps")
    else:
        if fork_exists(user, "gramps"):
            gitcmd = ["gh", "repo", "clone", "gramps"]
        else:
            gitcmd = [
                "gh", "repo", "fork",
                "https://github.com/gramps-project/gramps.git",
                "--", "-b", f"maintenance/{gramps_version}",
            ]
    res = subprocess.run(gitcmd, cwd=cwd, text=True)

    # collect a copy of the addons-source source tree
    print("gather up addons-source tree...")
    where = os.path.join(path, "addons-source")
    gitcmd = []
    cwd = path
    if os.path.exists(where):
        gitcmd = [
            "gh", "repo", "sync",
            "--branch", f"maintenance/{gramps_version}",
        ]
        cwd = os.path.join(cwd, "addons-source")
    else:
        if fork_exists(user, "addons-source"):
            gitcmd = ["gh", "repo", "clone", "addons-source"]
        else:
            gitcmd = [
                "gh", "repo", "fork",
                "https://github.com/gramps-project/addons-source.git",
                "--", "-b", f"maintenance/{gramps_version}",
            ]
    res = subprocess.run(gitcmd, cwd=cwd, text=True)

    # collect a copy of the addons source tree
    print("gather up addons tree...")
    where = os.path.join(path, "addons")
    gitcmd = []
    cwd = path
    if os.path.exists(where):
        gitcmd = [
            "gh", "repo", "sync",
        ]
        cwd = os.path.join(cwd, "addons")
    else:
        if fork_exists(user, "addons"):
            gitcmd = ["gh", "repo", "clone", "addons"]
        else:
            gitcmd = [
                "gh", "repo", "fork",
                "https://github.com/gramps-project/addons.git",
            ]
    res = subprocess.run(gitcmd, cwd=cwd, text=True)

    # now we can make the addon directory
    addonpath = os.path.join(path, "addons-source", addon)
    if os.path.exists(addonpath):
        if os.path.isdir(addonpath):
            print(f"addon directory '{addon}' already exists, reusing...")
        else:
            print(f"? addon file '{addon}' exists, but not a directory")
            exit(1)
    else:
        print(f"creating addon directory for '{addon}'...")
        os.makedirs(addonpath)

    # add in some templates if needed
    addon_template(addonpath, addon)
    gpr_template(addonpath, addon)
    init_command(command, os.path.join(path, "addons-source"), addon)

    # write out the config file
    with open(os.path.join(path, "addons-source", CONFIG_FILE), "w+") as cfd:
        config.write(cfd)

else:
    print(f"? unknown command: {command}")
    exit(1)

