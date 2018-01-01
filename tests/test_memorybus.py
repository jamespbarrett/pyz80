import unittest
from pyz80.memorybus import *
from unittest import mock

class TestMemoryBus(unittest.TestCase):
    @mock.patch("pyz80.memorybus.open")
    def setUp(self, _open):
        _open.return_value.__enter__.return_value = _open.return_value
        _open.return_value.read.return_value = range(0,256)
        self.UUT = MemoryBus(mappings=[(0x00, 0x4000, FileROM("tmp.rom")),
                                       (0x4000, 0x4000, Peripheral())])
        _open.assert_called_once_with("tmp.rom", "rb")
        _open.return_value.read.assert_called_once_with()

    def test_init(self):
        pass

    def test_read(self):
        for n in range(0,0x10000):
            if n < 0x4000:
                self.assertEqual(n%0x100, self.UUT.read(n))
            elif n < 0x8000:
                self.assertEqual(0xFF, self.UUT.read(n))
            else:
                self.assertEqual(0x00, self.UUT.read(n))

    def test_write(self):
        for n in range(0,0x10000):
            self.UUT.write(n, 0xFF - (n%0x100))

        for n in range(0,0x10000):
            if n < 0x4000:
                self.assertEqual(n%0x100, self.UUT.read(n))
            elif n < 0x8000:
                self.assertEqual(0xFF, self.UUT.read(n))
            else:
                self.assertEqual(0xFF - (n%0x100), self.UUT.read(n))

    def test_memory_map(self):
        outp = self.UUT.memory_map(granularity=0x2000)
        self.assertEqual(outp,
                             """\
0x0000 +-----------------------------------------------------------------------+
       | ROM ( tmp.rom )                                                       |
       |                                                                       |
0x4000 +-----------------------------------------------------------------------+
       | Generic Peripheral                                                    |
       |                                                                       |
0x8000 +-----------------------------------------------------------------------+
       | RAM                                                                   |
       |                                                                       |
       |                                                                       |
       |                                                                       |
       +-----------------------------------------------------------------------+""")
