"""
ISA datatype

See http://isa-tools.org

"""

#from __future__ import print_function
#
#import logging
#import os
#
#from galaxy.datatypes import metadata
#from . import data
#
#
#log = logging.getLogger(__name__)
#
#
#class Isa( data.Data ):
#    def __init__(self, **kwd):
#        data.Data.__init__(self, **kwd)
#
#    def sniff( self, filename ):
#        return os.path.isdir(filename) \
#           and os.path.isfile(os.path.join(filename, 'i_investigation.txt'))
