import unittest
from pyz80.registers import *
import mock
import itertools

class TestRegisterFile(unittest.TestCase):
    def test_init(self):
        reg = RegisterFile()
        self.assertEqual(reg.A, 0x00)
        self.assertEqual(reg.B, 0x00)
        self.assertEqual(reg.C, 0x00)
        self.assertEqual(reg.D, 0x00)
        self.assertEqual(reg.E, 0x00)
        self.assertEqual(reg.F, 0x00)
        self.assertEqual(reg.H, 0x00)
        self.assertEqual(reg.L, 0x00)
        self.assertEqual(reg.I, 0x00)
        self.assertEqual(reg.R, 0x00)
        self.assertEqual(reg.AF, 0x0000)
        self.assertEqual(reg.BC, 0x0000)
        self.assertEqual(reg.DE, 0x0000)
        self.assertEqual(reg.HL, 0x0000)
        self.assertEqual(reg.IX, 0x0000)
        self.assertEqual(reg.IY, 0x0000)
        self.assertEqual(reg.PC, 0x0000)
        self.assertEqual(reg.SP, 0x0000)

    def set8bit(self, name, value = 0xFF):
        reg = RegisterFile()
        setattr(reg, name, value)

        for r in ("A", "B", "C", "D", "E", "F", "H", "L", "I", "R", "IXL", "IXH", "IYH", "IYL"):
            if name == r:
                self.assertEqual(getattr(reg, r), value, msg="After setting register %s a check of register %s gives 0x%02X (expected 0x%02X)" % (name, r, getattr(reg, r), value))
            else:
                self.assertEqual(getattr(reg, r), 0x00, msg="After setting register %s a check of register %s gives 0x%02X (expected 0x00)" % (name, r, getattr(reg, r)))

        for r in ("AF", "BC", "DE", "HL"):
            if name == r[0]:
                self.assertEqual(getattr(reg, r), value << 8, msg="After setting register %s a check of register %s gives 0x%04X (expected 0x%04X)" % (name, r, getattr(reg, r), value << 8))
            elif name == r[1]:
                self.assertEqual(getattr(reg, r), value, msg="After setting register %s a check of register %s gives 0x%04X (expected 0x%04X)" % (name, r, getattr(reg, r), value))
            else:
                self.assertEqual(getattr(reg, r), 0x00, msg="After setting register %s a check of register %s gives 0x%04x (expected 0x0000)" % (name, r, getattr(reg, r)))

        for r in ("IX", "IY"):
            if name == r + "H":
                self.assertEqual(getattr(reg, r), value << 8, msg="After setting register %s a check of register %s gives 0x%04X (expected 0x%04X)" % (name, r, getattr(reg, r), value << 8))
            elif name == r + "L":
                self.assertEqual(getattr(reg, r), value, msg="After setting register %s a check of register %s gives 0x%04X (expected 0x%04X)" % (name, r, getattr(reg, r), value))
            else:
                self.assertEqual(getattr(reg, r), 0x00, msg="After setting register %s a check of register %s gives 0x%04X (expected 0x0000)" % (name, r, getattr(reg, r)))

        self.assertEqual(reg.PC, 0x0000, msg="After setting register %s a check of register PC gives 0x%04X (expected 0x0000)" % (name, reg.PC))
        self.assertEqual(reg.SP, 0x0000, msg="After setting register %s a check of register SP gives 0x%04X (expected 0x0000)" % (name, reg.SP))

    def test_set_8bit(self):
        for r in ("A", "B", "C", "D", "E", "F", "H", "L", "I", "R", "IXL", "IXH", "IYH", "IYL"):
            self.set8bit(r)

    def set16bit(self, name, value = 0x55AA):
        reg = RegisterFile()
        setattr(reg, name, value)

        for r in ("A", "B", "C", "D", "E", "F", "H", "L", "IXL", "IXH", "IYH", "IYL"):
            if name[0] == r or name + "H" == r:
                self.assertEqual(getattr(reg, r), (value >> 8)&0xFF, msg="After setting register %s a check of register %s gives 0x%02X (expected 0x%02X)" % (name, r, getattr(reg, r), (value >> 8)&0xFF))
            elif (name[1] == r and name != "PC") or name + "L" == r:
                self.assertEqual(getattr(reg, r), value&0xFF, msg="After setting register %s a check of register %s gives 0x%02X (expected 0x%02X)" % (name, r, getattr(reg, r), value&0xFF))
            else:
                self.assertEqual(getattr(reg, r), 0x00, msg="After setting register %s a check of register %s gives 0x%02X (expected 0x00)" % (name, r, getattr(reg, r)))

        self.assertEqual(reg.I, 0x00, msg="After setting register %s a check of register I gives 0x%02X (expected 0x00)" % (name, reg.I))
        self.assertEqual(reg.R, 0x00, msg="After setting register %s a check of register R gives 0x%02X (expected 0x00)" % (name, reg.R))

        for r in ("AF", "BC", "DE", "HL", "IX", "IY", "PC", "SP"):
            if name == r:
                self.assertEqual(getattr(reg, r), value, msg="After setting register %s a check of register %s gives 0x%04X (expected 0x%04X)" % (name, r, getattr(reg, r), value))
            else:
                self.assertEqual(getattr(reg, r), 0x0000, msg="After setting register %s a check of register %s gives 0x%04x (expected 0x0000)" % (name, r, getattr(reg, r)))

    def test_set_16bit(self):
        for r in ("AF", "BC", "DE", "HL", "IX", "IY", "IY", "PC", "SP"):
            self.set16bit(r)

    def test_bad_attr_raises(self):
        reg = RegisterFile()
        with self.assertRaises(AttributeError):
            reg.XY

        with self.assertRaises(AttributeError):
            reg.XY = 0

    def test_ex(self):
        reg = RegisterFile()
        reg.A = 0xAA
        reg.B = 0xBB
        reg.C = 0xCC
        reg.D = 0xDD
        reg.E = 0xEE
        reg.F = 0xF0
        reg.ex()
        self.assertEqual(reg.A, 0x00)
        self.assertEqual(reg.B, 0xBB)
        self.assertEqual(reg.C, 0xCC)
        self.assertEqual(reg.D, 0xDD)
        self.assertEqual(reg.E, 0xEE)
        self.assertEqual(reg.F, 0x00)
        self.assertEqual(reg.H, 0x00)
        self.assertEqual(reg.L, 0x00)
        self.assertEqual(reg.I, 0x00)
        self.assertEqual(reg.R, 0x00)
        self.assertEqual(reg.AF, 0x0000)
        self.assertEqual(reg.BC, 0xBBCC)
        self.assertEqual(reg.DE, 0xDDEE)
        self.assertEqual(reg.HL, 0x0000)
        self.assertEqual(reg.IX, 0x0000)
        self.assertEqual(reg.IY, 0x0000)
        self.assertEqual(reg.PC, 0x0000)
        self.assertEqual(reg.SP, 0x0000)
        reg.ex()
        self.assertEqual(reg.A, 0xAA)
        self.assertEqual(reg.B, 0xBB)
        self.assertEqual(reg.C, 0xCC)
        self.assertEqual(reg.D, 0xDD)
        self.assertEqual(reg.E, 0xEE)
        self.assertEqual(reg.F, 0xF0)
        self.assertEqual(reg.H, 0x00)
        self.assertEqual(reg.L, 0x00)
        self.assertEqual(reg.I, 0x00)
        self.assertEqual(reg.R, 0x00)
        self.assertEqual(reg.AF, 0xAAF0)
        self.assertEqual(reg.BC, 0xBBCC)
        self.assertEqual(reg.DE, 0xDDEE)
        self.assertEqual(reg.HL, 0x0000)
        self.assertEqual(reg.IX, 0x0000)
        self.assertEqual(reg.IY, 0x0000)
        self.assertEqual(reg.PC, 0x0000)
        self.assertEqual(reg.SP, 0x0000)

    def test_exx(self):
        reg = RegisterFile()
        reg.A = 0xAA
        reg.B = 0xBB
        reg.C = 0xCC
        reg.D = 0xDD
        reg.E = 0xEE
        reg.F = 0xF0
        reg.exx()
        self.assertEqual(reg.A, 0xAA)
        self.assertEqual(reg.B, 0x00)
        self.assertEqual(reg.C, 0x00)
        self.assertEqual(reg.D, 0x00)
        self.assertEqual(reg.E, 0x00)
        self.assertEqual(reg.F, 0xF0)
        self.assertEqual(reg.H, 0x00)
        self.assertEqual(reg.L, 0x00)
        self.assertEqual(reg.I, 0x00)
        self.assertEqual(reg.R, 0x00)
        self.assertEqual(reg.AF, 0xAAF0)
        self.assertEqual(reg.BC, 0x0000)
        self.assertEqual(reg.DE, 0x0000)
        self.assertEqual(reg.HL, 0x0000)
        self.assertEqual(reg.IX, 0x0000)
        self.assertEqual(reg.IY, 0x0000)
        self.assertEqual(reg.PC, 0x0000)
        self.assertEqual(reg.SP, 0x0000)
        reg.exx()
        self.assertEqual(reg.A, 0xAA)
        self.assertEqual(reg.B, 0xBB)
        self.assertEqual(reg.C, 0xCC)
        self.assertEqual(reg.D, 0xDD)
        self.assertEqual(reg.E, 0xEE)
        self.assertEqual(reg.F, 0xF0)
        self.assertEqual(reg.H, 0x00)
        self.assertEqual(reg.L, 0x00)
        self.assertEqual(reg.I, 0x00)
        self.assertEqual(reg.R, 0x00)
        self.assertEqual(reg.AF, 0xAAF0)
        self.assertEqual(reg.BC, 0xBBCC)
        self.assertEqual(reg.DE, 0xDDEE)
        self.assertEqual(reg.HL, 0x0000)
        self.assertEqual(reg.IX, 0x0000)
        self.assertEqual(reg.IY, 0x0000)
        self.assertEqual(reg.PC, 0x0000)
        self.assertEqual(reg.SP, 0x0000)

    def test_flags(self):
        reg = RegisterFile()
        flags = (("S", 0x80),
                 ("Z", 0x40),
                 ("H", 0x10),
                 ("P", 0x04),
                 ("V", 0x04),
                 ("N", 0x02),
                 ("C", 0x01))
        for (f,F) in flags:
            self.assertEqual(reg.getflag(f), 0)
            self.assertEqual(reg.F, 0x00)
            reg.setflag(f)
            self.assertEqual(reg.getflag(f), 1)
            self.assertEqual(reg.F, F)
            reg.resetflag(f)
            self.assertEqual(reg.getflag(f), 0)
            self.assertEqual(reg.F, 0x00)
        flagpairs    = [ ((X, Y), A|B) for ((X,A),(Y,B)) in itertools.product(flags, flags) ]
        flagtripples = [ ((X, Y, Z), A|B|C) for ((X,A),(Y,B),(Z,C)) in itertools.product(flags, flags, flags) ]
        flagquads    = [ ((W, X, Y, Z), A|B|C|D) for ((W,A),(X,B),(Y,C),(Z,D)) in itertools.product(flags, flags, flags, flags) ]
        flagquints   = [ ((V, W, X, Y, Z), A|B|C|D|E) for ((V,A),(W,B),(X,C),(Y,D),(Z,E)) in itertools.product(flags, flags, flags, flags, flags) ]
        flaghexes    = [ (("S", "Z", "H", "P", "N", "C"), 0xD7) ]
        for (L,F) in flagpairs + flagtripples + flagquads + flagquints + flaghexes:
            for f in L:
                self.assertEqual(reg.getflag(f), 0)
            self.assertEqual(reg.F, 0x00)
            for f in L:
                reg.setflag(f)
            for f in L:
                self.assertEqual(reg.getflag(f), 1)
            self.assertEqual(reg.F, F)
            for f in L:
                reg.resetflag(f)
            for f in L:
                self.assertEqual(reg.getflag(f), 0)
            self.assertEqual(reg.F, 0x00)

    def test_badflags(self):
        reg = RegisterFile()
        with self.assertRaises(KeyError):
            reg.setflag("X")
        with self.assertRaises(KeyError):
            reg.getflag("X")
        with self.assertRaises(KeyError):
            reg.resetflag("X")

    def test_registermap(self):
        reg = RegisterFile()
        reg.A = 0xAA
        reg.B = 0xBB
        reg.C = 0xCC
        reg.D = 0xDD
        reg.E = 0xEE
        reg.F = 0xFF
        reg.H = 0x44
        reg.L = 0x77
        reg.IX = 0xCAFE
        reg.IY = 0xBABE
        reg.SP = 0xBBC1
        reg.PC = 0xBBC2
        reg.I = 0x6
        reg.R = 0xD7
        expected = """\
  +------+------+    +------+------+
 A| 0xAA | 0xFF |F A'| 0x00 | 0x00 |F'
 B| 0xBB | 0xCC |C B'| 0x00 | 0x00 |C'
 D| 0xDD | 0xEE |E D'| 0x00 | 0x00 |E'
 H| 0x44 | 0x77 |L H'| 0x00 | 0x00 |L'
  +------+------+    +------+------+
IX|    0xCAFE   |
IY|    0xBABE   |
SP|    0xBBC1   |
PC|    0xBBC2   |
  +------+------+
 I| 0x06 | 0xD7 |R
  +------+------+
"""
        self.assertEqual(reg.registermap(), expected, msg="expected:\n %s,\n\n got:\n %s" % (expected, reg.registermap()))

