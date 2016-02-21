#!/usr/bin/env python
# encoding: utf-8
"""
    Tests for the bencode module
"""

__author__ = "Tom Lazar (tom@tomster.org)"
__version__ = "$Revision: 0.1 $"
__date__ = "$Date: 2007/07/29 $"
__copyright__ = "Copyright (c) 2007 Tom Lazar"
__license__ = "BitTorrent Open Source License"

from bencode import bencode
from bencode import bdecode
from bencode import BTFailure

import unittest

class KnownValues(unittest.TestCase):
    """ * example values partially taken from http://en.wikipedia.org/wiki/Bencode 
        * test case inspired by Mark Pilgrim's examples:
            http://diveintopython.org/unit_testing/romantest.html
    """
    knownValues = ( (0, 'i0e'),
                    (1, 'i1e'),
                    (10, 'i10e'),
                    (42, 'i42e'),
                    (-42, 'i-42e'),
                    (True, 'i1e'),
                    (False, 'i0e'),
                    ('spam', '4:spam'),
                    ('parrot sketch', '13:parrot sketch'),
                    (['parrot sketch', 42], 'l13:parrot sketchi42ee'),
                    ({
                        'foo' : 42,
                        'bar' : 'spam'
                    }, 'd3:bar4:spam3:fooi42ee'),
                  )

    def testBencodeKnownValues(self):
        """bencode should give known result with known input"""
        for plain, encoded in self.knownValues:
            result = bencode(plain)
            self.assertEqual(encoded, result)

    def testBdecodeKnownValues(self):
        """bdecode should give known result with known input"""
        for plain, encoded in self.knownValues:
            result = bdecode(encoded)
            self.assertEqual(plain, result)

    def testRoundtripEncoded(self):
        """ consecutive calls to bdecode and bencode should deliver the original
            data again
        """
        for plain, encoded in self.knownValues:
            result = bdecode(encoded)
            self.assertEqual(encoded, bencode(result))

    def testRoundtripDecoded(self):
        """ consecutive calls to bencode and bdecode should deliver the original
            data again
        """
        for plain, encoded in self.knownValues:
            result = bencode(plain)
            self.assertEqual(plain, bdecode(result))

class IllegaleValues(unittest.TestCase):
    """ handling of illegal values"""
    
    # TODO: BTL implementation currently chokes on this type of input
    # def testFloatRaisesIllegalForEncode(self):
    #     """ floats cannot be encoded. """
    #     self.assertRaises(BTFailure, bencode, 1.0)

    def testNonStringsRaiseIllegalInputForDecode(self):
        """ non-strings should raise an exception. """
        # TODO: BTL implementation currently chokes on this type of input
        # self.assertRaises(BTFailure, bdecode, 0)
        # self.assertRaises(BTFailure, bdecode, None)
        # self.assertRaises(BTFailure, bdecode, 1.0)
        self.assertRaises(BTFailure, bdecode, [1, 2])
        self.assertRaises(BTFailure, bdecode, {'foo' : 'bar'})

    def testRaiseIllegalInputForDecode(self):
        """illegally formatted strings should raise an exception when decoded."""
        self.assertRaises(BTFailure, bdecode, "foo")
        self.assertRaises(BTFailure, bdecode, "x:foo")
        self.assertRaises(BTFailure, bdecode, "x42e")

class Dictionaries(unittest.TestCase):
    """ handling of dictionaries """
    
    def testSortedKeysForDicts(self):
        """ the keys of a dictionary must be sorted before encoded. """
        dict = {'zoo' : 42, 'bar' : 'spam'}
        encoded_dict = bencode(dict)
        self.failUnless(encoded_dict.index('zoo') > encoded_dict.index('bar'))

    def testNestedDictionary(self):
        """ tests for handling of nested dicts"""
        dict = {'foo' : 42, 'bar' : {'sketch' : 'parrot', 'foobar' : 23}}
        encoded_dict = bencode(dict)
        self.assertEqual(encoded_dict, "d3:bard6:foobari23e6:sketch6:parrote3:fooi42ee")
        

if __name__ == "__main__":
	unittest.main()
