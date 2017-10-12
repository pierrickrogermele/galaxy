"""
ISA datatype

See http://isa-tools.org

"""

from __future__ import print_function

import re
import os
import sys
import shutil
import zipfile
import logging
import tarfile
import tempfile
import fnmatch

from io import BytesIO
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


class Logger(object):
    """ A simple logger which directly outputs messages to the stdout/stderr streams """

    def __init__(self):
        super(Logger, self).__init__()
        self._level = logging.INFO

    def set_level(self, level):
        self._level = level

    def info(self, message):
        print("INFO: %s" % message)

    def warn(self, message):
        print("WARN: %s" % message)

    def debug(self, message):
        if self._level == logging.DEBUG:
            print("DEBUG: %s" % message)

    def error(self, message):
        print("ERROR: %s" % message, file=sys.stderr)


# global logger
logger = Logger()
logger.set_level(logging.DEBUG)


class Isa(data.Data):
    """ Base class for implementing ISA datatypes """
    file_ext = "isa"
    composite_type = 'basic'  # 'auto_primary_file'
    allow_datatype_change = False
    is_binary = True

    # metadata.MetadataElement(name="base_name", desc="base name isa tab dataset",
    #                          default='Text',
    #                          readonly=True, set_in_upload=True)

    def __init__(self, **kwd):
        data.Data.__init__(self, **kwd)
        self.add_composite_file(ISA_ARCHIVE_NAME, is_binary=True, optional=True)

    def get_primary_filename(self, files_list):
        """ Return the investigation filename """
        raise NotImplementedError()

    def _extract_archive(self, stream):
        # extract the archive to a temp folder
        tmp_folder = tempfile.mkdtemp()
        # try to detect the type of the compressed archive
        a_type = self._detect_file_type(stream)
        # decompress the archive
        if a_type == "zip":
            self._extract_zip_archive(stream, tmp_folder)
        elif a_type == "gz":
            self._extract_tar_archive(stream, tmp_folder)
        else:
            raise Exception("Not supported archive format!!!")

        return tmp_folder

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

    def write_from_stream(self, dataset, stream):
        # Extract archive to a temporary folder
        tmp_folder = self._extract_archive(stream)
        # Copy all files of the uncompressed archive to their final destination
        tmp_files = [l for l in os.listdir(tmp_folder) if not (l.startswith(".") or l.startswith('__MACOSX'))]
        if len(tmp_files) > 0:
            first_path = os.path.join(tmp_folder, tmp_files[0])
            if os.path.isdir(first_path):
                shutil.move(os.path.join(tmp_folder, tmp_files[0]), dataset.files_path)
            else:
                shutil.move(tmp_folder, dataset.files_path)
        else:
            logger.error("No files found within the temp folder!!!!")
        # list all files
        for f in os.listdir(os.path.join(dataset.files_path)):
            logger.debug("Filename: %s" % f)
        # set the primary file
        primary_filename = self.get_primary_filename(os.listdir(dataset.files_path))
        if primary_filename is None:
            raise Exception("Unable to find the investigation file!!!")
        shutil.copy(os.path.join(dataset.files_path, primary_filename), dataset.file_name)
        logger.info("Primary file '%s' saved!" % primary_filename)

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
        logger.debug("Dataset type: %s, keys=%s, values=%s", type(dataset), dataset.keys(), dataset.values())

        rval = ['<html><head><title>Wiff Composite Dataset </title></head><p/>']
        rval.append('<div>This composite dataset is composed of the following files:<p/><ul>')

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

    def sniff(self, filename):
        """
        Try to detect whether the actual archive contains an ISA archive
        simply searching for the existence of an investigation file.

        :param filename: the name of the file containing the uploaded archive
        :return:
        """
        logger.info("Checking if it is an ISA: %s" % filename)
        # get the list of files within the compressed archive
        with open(filename, 'rb') as stream:
            files_list = self._list_archive_files(stream)
        # return True if the primary_filename exists
        return self.get_primary_filename(files_list) is not None

    def set_meta(self, dataset, **kwd):
        logger.debug("Setting metadata of ISA type: %s" % dataset.file_name)
        super(Isa, self).set_meta(dataset, **kwd)


class IsaTab(Isa):
    """ Class which implements the ISA-Tab datatype """
    file_ext = "isa-tab"

    def get_primary_filename(self, files_list):
        """ Use the `investigation` file as primary file"""
        # TODO: check pattern to identify the investigation file
        investigation_file_pattern = re.compile(fnmatch.translate("i_*.txt"))
        res = [l for l in files_list if investigation_file_pattern.match(l)]
        if len(res) > 0:
            if len(res) == 1:
                return res[0]
            logger.info("More than one file match the pattern '%s' "
                        "to identify the investigation file" % investigation_file_pattern)
        return None

    def validate(self, dataset):
        # TODO: implement a validator function
        logger.debug("Validating dataset....")
        return super(Isa, self).validate(dataset)


class IsaJson(Isa):
    """ Class which implements the ISA-JSON datatype """
    file_ext = "isa-json"

    def get_primary_filename(self, files_list):
        """ Use the `investigation` file as primary file"""
        res = [f for f in files_list if f.endswith(".json")]
        if len(res) > 0:
            if len(res) == 1:
                return res[0]
            logger.info("More than one JSON file match the pattern to identify the investigation file")
        return None
