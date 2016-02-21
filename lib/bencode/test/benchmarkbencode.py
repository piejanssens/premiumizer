#!/usr/bin/env python
# encoding: utf-8
"""
    Benchmark for the bencoding implementation in the 'official' Bittorrent library
"""

__author__ = "Tom Lazar (tom@tomster.org)"
__version__ = "$Revision: 0.1 $"
__date__ = "$Date: 2007/07/29 $"
__copyright__ = "Copyright (c) 2007 Tom Lazar"
__license__ = "Python"

ITERATIONS = 100

import sys
sys.path = ['.',] + sys.path #HACK: enables importing from `bencode`

import unittest
from bencode import bencode
from bencode import bdecode
from benchmarkdata import sampleValues, sampleEncodedValues

class Benchmark(unittest.TestCase):
    """ 
        A test to benchmark performance by repeatedly encoding and decoding sample data.
    """

    def testBencodeSampleValues(self):
        """ We encode the sample data """
        for iteration in range(0, ITERATIONS):
            for data in sampleValues:
                result = bencode(data)

    def testBdecodeSampleValues(self):
        """ We decode the sample data """
        for iteration in range(0, ITERATIONS):
            for data in sampleEncodedValues:
                result = bdecode(data)


if __name__ == "__main__":
	unittest.main()
