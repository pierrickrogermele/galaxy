"""
ISA datatype

See http://isa-tools.org

"""

from __future__ import print_function

import os
import sys
import glob
import logging
import tarfile
import tempfile
import shutil

from galaxy.datatypes import data
from galaxy.datatypes import metadata

# logger
logger = logging.getLogger("galaxy.jobs.runners.local")


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


class Isa(data.Data):
    """Tab delimited data in foo format"""
    file_ext = "isa"
    composite_type = 'basic'  # 'auto_primary_file'
    allow_datatype_change = False
    is_binary = True

    # metadata.MetadataElement(name="base_name", desc="base name isa tab dataset",
    #                          default='Text',
    #                          readonly=True, set_in_upload=True)

    def __init__(self, **kwd):
        data.Data.__init__(self, **kwd)

    def get_primary_filename(self, files_path):
        """ Use the `investigation` file as primary"""
        investigation_file_pattern = "i_*.txt"  # TODO: check pattern to identify the investigation file
        res = glob.glob(os.path.join(files_path, investigation_file_pattern))
        if len(res) > 0:
            if len(res) == 1:
                return res[0]
            print("More than one file match the pattern '%s' "
                  "to identify the investigation file" % investigation_file_pattern)
        return None

    def write_from_stream(self, dataset, stream):
        # TODO: check if the actual file is really a TAR archive
        # extract the archive to a temp folder
        tmp_folder = tempfile.mkdtemp()
        print("Using the custom uploader")
        with tarfile.open(fileobj=stream) as tar:
            for tarinfo in tar:
                print("File name: %s " % tarinfo.name)
            tar.extractall(path=tmp_folder)

        # FIXME: update this logic with a better implementation
        tmp_files = os.listdir(tmp_folder)
        if len(tmp_files) > 0:
            first_path = os.path.join(tmp_folder, tmp_files[0])
            if os.path.isdir(first_path):
                shutil.move(os.path.join(tmp_folder, tmp_files[0]), dataset.files_path)
            else:
                shutil.move(tmp_folder, dataset.files_path)
        else:
            print("No files found within the temp folder!!!!")

        primary_filename = self.get_primary_filename(dataset.files_path)
        if primary_filename is None:
            raise Exception("Unable to find the investigation file!!!")

        print("Primary (investigation) filename: %s" % primary_filename)
        shutil.copy(os.path.join(dataset.files_path, primary_filename), dataset.file_name)

        print("All files saved!!!")

    def generate_primary_file(self, dataset=None):
        print("Dataset type: %s, keys=%s, values=%s", type(dataset), dataset.keys(), dataset.values())

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
        logger.info("Checking if it is an ISA: %s" % filename)
        return True

    def validate(self, dataset):
        print("Validating dataset....")
        return super(Isa, self).validate(dataset)

    def set_meta(self, dataset, **kwd):
        print("Setting metadata of ISA type: %s" % dataset.file_name)
        # raise Error("Setting metadata of ISA type")
        super(Isa, self).set_meta(dataset, **kwd)
