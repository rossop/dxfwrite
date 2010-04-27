#!/usr/bin/env python
#coding:utf-8
# Author:  mozman
# Purpose: test drawing
# Created: 27.04.2010
# Copyright (C) 2010, Manfred Moitzi
# License: GPLv3

import os
import unittest

from dxfwrite import DXFEngine as dxf

class TestDrawing(unittest.TestCase):
    def test_drawing(self):
        dwg = dxf.drawing('test.dxf')
        res1 = dwg.__dxf__()
        self.assertTrue(isinstance(res1, basestring))

if __name__=='__main__':
    unittest.main()