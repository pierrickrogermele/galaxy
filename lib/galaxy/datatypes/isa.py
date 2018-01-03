"""
ISA datatype

See http://isa-tools.org

"""

from __future__ import print_function

import re
import os
import sys
import glob
import json
import shutil
import zipfile
import logging
import tarfile
import tempfile
import csv
from isatools import isatab
from isatools import isajson
from json import dumps
from io import BytesIO
from cgi import escape
from galaxy import util
from galaxy.datatypes import data
from galaxy.datatypes import metadata
from galaxy.util.sanitize_html import sanitize_html

# Function for opening correctly a CSV file for csv.reader() for both Python 2 and 3
def utf8_text_file_open(path):
    if sys.version_info[0] < 3: 
        fp = open(path, 'rb')
    else:
        fp = open(path, 'r', newline='', encoding='utf8')
    return fp

# The name of the ISA archive (compressed file) as saved inside Galaxy
ISA_ARCHIVE_NAME = "archive"

# Archives types
_FILE_TYPE_PREFIX = {
    "\x1f\x8b\x08": "gz",
    "\x42\x5a\x68": "bz2",
    "\x50\x4b\x03\x04": "zip"
}
_MAX_LEN_FILE_TYPE_PREFIX = max(len(x) for x in _FILE_TYPE_PREFIX)
_FILE_TYPE_REGEX = re.compile("(%s)" % "|".join(map(re.escape, _FILE_TYPE_PREFIX.keys())))

# Set max number of lines of the history peek
_MAX_LINES_HISTORY_PEEK = 11

# Configure logger
logger = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(name)s %(levelname)s %(asctime)s %(message)s")
ch.setFormatter(formatter)
logger.handlers = []
logger.propagate = False
logger.addHandler(ch)
logger.setLevel(logging.ERROR)


# ISA class {{{1
################################################################

class Isa(data.Data):
    """ Base class for implementing ISA datatypes """
    file_ext = "isa"
    composite_type = 'auto_primary_file'
    allow_datatype_change = False
    is_binary = True

    # Add static metadata responsible for naming dataset instances
#    metadata.MetadataElement(name="base_name", desc="Generic dataset name", default="isa dataset",
#                             readonly=True, set_in_upload=True)

    @classmethod
    def _make_investigation(cls, filename):
        
        # Parse JSON file
        if filename[-5:].lower() == '.json':
            fp = utf8_text_file_open(filename)
            isa = isajson.load(fp)
            return isa
        
        # Parse ISA-Tab investigation file
        parser = isatab.InvestigationParser()
        fp = utf8_text_file_open(filename)
        parser.parse(fp)
        isa = parser.isa
        return isa

    # Constructor {{{2
    ################################################################

    def __init__(self, **kwd):
        data.Data.__init__(self, **kwd)

        print('---------------------------- Isa::__init__ 01')
        print('KWD %r' % kwd)
        # Add the archive file as the only composite file
        self.add_composite_file(ISA_ARCHIVE_NAME, is_binary=True, optional=True)

    # Get main file {{{2
    ################################################################

    @classmethod
    def _get_main_file(cls, dataset):
        """Get the main file of the ISA type: either the ISA-Tab investigation file, or the ISA-Json JSON file."""

        main_file = None
        print('---------------------------- Isa::_get_main_file 01')
        print(type(dataset))
        if hasattr(dataset, "dataset"):
            print('---------------------------- Isa::_get_main_file 02')
            print(type(dataset.dataset))
            for attr, value in dataset.dataset.__dict__.iteritems():
                print(str(attr) + ' : ' + str(value))
            print('---------------------------- Isa::_get_main_file 03')
                
        # Detect type
        isa_folder = None
        if dataset:
            print('---------------------------- Isa::_get_main_file 02')
#            for attr, value in dataset.__dict__.iteritems():
#                print(str(attr) + ' : ' + str(value))
            print('---------------------------- Isa::_get_main_file 02.0')

#            print('dataset filename %r' % dataset.get_file_name())
#            with open(dataset.get_file_name(), 'rb') as stream:
#                a_type = self._detect_file_type(stream, output_path=output_path)
#                print('File type: ' + str(a_type))
            #print('dataset extra files path %r' % dataset.get_extra_files_path())
            print('---------------------------- Isa::_get_main_file 02.1')
            if hasattr(dataset, "extra_files_path"):
                print('---------------------------- Isa::_get_main_file 03')
                isa_folder = dataset.extra_files_path
            if isa_folder is None and hasattr(dataset, "dataset") and hasattr(dataset.dataset, "extra_files_path"):
                print('---------------------------- Isa::_get_main_file 04')
                isa_folder = dataset.dataset.extra_files_path
            print('---------------------------- Isa::_get_main_file 02.2')
            print(isa_folder)

        print('---------------------------- Isa::_get_main_file 05')
        print(isa_folder)
        if isa_folder is None:
            print('---------------------------- Isa::_get_main_file 06')
            logger.warning('Unvalid dataset object, or no extra files path found for this dataset.')
        elif not os.path.exists(isa_folder):
            print('---------------------------- Isa::_get_main_file 07')
            logger.warning("The extra files path '%s' doesn't exit", isa_folder)
        else:
            print('---------------------------- Isa::_get_main_file 08')
            logger.debug("The extra files folder is: %s", isa_folder)

            # Get ISA archive older
            isa_files = os.listdir(isa_folder)

            # Try to find an ISA-Tab investigation file
            main_file = cls._find_isatab_investigation_filename(isa_files)

            # Try to find an ISA-Json JSON file
            if main_file is None:
                main_file = cls._find_isajson_json_filename(isa_files)

            # Make full path
            if main_file is not None:
                main_file = os.path.join(isa_folder, main_file)

            if main_file is None:
                logger.warning(
                    'Unknown ISA archive type. Cannot determine if it is ISA-Tab or ISA-Json. Cannot find a main file.')

        return main_file

    # Get investigation {{{2
    ################################################################

    @classmethod
    def _get_investigation(cls, dataset):
        """Create a contained instance specific to the exact ISA type (Tab or Json).
           We will use it to parse and access information from the archive."""

        investigation = None
        main_file = cls._get_main_file(dataset)
        print('---------------------------- Isa::_get_investigation')
        print(main_file)
        if main_file is not None:
            investigation = Isa._make_investigation(main_file)

        return investigation

    # Find ISA-Tab investigation filename {{{2
    ################################################################

    @classmethod
    def _find_isatab_investigation_filename(cls, files_list):
        """Find the investigation file inside the ISA-Tab archive."""
        logger.debug("Finding investigation filename assuming an ISA-Tab dataset...")
        res = []
        for f in files_list:
            logger.debug("Checking for matchings with file '%s'", f)
            match = re.findall(r"^[i]_[\w]+\.txt", f, flags=re.IGNORECASE)
            if match:
                res.append(match[0])
                logger.debug("A match found: %r", match)
        logger.debug("List of matches: %r", res)
        if len(res) > 0:
            if len(res) == 1:
                investigation_filename = res[0]
                logger.debug("Found primary file: %s", investigation_filename)
                return investigation_filename
            logger.error("More than one file match the pattern 'i_*.txt' to identify the investigation file")
        return None

    # Find ISA-Json JSON filename {{{2
    ################################################################

    @classmethod
    def _find_isajson_json_filename(cls, files_list):
        """Find the JSON file inside the ISA-Json archive."""
        logger.debug("Finding investigation filename assuming an ISA-JSON dataset...")
        res = [f for f in files_list if f.endswith(".json")]
        logger.debug("List of matches: %r", res)
        if len(res) > 0:
            if len(res) == 1:
                investigation_filename = res[0]
                logger.debug("Found primary file: %s", investigation_filename)
                return investigation_filename
            logger.error("More than one JSON file match the pattern to identify the investigation file")
        return None

    # Extract archive {{{2
    ################################################################

    def _extract_archive(self, stream, output_path=None):
        """Extract files from archive and put them is predefined folder."""

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

    # Extract ZIP archive {{{2
    ################################################################

    def _extract_zip_archive(self, stream, target_path):
        """Extract files from a ZIP archive."""

        logger.debug("Isa::_extract_zip_archive")
        logger.debug("Decompressing the ZIP archive")
        temp_folder = tempfile.mkdtemp()
        data = BytesIO(stream.read())
        zip_ref = zipfile.ZipFile(data)
        zip_ref.extractall(path=temp_folder)
        self._move_to_target_path(temp_folder, target_path)

    # Extract TAR archive {{{2
    ################################################################

    def _extract_tar_archive(self, stream, target_path):
        """Extract files from a TAR archive."""
        
        logger.debug("Isa::_extract_tar_archive")
        # extract the TAR archive
        logger.debug("Decompressing the TAR archive")
        temp_folder = tempfile.mkdtemp()
        with tarfile.open(fileobj=stream) as tar:
            tar.extractall(path=temp_folder)
        self._move_to_target_path(temp_folder, target_path)

    # Move to target path {{{2
    ################################################################

    def _move_to_target_path(self, temp_folder, target_path, delete_temp_folder=True):
        """Move extracted files to the destination folder imposed by Galaxy."""

        logger.debug("Isa::_move_to_target_path")
        # find the root folder containing the dataset
        tmp_subfolders = [f for f in os.listdir(temp_folder) if
                          not f.startswith(".") and f not in (ISA_ARCHIVE_NAME, "__MACOSX")]
        logger.debug("Files within the temp folder: %r", tmp_subfolders)
        # move files contained within the root dataset folder to their target path
        root_folder = os.path.join(temp_folder, tmp_subfolders[0])
        if len(tmp_subfolders) == 1 and os.path.isdir(root_folder):
            # move the root dataset folder to its final destination and clean the temp data
            for f in os.listdir(root_folder):
                shutil.move(os.path.join(root_folder, f), target_path)
        elif len(tmp_subfolders) > 1:
            for f in tmp_subfolders:
                shutil.move(os.path.join(temp_folder, f), target_path)
        # clean temp data if required
        if delete_temp_folder:
            shutil.rmtree(temp_folder)

    # List archive files {{{2
    ################################################################

    def _list_archive_files(self, stream):
        """List files contained inside the ISA archive."""

        logger.debug("Isa::_list_archive_files")
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

    # Detect file type {{{2
    ################################################################

    def _detect_file_type(self, stream):
        """
        Try to detect the type of the ISA archive: is it ZIP, or GUNZIP?

        :return: "zip" or "gz" if the file type is detected; None otherwise.
        """
        logger.debug("Isa::_detect_file_type")
        file_type = None
        file_start = stream.read(_MAX_LEN_FILE_TYPE_PREFIX)
        stream.seek(0)  # reset the stream
        matched_prefix = _FILE_TYPE_REGEX.match(file_start)
        if matched_prefix:
            file_type = _FILE_TYPE_PREFIX[matched_prefix.string[matched_prefix.start():matched_prefix.end()]]
        logger.debug("Detected file type: %s (prefix: %r)" % (file_type, file_start))

        return file_type

    # Set peek {{{2
    ################################################################

    def set_peek(self, dataset, is_multi_byte=False):
        """Set the peek and blurb text. Get first lines of the main file and set it as the peek."""

        main_file = self._get_main_file(dataset)

        if main_file is None:
            raise RuntimeError("Unable to find the main file within the 'files_path' folder")

        # Read first lines of main file
        with open(main_file, "r") as f:
            data = []
            for line in f:
                if len(data) < _MAX_LINES_HISTORY_PEEK:
                    data.append(line)
                else:
                    break
            if not dataset.dataset.purged and data:
                dataset.peek = json.dumps({"data": data})
                dataset.blurb = 'data'
            else:
                dataset.peek = 'file does not exist'
                dataset.blurb = 'file purged from disk'

    # Display peek {{{2
    ################################################################

    def display_peek(self, dataset):
        """Create the HTML table used for displaying peek, from the peek text found by set_peek() method."""

        out = ['<table cellspacing="0" cellpadding="3">']
        try:
            if not dataset.peek:
                dataset.set_peek()
            json_data = json.loads(dataset.peek)
            for line in json_data["data"]:
                line = line.strip()
                if not line:
                    continue
                out.append('<tr><td>%s</td></tr>' % escape(util.unicodify(line, 'utf-8')))
            out.append('</table>')
            out = "".join(out)
        except Exception as exc:
            out = "Can't create peek %s" % str(exc)
        return out

    # Generate primary file {{{2
    ################################################################

    def generate_primary_file(self, dataset=None):
        """Generate the primary file. It is an HTML file containing description of the composite dataset
           as well as a list of the composite files that it contains."""
        logger.debug("Isa::generate_primary_file")
        if dataset:
            logger.debug("Dataset: %r", dataset)
            logger.debug("Isa::generate_primary_file " + str(dataset))
            rval = ['<html><head><title>ISA Dataset </title></head><p/>']
            if hasattr(dataset, "extra_files_path"):
                rval.append('<div>ISA Dataset composed of the following files:<p/><ul>')
                for cmp_file in os.listdir(dataset.extra_files_path):
                    opt_text = ''
                    rval.append('<li><a href="%s" type="text/plain">%s</a>%s</li>' % (cmp_file, cmp_file, opt_text))
                rval.append('</ul></div></html>')
            else:
                rval.append('<div>ISA Dataset is empty!<p/><ul>')
            logger.debug(" ".join(rval))
            return "\n".join(rval)
        return "<div>No dataset available</div>"

    # Dataset content needs grooming {{{2
    ################################################################

    def dataset_content_needs_grooming(self, file_name):
        """This function is called on an output dataset file after the content is initially generated."""
        return True

    # Groom dataset content {{{2
    ################################################################

    def groom_dataset_content(self, file_name):
        """This method is called by Galaxy to extract files contained in a composite data type."""
        # XXX Is the right place to extract files? Should this step not be a cleaning step instead?
        # Could extracting be done earlier and composite files declared as files contained inside the archive
        # instead of the archive itself?

        # extract basename and folder of the current file whose content has to be groomed
        basename = os.path.basename(file_name)
        output_path = os.path.dirname(file_name)
        # extract archive if the file corresponds to the ISA archive
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

    # Sniff {{{2
    ################################################################

    def sniff(self, filename):
        """Try to detect whether the actual archive contains an ISA archive simply searching for the existence
           of an investigation file."""

        # XXX Remove this method? This method seems to be unused for a composite data type.
        # Inside the uploader tool, only the types of normal datasets can be detected automatically,
        # the types of composite datasets are always specified manually.

        logger.debug("Checking if %s is an ISA.", filename)

        # Get the list of files within the compressed archive
        with open(filename, 'rb') as stream:
            files_list = self._list_archive_files(stream)
            if self._find_isatab_investigation_filename(files_list) is not None \
                    or self._find_isajson_json_filename(files_list) is not None:
                return True

        return False

    def init_meta( self, dataset, copy_from=None ):
        super(Isa, self).init_meta(dataset, copy_from)
        print('---------------------------- Isa::init_meta 01')
        print(type(dataset))
        print(dataset)
        print(dataset.name)
        print('---------------------------- Isa::init_meta 01.1')
        for attr, value in dataset.__dict__.iteritems():
            print(str(attr) + ' : ' + str(value))
        print('---------------------------- Isa::init_meta 02')
        for attr, value in self.__dict__.iteritems():
            print(str(attr) + ' : ' + str(value))
        print('---------------------------- Isa::init_meta 03')
        print(self.composite_files)
        for attr, value in self.composite_files.__dict__.iteritems():
            print(str(attr) + ' : ' + str(value))
        print('---------------------------- Isa::init_meta 04')
        print(self.composite_files['archive'])
        for attr, value in self.composite_files['archive'].__dict__.iteritems():
            print(str(attr) + ' : ' + str(value))
        self._set_dataset_name(dataset)
        print('---------------------------- Isa::init_meta 10')
        print(dataset.name)
        
    # Set meta {{{2
    ################################################################

#    def set_meta(self, dataset, **kwd):
    def set_meta( self, dataset, overwrite=True, **kwd ):
        """Set meta data information."""
        print('---------------------------- Isa::set_meta')
        print(dataset)
        print(type(dataset))
        print(dataset.name)
        super(Isa, self).set_meta(dataset, **kwd)
        self._set_dataset_name(dataset)
        return True

    # Set dataset name {{{2
    ################################################################
    
    def _set_dataset_name(self, dataset):
        print('---------------------------- Isa::_set_dataset_name 01')
        print(dataset)
#        for attr, value in dataset.__dict__.iteritems():
#            print(str(attr) + ' : ' + str(value))
        print('---------------------------- Isa::_set_dataset_name 02')
        if dataset.dataset:
            print(dataset.dataset)
            for attr, value in dataset.dataset.__dict__.iteritems():
                print(str(attr) + ' : ' + str(value))
        investigation = self._get_investigation(dataset)
        if investigation is not None:
            print('---------------------------- Isa::_set_dataset_name 10')
            dataset.name = investigation.identifier
        else:
            dataset.name = 'ISA DATASET'
        print('---------------------------- Isa::_set_dataset_name 20')
        print(type(dataset))
        print(dataset.name)

    def display_name(self, dataset):
        """Returns formatted html of dataset name"""
        self._set_dataset_name(dataset)
        print('-------------------------------- Isa::display_name 01')
        print(type(dataset))
        print(dataset.name)
        print('-------------------------------- Isa::display_name 02')
        super(Isa, self).display_name(dataset)
        
    # Display data {{{2
    ################################################################


    def display_data(self, trans, dataset, preview=False, filename=None, to_ext=None, offset=None, ck_size=None, **kwd):
        """Downloads the ISA dataset if `preview` is `False`;
           if `preview` is `True`, it returns a preview of the ISA dataset as a HTML page.
           The preview is triggered when user clicks on the eye icon of the composite dataset."""

        print('-------------------------------- Isa::display_data 01')
        print(dataset.name)
        self._set_dataset_name(dataset)
        print(dataset.name)
        print('-------------------------------- Isa::display_data 02')
        # if it is not required a preview use the default behaviour of `display_data`
        if not preview:
            logger.debug("Use the default `display_data` behaviour")
            return super(Isa, self).display_data(trans, dataset, preview, filename, to_ext, **kwd)

        # prepare the preview of the ISA dataset
        investigation = self._get_investigation(dataset)
        logger.debug('---------------------------- Isa::display_data Investigation %r', investigation)
        if investigation is None:
            html = '<html><header><title>Error while reading ISA archive.</title></header>' \
                   '<body><h1>An error occured while reading content of ISA archive.</h1></body></html>'
        else:
            html = '<html><body>'
            html += '<h1>{0} {1}</h1>'.format(investigation.title, investigation.identifier)
            logger.debug('---------------------------- Isa::display_data Investigation title %r', investigation.title)
            logger.debug('---------------------------- Isa::display_data %s studies', len(investigation.studies))
            for study in investigation.studies:
                html += '<h2>Study %s</h2>' % study.identifier
                html += '<h3>%s</h3>' % study.title
                html += '<p>%s</p>' % study.description
                html += '<p>Submitted the %s</p>' % study.submission_date
                html += '<p>Released on %s</p>' % study.public_release_date
            html += '</body></html>'

        # Set mime type
        mime = 'text/html'
        self._clean_and_set_mime_type(trans, mime)

        return sanitize_html(html).encode('utf-8')
