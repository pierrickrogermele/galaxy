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
#from isatools import isatab ==> XXX ImportError: cannot import name zip_longest. Is isatools compatible with Python 2.7?
#from isatools import isajson
from json import dumps
from io import BytesIO
from cgi import escape
from galaxy import util
from galaxy.datatypes import data
from galaxy.datatypes import metadata
from galaxy.util.sanitize_html import sanitize_html

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

# max number of lines of the history peek
_MAX_LINES_HISTORY_PEEK = 11

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
    
    class InvestigationTab(object):
        investigation_file = None
        
        def __init__(self, investigation_file):
            self.investigation_file = investigation_file
        
    class InvestigationJson(object):
        json_file = None
        
        def __init__(self, json_file):
            self.json_file = json_file
        
    """ Base class for implementing ISA datatypes """
    file_ext = "isa"
    composite_type = 'auto_primary_file'
    allow_datatype_change = False
    is_binary = True
    investigation = None
    main_file = None

    # metadata.MetadataElement(name="base_name", desc="base name isa tab dataset",
    #                          default='Text',
    #                          readonly=True, set_in_upload=True)

    def __init__(self, **kwd):
        data.Data.__init__(self, **kwd)
        self.add_composite_file(ISA_ARCHIVE_NAME, is_binary=True, optional=True)

    def _init_investigation(self, dataset):
        """Create a contained instance specific to the exact ISA type (Tab or Json)."""
        
        if self.investigation is None:
            
            # Detect type
            if dataset and dataset.dataset and dataset.dataset.extra_files_path and os.path.exists(dataset.dataset.extra_files_path):
                
                # Get ISA archive older
                isa_folder = dataset.dataset.extra_files_path
                
                # Test if it is an ISA-Tab
                investigation_file = self._find_isatab_investigation_filename(os.listdir(isa_folder))
                if investigation_file is not None:
                    self.main_file = investigation_file
                    self.investigation = InvestigationTab(investigation_file)
                
                # Test if it is an ISA-Json
                if self.investigation is None:
                    json_file = self._find_isajson_json_filename(os.listdir(isa_folder))
                    if json_file is not None:
                        self.main_file = json_file
                        self.investigation = InvestigationJson(json_file)
                    
                # Unable to determine ISA archive type
                if self.investigation is None:
                    logger.warning('Unknown ISA archive type. Cannot determine if it is ISA-Tab or ISA-Json.')
            else:
                logger.warning('Unvalid dataset object, or no extra files path found for this dataset.')
        
    def get_main_file(self, dataset):
        """Get main file of ISA archive. Either the i_investigation.txt file for an ISA-Tab or the JSON file for an ISA-Json."""
        
        # Initialize investigation
        self._init_investigation(dataset)
        
        file = None
        
        # Search for main file
            
            
        return file
        
    def get_investigation_filename(self, files_list):
        if self.investigation is None:
            investigation_filename = self._find_isatab_investigation_filename(files_list)
            if investigation_filename:
                self.investigation = IsaTab
            else:
                investigation_filename = self._find_isajson_json_filename(files_list)
                self.investigation = IsaJson
            return investigation_filename
        else:
            return self._find_isatab_investigation_filename(files_list) \
                if self.investigation == IsaTab else self._find_isajson_json_filename(files_list)

    def _find_isatab_investigation_filename(self, files_list):
        """Find the investigation file of an ISA-Tab."""
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

    def _find_isajson_json_filename(self, files_list):
        """Find the JSON file of an ISA-Json."""
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

    def _detect_file_type(self, stream):
        """
        Try to detect the type of the dataset archive.

        :param dataset:
        :return: _ZIP or _TAR if the file type is detected; None otherwise.
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

    def set_peek(self, dataset, is_multi_byte=False):
        """Set the peek and blurb text"""
        
        self._init_investigation(dataset)
        
        if self.main_file is None:
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

    def display_peek(self, dataset):
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
                out.append('<tr><td>%s</td></tr>' % escape(util.unicodify(line, 'utf-8')))
            out.append('</table>')
            out = "".join(out)
        except Exception as exc:
            out = "Can't create peek %s" % str(exc)
        return out

    def _extract_zip_archive(self, stream, target_path):
        logger.debug("Isa::_extract_zip_archive")
        logger.debug("Decompressing the ZIP archive")
        temp_folder = tempfile.mkdtemp()
        data = BytesIO(stream.read())
        zip_ref = zipfile.ZipFile(data)
        zip_ref.extractall(path=temp_folder)
        self._move_to_target_path(temp_folder, target_path)

    def _extract_tar_archive(self, stream, target_path):
        logger.debug("Isa::_extract_tar_archive")
        # extract the TAR archive
        logger.debug("Decompressing the TAR archive")
        temp_folder = tempfile.mkdtemp()
        with tarfile.open(fileobj=stream) as tar:
            tar.extractall(path=temp_folder)
        self._move_to_target_path(temp_folder, target_path)

    def _move_to_target_path(self, temp_folder, target_path, delete_temp_folder=True):
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

    def generate_primary_file(self, dataset=None):
        logger.debug("Isa::generate_primary_file")
        if dataset:
            logger.debug("Dataset: %r", dataset)
            logger.debug("Isa::generate_primary_file " + str(dataset))
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
            logger.debug(" ".join(rval))
            return "\n".join(rval)
        return "<div>No dataset available</div>"

    def dataset_content_needs_grooming(self, file_name):
        """This function is called on an output dataset file after the content is initially generated."""
        return True

    def groom_dataset_content(self, file_name):
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

    def sniff(self, filename):
        """Try to detect whether the actual archive contains an ISA archive simply searching for the existence of an investigation file."""
        logger.debug("Checking if %s is an ISA.", filename)
        
        # Get the list of files within the compressed archive
        with open(filename, 'rb') as stream:
            files_list = self._list_archive_files(stream)
            if self._find_isatab_investigation_filename(files_list) is not None or self._find_isajson_json_filename(files_list) is not None:
                return True

        return False

    def set_meta(self, dataset, **kwd):
        logger.info("Setting metadata of ISA type: %r", dataset)
        logger.debug("ISA filename: %s", dataset.file_name)
        super(Isa, self).set_meta(dataset, **kwd)

    def get_isajson_json_file(self, dataset):
        
        file = None
        
        if dataset.dataset is not None:
            # Open ISA folder
            isa_folder = dataset.dataset.extra_files_path
            if os.path.exists(isa_folder):
                json_files = glob.glob(os.path.join(isa_folder, '*.json'))
                if len(json_files) >= 1:
                    file = json_files[0]

        return file

    def get_isatab_investigation_file(self, dataset):
        
        file = None
        
        if dataset.dataset is not None:
            # Open ISA folder
            isa_folder = dataset.dataset.extra_files_path
            if os.path.exists(isa_folder):
                investigation_files = glob.glob(os.path.join(isa_folder, 'i_*.txt'))
                if len(investigation_files) >= 1:
                    file = investigation_files[0]

        return file
        
    def is_isatab(self, dataset):
        return self.get_isatab_investigation_file(dataset) is not None
        
    def is_isajson(self, dataset):
        return self.get_isajson_json_file(dataset) is not None
        
    def make_info_page_from_isatab(self, dataset):
        
        html = None
        
        # Read investigation file "by hand". TODO Use isatools for that
        with open(self.get_isatab_investigation_file(dataset), 'rb') as csvfile:
            investigation_reader = csv.reader(csvfile, delimiter = "\t")
            html = '<html><body>'
            current_section = None
            for row in investigation_reader:
                if len(row) == 1:
                    current_section = row[0]
                elif current_section == 'STUDY':
                    if row[0] == 'Study Identifier':
                        html += '<h1>%s</h1>' % row[1]
                    if row[0] == 'Study Title':
                        html += '<h2>%s</h2>' % row[1]
                    if row[0] == 'Study Description':
                        html += '<p>%s</p>' % row[1]
                    if row[0] == 'Study Submission Date':
                        html += '<p>Submitted the %s</p>' % row[1]
                    if row[0] == 'Study Public Release Date':
                        html += '<p>Released on %s</p>' % row[1]
                        
            html += '</body></html>'
            
        return html
        
    def make_info_page_from_isajson(self, dataset):
        
        html = None
        
        filename = self.get_isajson_json_file(dataset) 
        logger.debug("Isa::make_info_page_from_isajson Filename: %r", filename)
        fp = open(filename)
        logger.debug("Isa::make_info_page_from_isajson fp: %r", fp)
        json_isa = json.load(fp)
        html = '<html><body>'
        study = json_isa['studies'][0]
        if 'identifier' in study:
            html += '<h1>%s</h1>' % study['identifier']
        if 'title' in study:
            html += '<h2>%s</h2>' % study['title']
        if 'description' in study:
            html += '<p>%s</p>' % study['description']
        if 'submissionDate' in study:
            html += '<p>Submitted the %s</p>' % study['submissionDate']
        if 'publicReleaseDate' in study:
            html += '<p>Released on %s</p>' % study['publicReleaseDate']
        html += '</body></html>'
            
        return html
        
    def display_data(self, trans, dataset, preview=False, filename=None, to_ext=None, offset=None, ck_size=None, **kwd):
        
        logger.debug('Isa::display_data 01')
        html = None
        if dataset is not None:
            if self.is_isatab(dataset):
                html = self.make_info_page_from_isatab(dataset)
            elif self.is_isajson(dataset):
                html = self.make_info_page_from_isajson(dataset)
                
        if html is None:
            html = '<html><header><title>Error while reading ISA archive.</title></header><body><h1>An error occured while reading content of ISA archive.</h1></body></html>'
        logger.debug(html)
        mime = 'text/html'
        self._clean_and_set_mime_type(trans, mime)
        return sanitize_html(html).encode('utf-8')

class IsaTab(Isa):
    """ Class which implements the ISA-Tab datatype """
    file_ext = "isa-tab"

    def get_investigation_filename(self, files_list):
        logger.debug("IsaTab::get_investigation_filename")
        return self._find_isatab_investigation_filename(files_list)

    def validate(self, dataset):
        logger.debug("IsaTab::validate")
        # TODO: implement a validator function
        logger.debug("Validating dataset....")
        return super(Isa, self).validate(dataset)


class IsaJson(Isa):
    """ Class which implements the ISA-JSON datatype """
    file_ext = "isa-json"

    def get_investigation_filename(self, files_list):
        logger.debug("IsaJson::get_investigation_filename")
        return self._find_isajson_json_filename(files_list)
