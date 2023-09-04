"""Upload media files to S3 via the command line."""
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
# $Id$
#

import logging
import os
import sys

from gramps.gen.utils.file import create_checksum, expand_media_path
from gramps.gui.plug import tool

_LOG = logging.getLogger("S3MediaUploader")

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    _LOG.error(
        "The S3 media uploader add-on requires the boto3"
        "Python library to be installed."
    )
    sys.exit(1)


class S3MediaUploader(tool.Tool):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        """Initialize tool."""
        tool.Tool.__init__(self, dbstate, options_class, name)
        self.dbstate = dbstate
        self.run_tool()

    def run_tool(self):
        """Run the tool."""
        bucket_name = self.options.handler.options_dict["bucket_name"]
        endpoint_url = self.options.handler.options_dict["endpoint_url"] or None
        try:
            uploader = S3MediaUploadHandler(
                db=self.dbstate.db,
                bucket_name=bucket_name,
                endpoint_url=endpoint_url,
                create=True,
                logger=_LOG,
            )
        except (BotoCoreError, ClientError) as err:
            _LOG.error(err)
            return None
        uploader.upload_missing()


class S3MediaUploaderOptions(tool.ToolOptions):
    """Options class for S3 Media Uploader addon."""

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        self.options_dict = {
            "bucket_name": "",
            "endpoint_url": "",
        }
        self.options_help = {
            "bucket_name": ("=str", "Name of the bucket to store files in.", "string"),
            "endpoint_url": (
                "=str",
                "Altnerative endpoint URL for S3-compatible storage.",
                "string",
            ),
        }


class S3MediaUploadHandler:
    """Class to upload media objects to an S3 bucket.

    Based on https://github.com/DavidMStraub/gramps-webapp/.
    """

    def __init__(self, db, bucket_name, endpoint_url=None, create=False, logger=None):
        """Initialize the class.

        `db` is an instance of an appropriate subclass of `gramps.gen.db.base.DbReadBase`.
        `bucket_name` is the S3 bucket name.
        If `create` is True, the bucket will be created if it doesn't exist.
        """
        self.db = db
        self.bucket_name = bucket_name
        self.s3 = boto3.resource("s3", endpoint_url=endpoint_url)
        self.client = boto3.client("s3", endpoint_url=endpoint_url)
        self.logger = logger or logging.getLogger()
        if create:
            if self.bucket_exists:
                self.logger.debug("Bucket {} already exists".format(bucket_name))
            else:
                self.logger.warning(
                    "Bucket {} not found. Creating ...".format(bucket_name)
                )
                region_name = boto3.session.Session().region_name
                bucket_config = {}
                if region_name:
                    bucket_config = {"LocationConstraint": region_name}
                self.client.create_bucket(
                    Bucket=bucket_name, CreateBucketConfiguration=bucket_config
                )
        self.bucket = self.s3.Bucket(self.bucket_name)
        self.base_path = expand_media_path(self.db.get_mediapath(), self.db)

    @property
    def bucket_exists(self):
        """Return boolean if the bucket exists."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as err:
            error_code = int(err.response["Error"]["Code"])
            if error_code == 404:  # bucket does not exist
                return False
        return True

    def get_remote_objects(self):
        """Get a set of all names of objects (media hashes) in the bucket."""
        return set(obj.key for obj in self.bucket.objects.all())

    def get_local_objects(self):
        """Get a dictionary of handle, hash, and mime types of all media objects
        in the database."""
        return {
            media_obj.handle: {
                "checksum": media_obj.get_checksum(),
                "mime": media_obj.get_mime_type(),
            }
            for media_obj in self.db.iter_media()
        }

    def get_full_path(self, handle):
        """Get the full local path to a media object by handle."""
        media_obj = self.db.get_media_from_handle(handle)
        return os.path.join(self.base_path, media_obj.path)

    def check_checksum(self, handle, checksum):
        """Check the media object's checksum, returning a boolean."""
        full_path = self.get_full_path(handle)
        new_checksum = create_checksum(full_path)
        return new_checksum == checksum

    def upload(self, handle, checksum, mime):
        """Upload a media object with given handle, hash, and MIME type."""
        path = self.get_full_path(handle)
        if not os.path.exists(path):
            self.logger.error("File {} not found. Skipping upload".format(path))
            return False
        if not self.check_checksum(handle, checksum):
            self.logger.error(
                "Found checksum mismatch for file {}. Skipping upload".format(path)
            )
            self.logger.error(
                "Old: {}, New: {}".format(checksum, create_checksum(path))
            )
            return False
        try:
            self.client.upload_file(
                path, self.bucket_name, checksum, ExtraArgs={"ContentType": mime}
            )
        except ClientError as err:
            logging.error(err)
            return False
        return True

    def upload_all(self):
        """Upload all media objects (overwriting existing ones)."""
        local_objects = self.get_local_objects()
        for handle, v in local_objects.items():
            self.upload(handle, **v)

    def upload_missing(self):
        """Upload the media objects that are not yet in the bucket."""
        local_objects_dict = self.get_local_objects()
        checksum_dict = {
            v["checksum"]: (handle, v["mime"])
            for handle, v in local_objects_dict.items()
        }
        local_checksums = set(obj["checksum"] for obj in local_objects_dict.values())
        remote_checksums = self.get_remote_objects()
        missing = local_checksums - remote_checksums
        num_missing = len(missing)
        self.logger.info("Found {} objects to upload.".format(num_missing))
        for i, checksum in enumerate(missing):
            self.logger.info(
                "Uploading file {} of {} ({}%)".format(
                    i + 1, num_missing, round(100 * i / num_missing)
                )
            )
            handle, mime = checksum_dict[checksum]
            self.upload(handle, checksum, mime)
