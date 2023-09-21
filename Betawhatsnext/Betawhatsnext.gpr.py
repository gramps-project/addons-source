# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Benny Malengier
# Copyright (C) 2011 Nick Hall
# Copyright (C) 2011 Tim G L Lyons
# Copyright (C) 2023 Brian McCullough
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

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------

# from gramps.gen.plug._pluginreg import register, STABLE, BETA, EXPERIMENTAL, UNSTABLE, DEVELOPER, GRAMPLET
# from gramps.gen.const import GRAMPS_LOCALE as glocale
# _ = glocale.translation.sgettext

MODULE_VERSION = "5.2"


# ------------------------------------------------------------------------
#
# Register Gramplet
#
# ------------------------------------------------------------------------


register(GRAMPLET,
         id="Beta What's Next",
         name=_("Beta What's Next"),
         description=_("Beta Gramplet suggesting items to research"),
         status=STABLE,
         audience=EVERYONE,
         maintainers=["Reinhard Mueller", "Jakim Friant", "Brian McCullough"],
         maintainers_email=["", "jmodule@friant.org" ,"emyoulation@yahoo.com"],
         fname="Betawhatsnext.py",
         height=230,
         expand=True,
         gramplet='BetaWhatNextGramplet',
         gramplet_title=_("Beta What's Next?"),
         version = '0.1.5',
         help_url="https://github.com/emyoulation/_BetaDashboards/blob/5.2/README.md",
         gramps_target_version=MODULE_VERSION,
         )
