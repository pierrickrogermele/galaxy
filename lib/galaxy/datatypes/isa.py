"""
ISA datatype

See http://isa-tools.org

"""

from __future__ import print_function

import re
import os
import sys
import json
import shutil
import zipfile
import logging
import tarfile
import tempfile
from io import BytesIO
from cgi import escape
from galaxy.util import unicodify
from galaxy.datatypes import data
from galaxy.datatypes import metadata

# the name of file containing the isa archive
ISA_ARCHIVE_NAME = "archive"

# archives types
_FILE_TYPE_PREFIX = {
    "\x1f\x8b\x08": "gz",
    "\x42\x5a\x68": "bz2",
    "\x50\x4b\x03\x04": "zip"
}
_MAX_LEN_FILE_TYPE_PREFIX = max(len(x) for x in _FILE_TYPE_PREFIX)
_FILE_TYPE_REGEX = re.compile("(%s)" % "|".join(map(re.escape, _FILE_TYPE_PREFIX.keys())))

# configure logger
logger = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(name)s %(levelname)s %(asctime)s %(message)s")
ch.setFormatter(formatter)
logger.handlers = []
logger.propagate = False
logger.addHandler(ch)
logger.setLevel(logging.DEBUG)


class Isa(data.Data):
    """ Base class for implementing ISA datatypes """
    file_ext = "isa"
    composite_type = 'auto_primary_file'
    allow_datatype_change = False
    is_binary = True

    # metadata.MetadataElement(name="base_name", desc="base name isa tab dataset",
    #                          default='Text',
    #                          readonly=True, set_in_upload=True)

    def __init__(self, **kwd):
        data.Data.__init__(self, **kwd)
        self.add_composite_file(ISA_ARCHIVE_NAME, is_binary=True, optional=True)

    def get_investigation_filename(self, files_list):
        """ Return the investigation filename """
        raise NotImplementedError()

    def _extract_archive(self, stream, output_path=None):
        # extract the archive to a temp folder
        if output_path is None:
            output_path = tempfile.mkdtemp()
        # try to detect the type of the compressed archive
        a_type = self._detect_file_type(stream)
        # decompress the archive
        if a_type == "zip":
            self._extract_zip_archive(stream, output_path)
        elif a_type == "gz":
            self._extract_tar_archive(stream, output_path)
        else:
            raise Exception("Not supported archive format!!!")

        return output_path

    def _list_archive_files(self, stream):
        # try to detect the type of the compressed archive
        a_type = self._detect_file_type(stream)
        # decompress the archive
        if a_type == "zip":
            data = BytesIO(stream.read())
            zip_ref = zipfile.ZipFile(data)
            files_list = zip_ref.namelist()
        elif a_type == "gz":
            with tarfile.open(fileobj=stream) as tar:
                files_list = [i.name for i in tar]
        else:
            raise Exception("Not supported archive format!!!")
        # filter the base path if it exists
        if len(files_list) > 0:
            base_path = files_list[0].split("/")[0]
            logger.debug("Base path: %s" % base_path)
            if base_path:
                # the TAR archive encodes the base_path without a final '/'
                if base_path in files_list:
                    files_list.remove(base_path)
                # the ZIP archive encodes the base_path with a final '/'
                base_path = os.path.join(base_path, '')
                if base_path in files_list:
                    files_list.remove(base_path)
                # remove the base_path from all remaining files
                files_list = [f.replace(base_path, '') for f in files_list]
        return files_list

    def _detect_file_type(self, stream):
        """
        Try to detect the type of the dataset archive.

        :param dataset:
        :return: _ZIP or _TAR if the file type is detected; None otherwise.
        """
        file_type = None
        file_start = stream.read(_MAX_LEN_FILE_TYPE_PREFIX)
        stream.seek(0)  # reset the stream
        matched_prefix = _FILE_TYPE_REGEX.match(file_start)
        if matched_prefix:
            file_type = _FILE_TYPE_PREFIX[matched_prefix.string[matched_prefix.start():matched_prefix.end()]]
        logger.debug("Detected file type: %s (prefix: %r)" % (file_type, file_start))
        return file_type

    def set_peek(self, dataset, is_multi_byte=False):
        """Set the peek and blurb text"""
        data = None
        if not dataset or not dataset.dataset or not dataset.dataset.extra_files_path:
            raise RuntimeError("Unable to find the 'files-path'!")
        files_path = dataset.dataset.extra_files_path
        files = os.listdir(files_path)
        primary_file = self.get_investigation_filename(files)
        if primary_file is None:
            raise RuntimeError("Unable to find the investigation file within the 'files_path' folder")
        with open(os.path.join(files_path, primary_file), "r") as f:
            data = f.readlines()
        if not dataset.dataset.purged and data:
            dataset.peek = json.dumps({"data": data})
            dataset.blurb = 'data'
        else:
            dataset.peek = 'file does not exist'
            dataset.blurb = 'file purged from disk'

    def display_peek(self, dataset):
        logger.debug("Dataset: %r" % dataset)
        logger.debug("Files path: %s" % dataset.dataset.extra_files_path)
        logger.debug("Displaying PEEK")
        # raise Exception("Display PEKEK")
        """Create HTML table, used for displaying peek"""
        out = ['<table cellspacing="0" cellpadding="3">']
        try:
            if not dataset.peek:
                dataset.set_peek()
            json_data = json.loads(dataset.peek)
            for line in json_data["data"]:
                line = line.strip()
                if not line:
                    continue
                out.append('<tr><td>%s</td></tr>' % escape(unicodify(line, 'utf-8')))
            out.append('</table>')
            out = "".join(out)
        except Exception as exc:
            out = "Can't create peek %s" % str(exc)
        return out

    def _extract_zip_archive(self, stream, target_path):
        logger.debug("Decompressing the ZIP archive")
        data = BytesIO(stream.read())
        zip_ref = zipfile.ZipFile(data)
        zip_ref.extractall(path=target_path)

    def _extract_tar_archive(self, stream, target_path):
        logger.debug("Decompressing the TAR archive")
        with tarfile.open(fileobj=stream) as tar:
            tar.extractall(path=target_path)

    def generate_primary_file(self, dataset=None):
        logger.debug("Dataset type: %s, keys=%s, values=%s" % (type(dataset), dataset.keys(), dataset.values()))
        rval = ['<html><head><title>ISA Dataset </title></head><p/>']
        rval.append('<div>ISA Dataset composed of the following files:<p/><ul>')
        for composite_name, composite_file in self.get_composite_files(dataset=dataset).items():
            fn = composite_name
            opt_text = ''
            if composite_file.optional:
                opt_text = ' (optional)'
            if composite_file.get('description'):
                rval.append('<li><a href="%s" type="text/plain">%s (%s)</a>%s</li>' % (
                    fn, fn, composite_file.get('description'), opt_text))
            else:
                rval.append('<li><a href="%s" type="text/plain">%s</a>%s</li>' % (fn, fn, opt_text))
        rval.append('</ul></div></html>')
        return "\n".join(rval)
            logger.debug("Dataset: %r", dataset)

    def dataset_content_needs_grooming(self, file_name):
        """This function is called on an output dataset file after the content is initially generated."""
        return True

    def groom_dataset_content(self, file_name):
        # extract basename and folder of the current file whose content has to be groomed
        basename = os.path.basename(file_name)
        output_path = os.path.dirname(file_name)
        # extract archive if the file corresponds tos the ISA archive
        if basename == ISA_ARCHIVE_NAME:
            # list files before
            logger.debug("Files in %s before grooming...", output_path)
            for f in os.listdir(output_path):
                logger.debug("File: %s", f)
                logger.debug("Grooming dataset: %s", file_name)
            # perform extraction
            with open(file_name, 'rb') as stream:
                self._extract_archive(stream, output_path=output_path)
            # remove the original archive file
            os.remove(file_name)
            # list files after
            logger.debug("Files in %s after grooming...", output_path)
            for f in os.listdir(output_path):
                logger.debug("File: %s", f)

    def sniff(self, filename):
        """
        Try to detect whether the actual archive contains an ISA archive
        simply searching for the existence of an investigation file.

        :param filename: the name of the file containing the uploaded archive
        :return:
        """
        logger.debug("Checking if it is an ISA: %s", filename)
        # get the list of files within the compressed archive
        with open(filename, 'rb') as stream:
            files_list = self._list_archive_files(stream)
        # return True if the primary_filename exists
        return self.get_investigation_filename(files_list) is not None

    def set_meta(self, dataset, **kwd):
        logger.info("Setting metadata of ISA type: %r", dataset)
        logger.debug("ISA filename: %s", dataset.file_name)
        super(Isa, self).set_meta(dataset, **kwd)


class IsaTab(Isa):
    """ Class which implements the ISA-Tab datatype """
    file_ext = "isa-tab"

    def get_investigation_filename(self, files_list):
        """ Use the `investigation` file as primary file"""
        # TODO: check pattern to identify the investigation file
        res = []
        for f in files_list:
            logger.debug("Checking for matchings with file '%s'", f)
            match = re.findall(r"[i]_[\w]+\.txt", f, flags=re.IGNORECASE)
            if match:
                res.append(match[0])
                logger.debug("A match found: %r", match)
        logger.debug("List of matches: %r", res)
        if len(res) > 0:
            if len(res) == 1:
                return res[0]
            logger.error("More than one file match the pattern 'i_*.txt' to identify the investigation file")
        return None

    def validate(self, dataset):
        # TODO: implement a validator function
        logger.debug("Validating dataset....")
        return super(Isa, self).validate(dataset)


class IsaJson(Isa):
    """ Class which implements the ISA-JSON datatype """
    file_ext = "isa-json"

    def get_investigation_filename(self, files_list):
        """ Use the `investigation` file as primary file"""
        res = [f for f in files_list if f.endswith(".json")]
        if len(res) > 0:
            if len(res) == 1:
                return res[0]
            logger.error("More than one JSON file match the pattern to identify the investigation file")
        return None
