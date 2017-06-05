from distutils.core import setup
import py2exe
import numpy
setup(console=['lc3_logic.py'], requires=['PyQt4'])