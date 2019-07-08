#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016 Douglas Blank <doug.blank@gmail.com>
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
import importlib
module1 = importlib.find_loader("psycopg2") is not None
# Don't register if not runnable, but have to 'Make build' anyway
if module1 or locals().get('build_script'):
    register(DATABASE,
             id='postgresql',
             name=_('PostgreSQL'),
             name_accell=_('_PostgreSQL Database'),
             description=_('PostgreSQL Database'),
             version = '1.0.6',
             gramps_target_version='5.1',
             status=STABLE,
             fname='postgresql.py',
             databaseclass='PostgreSQL',
             authors=['Doug Blank'],
             authors_email=['doug.blank@gmail.com']
    )
elif locals().get('uistate'):  # don't start GUI if in CLI mode, just ignore
    from gramps.gen.config import config
    from gramps.gui.dialog import QuestionDialog2
    from gramps.gen.config import logging
    if not module1:
        warn_msg = _("PostgreSQL Warning:  Python psycopg2 module not found.")
        logging.log(logging.WARNING, warn_msg)
    inifile = config.register_manager("postgresqlwarn")
    inifile.load()
    sects = inifile.get_sections()
    if 'postgresqlwarn' not in sects:
        yes_no = QuestionDialog2(_("PostgreSQL Failed to Load"),
            _("\n\nPostgreSQL is missing the psycopg2 python module.\n"
              "For now, it may be possible to install the files manually. See\n\n"
              "https://gramps-project.org/wiki/index.php?title=PostgreSQL \n\n"
              "To dismiss all future PostgreSQL warnings click Dismiss."),
            _(" Dismiss "),
            _("Continue"), parent=uistate.window)
        prompt = yes_no.run()
        if prompt is True:
            inifile.register('postgresqlwarn.MissingModules', "")
            inifile.set('postgresqlwarn.MissingModules', "True")
            inifile.save()
