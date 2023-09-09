#
#
# Copyright (C) 2022      David M. Straub
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
#
# -------------------------
#
# S3 Media Uploader
#
# -----------------------
register(
    TOOL,
    id="s3uploader",
    name=_("S3 Media Uploader"),
    category=TOOL_UTILS,
    status=STABLE,
    fname="S3MediaUploader.py",
    toolclass="S3MediaUploader",
    optionclass="S3MediaUploaderOptions",
    tool_modes=[TOOL_MODE_CLI],
    authors=["David M. Straub"],
    authors_email=["straub@protonmail.com"],
    description=_(
        "Upload media files to S3 (or compatible) object-based storage via the command line."
    ),
    version = '0.1.6',
    gramps_target_version="5.2",
    requires_mod=["python-dateutil", "urllib3", "botocore", "jmespath", "s3transfer", "boto3"],
)
