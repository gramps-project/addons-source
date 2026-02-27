# Copyright (C) 2026  Ludwig Tiston <help.ludwig@proton.me>
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
# along with this program; if not, see <https://www.gnu.org/licenses/>.

register(
    GRAMPLET,
    gramps_target_version = '6.0',
    version = '1.0.1',
    id="ArchiveAssist",
    name="Archive Assist",
    description=_("Parses strings from Riksarkivet and ArkivDigital to create sources and citations."),
    status=STABLE,
    fname="ArchiveAssist.py",
    gramplet="ArchiveAssist",
    gramplet_title=_("Archive Assist"),
    authors = ["Ludwig Tiston"],
    authors_email = ["help.ludwig@proton.me"],
    help_url="https://gramps-project.org/wiki/index.php/Addon:ArchiveAssist"
)
