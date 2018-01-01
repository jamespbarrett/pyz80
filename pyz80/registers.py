"""Implementation of the Z80 register file."""

class RegisterFile(object):
    """This is an emulation of the z80 register file, which will respond to both 8 and 16-bit register names
    as attributes, and supports the ex and exx instructions."""
    def __init__(self):
        super(RegisterFile, self).__setattr__("A", 0x00)
        super(RegisterFile, self).__setattr__("B", 0x00)
        super(RegisterFile, self).__setattr__("C", 0x00)
        super(RegisterFile, self).__setattr__("D", 0x00)
        super(RegisterFile, self).__setattr__("E", 0x00)
        super(RegisterFile, self).__setattr__("F", 0x00)
        super(RegisterFile, self).__setattr__("H", 0x00)
        super(RegisterFile, self).__setattr__("L", 0x00)
        super(RegisterFile, self).__setattr__("I", 0x00)
        super(RegisterFile, self).__setattr__("R", 0x00)

        super(RegisterFile, self).__setattr__("IX", 0x0000)
        super(RegisterFile, self).__setattr__("IY", 0x0000)
        super(RegisterFile, self).__setattr__("SP", 0x0000)
        super(RegisterFile, self).__setattr__("PC", 0x0000)

        super(RegisterFile, self).__setattr__("_A", 0x00)
        super(RegisterFile, self).__setattr__("_B", 0x00)
        super(RegisterFile, self).__setattr__("_C", 0x00)
        super(RegisterFile, self).__setattr__("_D", 0x00)
        super(RegisterFile, self).__setattr__("_E", 0x00)
        super(RegisterFile, self).__setattr__("_F", 0x00)
        super(RegisterFile, self).__setattr__("_H", 0x00)
        super(RegisterFile, self).__setattr__("_L", 0x00)

    def ex(self):
        """Exchange A and F with A' and F'"""
        (a, f) = (self.A, self.F)
        (self.A, self.F) = (self._A, self._F)
        (self._A, self._F) = (a,f)

    def exx(self):
        """Exchange BC, DE, and HL with BC', DE', and HL'"""
        (b, c, d, e, h, l) = (self.B, self.C, self.D, self.E, self.H, self.L)
        (self.B, self.C, self.D, self.E, self.H, self.L) = (self._B, self._C, self._D, self._E, self._H, self._L)
        (self._B, self._C, self._D, self._E, self._H, self._L) = (b, c, d, e, h, l)

    def getflag(self, name):
        """Return the value of the flag, S, Z, H, P, V, N, or C"""
        if name == "S":
            return (self.F >> 7)&0x1
        elif name == "Z":
            return (self.F >> 6)&0x1
        elif name == '5':
            return (self.F >> 5)&0x1
        elif name == "H":
            return (self.F >> 4)&0x1
        elif name == '3':
            return (self.F >> 3)&0x1
        elif name == "P" or name == "V":
            return (self.F >> 2)&0x1
        elif name == "N":
            return (self.F >> 1)&0x1
        if name == "C":
            return (self.F >> 0)&0x1
        raise KeyError

    def setflag(self, name):
        """Set the flag S, Z, H, P, V, N, or C"""
        if name == "S":
            self.F |= 1 << 7
        elif name == "Z":
            self.F |= 1 << 6
        elif name== '5':
            self.F |= 1 << 5
        elif name == "H":
            self.F |= 1 << 4
        elif name== '3':
            self.F |= 1 << 3
        elif name == "P" or name == "V":
            self.F |= 1 << 2
        elif name == "N":
            self.F |= 1 << 1
        elif name == "C":
            self.F |= 1 << 0
        else:
            raise KeyError

    def resetflag(self, name):
        """Reset the flag S, Z, H, P, V, N, or C"""
        if name == "S":
            self.F &= 0xFF - (1 << 7)
        elif name == "Z":
            self.F &= 0xFF - (1 << 6)
        elif name == "5":
            self.F &= 0xFF - (1 << 5)
        elif name == "H":
            self.F &= 0xFF - (1 << 4)
        elif name == "3":
            self.F &= 0xFF - (1 << 3)
        elif name == "P" or name == "V":
            self.F &= 0xFF - (1 << 2)
        elif name == "N":
            self.F &= 0xFF - (1 << 1)
        elif name == "C":
            self.F &= 0xFF - (1 << 0)
        else:
            raise KeyError

    def __getattr__(self, name):
        if name == "AF":
            return self.A << 8 | self.F
        elif name == "BC":
            return self.B << 8 | self.C
        elif name == "DE":
            return self.D << 8 | self.E
        elif name == "HL":
            return self.H << 8 | self.L
        elif name == "IXH":
            return self.IX >> 8
        elif name == "IXL":
            return self.IX&0xFF
        elif name == "IYH":
            return self.IY >> 8
        elif name == "IYL":
            return self.IY&0xFF
        elif name == "SPH":
            return self.SP >> 8
        elif name == "SPL":
            return self.SP&0xFF
        elif name == "PCH":
            return self.PC >> 8
        elif name == "PCL":
            return self.PC&0xFF
        raise AttributeError

    def __setattr__(self, name, value):
        if not isinstance(value, int):
            raise Exception("Attempt to set register {} to invalid value {}".format(name, value))
        if name == "AF":
            super(RegisterFile, self).__setattr__('A', (value >> 8)&0xFF)
            super(RegisterFile, self).__setattr__('F', value&0xFF)
        elif name == "BC":
            super(RegisterFile, self).__setattr__('B', (value >> 8)&0xFF)
            super(RegisterFile, self).__setattr__('C', value&0xFF)
        elif name == "DE":
            super(RegisterFile, self).__setattr__('D', (value >> 8)&0xFF)
            super(RegisterFile, self).__setattr__('E', value&0xFF)
        elif name == "HL":
            super(RegisterFile, self).__setattr__('H', (value >> 8)&0xFF)
            super(RegisterFile, self).__setattr__('L', value&0xFF)
        elif name == "IXH":
            super(RegisterFile, self).__setattr__('IX', self.IXL + (value << 8))
        elif name == "IXL":
            super(RegisterFile, self).__setattr__('IX', (self.IXH << 8) + value)
        elif name == "IYH":
            super(RegisterFile, self).__setattr__('IY', self.IYL + (value << 8))
        elif name == "IYL":
            super(RegisterFile, self).__setattr__('IY', (self.IYH << 8) + value)
        elif name == "SPH":
            super(RegisterFile, self).__setattr__('SP', self.SPL + (value << 8))
        elif name == "SPL":
            super(RegisterFile, self).__setattr__('SP', (self.SPH << 8) + value)
        elif name == "PCH":
            super(RegisterFile, self).__setattr__('PC', self.PCL + (value << 8))
        elif name == "PCL":
            super(RegisterFile, self).__setattr__('PC', (self.PCH << 8) + value)
        else:
            getattr(self, name)
            super(RegisterFile,self).__setattr__(name, value)

    def registermap(self):
        """Return a string which is a diagram illustrating the current state of the registers."""
        return """\
  +------+------+    +------+------+
 A| 0x%02X | 0x%02X |F A'| 0x%02X | 0x%02X |F'
 B| 0x%02X | 0x%02X |C B'| 0x%02X | 0x%02X |C'
 D| 0x%02X | 0x%02X |E D'| 0x%02X | 0x%02X |E'
 H| 0x%02X | 0x%02X |L H'| 0x%02X | 0x%02X |L'
  +------+------+    +------+------+
IX|    0x%04X   |    +-+-+-+-+-+-+-+-+
IY|    0x%04X   |    |S|Z|5|H|3|V|N|C|
SP|    0x%04X   |    |%1d|%1d|%1d|%1d|%1d|%1d|%1d|%1d|
PC|    0x%04X   |    +-+-+-+-+-+-+-+-+
  +------+------+
 I| 0x%02X | 0x%02X |R
  +------+------+
""" % (self.A, self.F, self._A, self._F,
           self.B, self.C, self._B, self._C,
           self.D, self.E, self._D, self._E,
           self.H, self.L, self._H, self._L,
           self.IX,
           self.IY,
           self.SP, self.getflag('S'), self.getflag('Z'), self.getflag('5'), self.getflag('H'), self.getflag('3'), self.getflag('V'), self.getflag('N'), self.getflag('C'),
           self.PC,
           self.I, self.R)

if __name__ == "__main__": # pragma: no cover
    reg = RegisterFile()
    print(reg.registermap())
