import unittest
import mock

from pyz80.machinestates import decode_instruction
from pyz80.machinestates import INSTRUCTION_STATES

from pyz80.cpu import *
from pyz80.memorybus import MemoryBus, ROM
from pyz80.iobus import IOBus, Device

def set_register_to(reg, val):
    def _inner(tc, cpu, name):
        setattr(cpu.reg, reg, val)
    return _inner

def write_to_memory(addr, val):
    def _inner(tc, cpu, name):
        cpu.membus.write(addr, val)
    return _inner

def expect_register_equal(reg, val):
    def _inner(tc, cpu, name):
        rval = getattr(cpu.reg, reg)
        tc.assertEqual(rval, val, msg="""[ {} ] Expected register {} to contain value 0x{:X}, but actually contains 0x{:X}
Full register contents:
{}
""".format(name, reg, val, rval, cpu.reg.registermap()))
    return _inner

def expect_memory_location_equal(addr, val):
    def _inner(tc, cpu, name):
        rval = cpu.membus.read(addr)
        tc.assertEqual(rval, val, msg="""[ {} ] Expected location 0x{:X} to contain value 0x{:X}, but actually contains 0x{:X}""".format(name, addr, val, rval))
    return _inner

def ex(tc, cpu, name):
    cpu.reg.ex()

def exx(tc, cpu, name):
    cpu.reg.exx()

def ei(tc, cpu, name):
    cpu.iff1 = 1
    cpu.iff2 = 1

def di(tc, cpu, name):
    cpu.iff1 = 0
    cpu.iff2 = 0

def begin_nmi(tc, cpu, name):
    cpu.iff1 = 0
    cpu.iff2 = 1

def expect_int_enabled(tc, cpu, name):
    tc.assertEqual(cpu.iff1, 1, msg="""[ {} ] Expected iff1 to be set, is actually reset""".format(name))

class MEM(object):
    def __call__(self, key, value):
        return write_to_memory(key, value)

    def __getitem__(self, key):
        class __inner(object):
            def __init__(self, key):
                self.key = key

            def __eq__(self, other):
                return expect_memory_location_equal(self.key, other)
        return __inner(key)

class FLAG(object):
    def __call__(self, key, value=None):
        if value is None:
            return set_register_to("F", key)
        def _inner(tc, cpu, name):
            if value == 0:
                cpu.reg.resetflag(key)
            else:
                cpu.reg.setflag(key)
        return _inner

    def __getitem__(self, key):
        class _inner(object):
            def __init__(self, key):
                self.key = key

            def __eq__(self, other):
                def __inner(tc, cpu, name):
                    rval = cpu.reg.getflag(self.key)
                    tc.assertEqual(rval, other, msg="""[ {} ] Expected flag {} to be {}, was actually {}""".format(name, self.key, other, rval))
                return __inner
        return _inner(key)

    def __eq__(self, other):
        return expect_register_equal('F', other)

class REG(object):
    def __init__(self, r):
        self.r = r

    def __call__(self, value):
        return set_register_to(self.r, value)

    def __eq__(self, other):
        return expect_register_equal(self.r, other)

class DummyInput(Device):
    def __init__(self):
        self.data = 0x00
        self.high = 0x00
        super(DummyInput, self).__init__()
    
    def responds_to_port(self, port):
        return (port == 0xFE)

    def read(self, address):
        self.high = address
        return self.data

class _IN(object):
    def __init__(self):
        self.device = DummyInput()

    def __call__(self, value):
        def _inner(tc, cpu, name):
            self.device.data = value
            self.device.high = 0x00
        return _inner

    def __eq__(self, other):
        def _inner(tc, cpu, name):
            tc.assertEqual(self.device.high, other, msg="""[ {} ] Expected most recent high address on input port to be 0x{:X}, but actually 0x{:X}""".format(name, other, self.device.high))
        return _inner

class DummyOutput(Device):
    def __init__(self):
        self.data = 0x00
        self.high = 0x00
        super(DummyOutput, self).__init__()
    
    def responds_to_port(self, port):
        return (port == 0xFA)

    def write(self, address, value):
        self.data = value
        self.high = address

class _OUT(object):
    def __init__(self):
        self.device = DummyOutput()

    def __eq__(self, other):
        def _inner(tc, cpu, name):
            tc.assertEqual((self.device.high, self.device.data), other, msg="""[ {} ] Expected most recent high address and data on input port to be (0x{:X},0x{:X}) but actually (0x{:X},0x{:X})""".format(name, other[0], other[1], self.device.high, self.device.data))
        return _inner

IN = _IN()
OUT = _OUT()
F = FLAG()
M = MEM()
A = REG('A')
B = REG('B')
C = REG('C')
D = REG('D')
E = REG('E')
H = REG('H')
L = REG('L')
I = REG('I')
R = REG('R')

SP = REG('SP')
PC = REG('PC')

IX = REG('IX')
IY = REG('IY')

AF = REG('AF')
BC = REG('BC')
DE = REG('DE')
HL = REG('HL')

class TestInstructionSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executed_instructions = []

    @classmethod
    def tearDownClass(cls):
        print
        print "Instruction Coverage:"
        print "---------------------"
        covered = 0
        total   = 0
        keys = sorted(INSTRUCTION_STATES.iterkeys())
        for i in keys:
            if i in cls.executed_instructions:
                print "> ",
                covered += 1
            else:
                print "! ",
            if isinstance(i, int):
                print "{:#02x}".format(i)
            else:
                print "({:#02x},{:#02x})".format(*i)
            total += 1
        print "---------------------"
        print "Cover: {: >7.2%}".format(float(covered)/float(total))
        print "---------------------"

    def execute_instructions(self, pre, instructions, t_cycles, post, name):
        IN.device.data = 0x00
        IN.device.high = 0x00
        OUT.device.data = 0x00
        OUT.device.high = 0x00
        membus = MemoryBus()
        iobus  = IOBus([ IN.device, OUT.device ])
        cpu    = Z80CPU(iobus, membus)

        for n in range(0,len(instructions)):
            membus.write(n, instructions[n])
        membus.write(len(instructions), 0xFF) # This should raise an exception when we reach it

        for action in pre:
            action(self, cpu, name)

        original_decode_instruction = decode_instruction
        with mock.patch('pyz80.machinestates.decode_instruction', side_effect=original_decode_instruction) as _decode_instruction:
            for n in range(0, t_cycles):
                cpu.clock()

        self.__class__.executed_instructions.extend(call[1][0] for call in _decode_instruction.mock_calls)

        self.assertEqual(len(cpu.pipelines), 1)
        self.assertEqual(len(cpu.pipelines[0]), 1, msg="[{}] At end of instruction pipeline still contains machine states: {!r}".format(name, cpu.pipelines[0]))
        self.assertEqual(str(type(cpu.pipelines[0][0])), "<class 'pyz80.machinestates._OCF'>")

        for action in post:
            action(self, cpu, name)

    def test_NOP(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [], [ 0x00, ], 4, [ (PC == 0x01), ], "NOP" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_LD(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ I(0x0B) ],     [ 0xED, 0x57 ], 9, [ (PC == 0x02), (A == 0x0B), (F == 0x08) ], "LD A,I (I == 0x0B)" ],
            [ [ I(0x80) ],     [ 0xED, 0x57 ], 9, [ (PC == 0x02), (A == 0x80), (F == 0x80) ], "LD A,I (I == 0x80)" ],
            [ [ I(0x00) ],     [ 0xED, 0x57 ], 9, [ (PC == 0x02), (A == 0x00), (F == 0x40) ], "LD A,I (I == 0x00)" ],
            [ [ I(0x20) ],     [ 0xED, 0x57 ], 9, [ (PC == 0x02), (A == 0x20), (F == 0x20) ], "LD A,I (I == 0x20)" ],
            [ [ ei, I(0x01) ], [ 0xED, 0x57 ], 9, [ (PC == 0x02), (A == 0x01), (F == 0x04) ], "LD A,I (I == 0x01, iff2=1)" ],
            [ [ R(0x0B) ],     [ 0xED, 0x5F ], 9, [ (PC == 0x02), (A == 0x0B), (F == 0x08) ], "LD A,R (R == 0x0B)" ],
            [ [ R(0x80) ],     [ 0xED, 0x5F ], 9, [ (PC == 0x02), (A == 0x80), (F == 0x80) ], "LD A,R (R == 0x80)" ],
            [ [ R(0x00) ],     [ 0xED, 0x5F ], 9, [ (PC == 0x02), (A == 0x00), (F == 0x40) ], "LD A,R (R == 0x00)" ],
            [ [ R(0x20) ],     [ 0xED, 0x5F ], 9, [ (PC == 0x02), (A == 0x20), (F == 0x20) ], "LD A,R (R == 0x20)" ],
            [ [ ei, R(0x01) ], [ 0xED, 0x5F ], 9, [ (PC == 0x02), (A == 0x01), (F == 0x04) ], "LD A,R (R == 0x01, iff2=1)" ],
            [ [ A(0x0B) ], [ 0xED, 0x47 ], 9, [ (PC == 0x02), (I == 0x0B) ], "LD I,A" ],
            [ [ A(0x0B) ], [ 0xED, 0x4F ], 9, [ (PC == 0x02), (R == 0x0B) ], "LD R,A" ],

            [ [], [ 0x01, 0xBC, 0x1B ], 10, [ (PC == 0x03), (BC == 0x1BBC), ], "LD BC,1BBCH" ],
            [ [], [ 0x11, 0xBC, 0x1B ], 10, [ (PC == 0x03), (DE == 0x1BBC), ], "LD DE,1BBCH" ],
            [ [], [ 0x21, 0xBC, 0x1B ], 10, [ (PC == 0x03), (HL == 0x1BBC), ], "LD HL,1BBCH" ],
            [ [], [ 0x31, 0xBC, 0x1B ], 10, [ (PC == 0x03), (SP == 0x1BBC), ], "LD SP,1BBCH" ],
            [ [], [ 0xDD, 0x21, 0xBC, 0x1B ], 14, [ (PC == 0x04), (IX == 0x1BBC), ], "LD IX,1BBCH" ],
            [ [], [ 0xFD, 0x21, 0xBC, 0x1B ], 14, [ (PC == 0x04), (IY == 0x1BBC), ], "LD IY,1BBCH" ],

            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0x2A, 0xBC, 0x1B ],       16, [ (PC == 0x03), (HL == 0xCAFE) ], "LD HL,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xED, 0x4B, 0xBC, 0x1B ], 20, [ (PC == 0x04), (BC == 0xCAFE) ], "LD BC,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xED, 0x5B, 0xBC, 0x1B ], 20, [ (PC == 0x04), (DE == 0xCAFE) ], "LD DE,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xED, 0x7B, 0xBC, 0x1B ], 20, [ (PC == 0x04), (SP == 0xCAFE) ], "LD SP,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xDD, 0x2A, 0xBC, 0x1B ], 20, [ (PC == 0x04), (IX == 0xCAFE) ], "LD IX,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xFD, 0x2A, 0xBC, 0x1B ], 20, [ (PC == 0x04), (IY == 0xCAFE) ], "LD IY,(1BBCH)" ],

            [ [ BC(0xCAFE) ], [ 0xED, 0x43, 0xBC, 0x1B ], 20, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),BC" ],
            [ [ DE(0xCAFE) ], [ 0xED, 0x53, 0xBC, 0x1B ], 20, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),DE" ],
            [ [ HL(0xCAFE) ], [ 0x22, 0xBC, 0x1B ],       16, [ (PC == 0x03), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),HL" ],
            [ [ SP(0xCAFE) ], [ 0xED, 0x73, 0xBC, 0x1B ], 20, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),SP" ],
            [ [ IX(0xCAFE) ], [ 0xDD, 0x22, 0xBC, 0x1B ], 20, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IX" ],
            [ [ IY(0xCAFE) ], [ 0xFD, 0x22, 0xBC, 0x1B ], 20, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IY" ],

            [ [ HL(0x1BBC) ], [ 0xF9 ], 4, [ (PC == 0x01), (SP == 0x1BBC), ], "LD SP,HL" ],

            [ [ BC(0x1BBC), A(0xB) ], [ 0x02, ], 7, [ (PC == 0x01), (M[0x1BBC] == 0xB) ], "LD (BC),A" ],
            [ [ DE(0x1BBC), A(0xB) ], [ 0x12, ], 7, [ (PC == 0x01), (M[0x1BBC] == 0xB) ], "LD (DE),A" ],

            [ [ BC(0x1BBC), M(0x1BBC,0xB) ], [ 0x0A, ], 7, [ (PC == 0x01), (A == 0xB), ], "LD A,(BC)" ],
            [ [ DE(0x1BBC), M(0x1BBC,0xB) ], [ 0x1A, ], 7, [ (PC == 0x01), (A == 0xB), ], "LD A,(DE)" ],

            [ [], [ 0x06, 0x0B, ], 7, [ (PC == 0x02), (B == 0xB) ], "LD B,0BH" ],
            [ [], [ 0x0E, 0x0B, ], 7, [ (PC == 0x02), (C == 0xB) ], "LD C,0BH" ],
            [ [], [ 0x16, 0x0B, ], 7, [ (PC == 0x02), (D == 0xB) ], "LD D,0BH" ],
            [ [], [ 0x1E, 0x0B, ], 7, [ (PC == 0x02), (E == 0xB) ], "LD E,0BH" ],
            [ [], [ 0x26, 0x0B, ], 7, [ (PC == 0x02), (H == 0xB) ], "LD H,0BH" ],
            [ [], [ 0x2E, 0x0B, ], 7, [ (PC == 0x02), (L == 0xB) ], "LD L,0BH" ],
            [ [], [ 0x3E, 0x0B, ], 7, [ (PC == 0x02), (A == 0xB) ], "LD A,0BH" ],

            [ [ A(0xB), ],        [ 0x32, 0xBC, 0x1B ], 13, [ (PC == 0x03), (M[0x1BBC] == 0x0B) ], "LD (1BBCH),A" ],
            [ [ HL(0x1BBC), ],    [ 0x36, 0x0B ],       10, [ (PC == 0x02), (M[0x1BBC] == 0x0B) ], "LD (HL),0BH"  ],
            [ [ M(0x1BBC,0xB), ], [ 0x3A, 0xBC, 0x1B ], 13, [ (PC == 0x03), (A == 0x0B) ],         "LD A,(1BBCH)" ],

            [ [ B(0xB) ], [ 0x40, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,B" ],
            [ [ C(0xB) ], [ 0x41, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,C" ],
            [ [ D(0xB) ], [ 0x42, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,D" ],
            [ [ E(0xB) ], [ 0x43, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,E" ],
            [ [ H(0xB) ], [ 0x44, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,H" ],
            [ [ L(0xB) ], [ 0x45, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,L" ],
            [ [ HL(0x1BBC), M(0x1BBC,0xB) ], [ 0x46, ], 7, [ (PC == 0x01), (B == 0xB), ], "LD B,(HL)" ],
            [ [ A(0xB) ], [ 0x47, ], 4, [ (PC == 0x01), (B == 0xB), ], "LD B,A" ],
            [ [ B(0xB) ], [ 0x48, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,B" ],
            [ [ C(0xB) ], [ 0x49, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,C" ],
            [ [ D(0xB) ], [ 0x4A, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,D" ],
            [ [ E(0xB) ], [ 0x4B, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,E" ],
            [ [ H(0xB) ], [ 0x4C, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,H" ],
            [ [ L(0xB) ], [ 0x4D, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,L" ],
            [ [ HL(0x1BBC), M(0x1BBC, 0xB) ], [ 0x4E, ], 7, [ (PC == 0x01), (C == 0xB), ], "LD C,(HL)" ],
            [ [ A(0xB) ], [ 0x4F, ], 4, [ (PC == 0x01), (C == 0xB), ], "LD C,A" ],

            [ [ B(0xB) ], [ 0x50, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,B" ],
            [ [ C(0xB) ], [ 0x51, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,C" ],
            [ [ D(0xB) ], [ 0x52, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,D" ],
            [ [ E(0xB) ], [ 0x53, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,E" ],
            [ [ H(0xB) ], [ 0x54, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,H" ],
            [ [ L(0xB) ], [ 0x55, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,L" ],
            [ [ HL(0x1BBC), M(0x1BBC, 0xB) ], [ 0x56, ], 7, [ (PC == 0x01), (D == 0xB), ], "LD D,(HL)" ],
            [ [ A(0xB) ], [ 0x57, ], 4, [ (PC == 0x01), (D == 0xB), ], "LD D,A" ],
            [ [ B(0xB) ], [ 0x58, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,B" ],
            [ [ C(0xB) ], [ 0x59, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,C" ],
            [ [ D(0xB) ], [ 0x5A, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,D" ],
            [ [ E(0xB) ], [ 0x5B, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,E" ],
            [ [ H(0xB) ], [ 0x5C, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,H" ],
            [ [ L(0xB) ], [ 0x5D, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,L" ],
            [ [ HL(0x1BBC), M(0x1BBC, 0xB) ], [ 0x5E, ], 7, [ (PC == 0x01), (E == 0xB), ], "LD E,(HL)" ],
            [ [ A(0xB) ], [ 0x5F, ], 4, [ (PC == 0x01), (E == 0xB), ], "LD E,A" ],

            [ [ B(0xB) ], [ 0x60, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,B" ],
            [ [ C(0xB) ], [ 0x61, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,C" ],
            [ [ D(0xB) ], [ 0x62, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,D" ],
            [ [ E(0xB) ], [ 0x63, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,E" ],
            [ [ H(0xB) ], [ 0x64, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,H" ],
            [ [ L(0xB) ], [ 0x65, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,L" ],
            [ [ HL(0x1BBC), M(0x1BBC, 0xB) ], [ 0x66, ], 7, [ (PC == 0x01), (H == 0xB), ], "LD H,(HL)" ],
            [ [ A(0xB) ], [ 0x67, ], 4, [ (PC == 0x01), (H == 0xB), ], "LD H,A" ],
            [ [ B(0xB) ], [ 0x68, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,B" ],
            [ [ C(0xB) ], [ 0x69, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,C" ],
            [ [ D(0xB) ], [ 0x6A, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,D" ],
            [ [ E(0xB) ], [ 0x6B, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,E" ],
            [ [ H(0xB) ], [ 0x6C, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,H" ],
            [ [ L(0xB) ], [ 0x6D, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,L" ],
            [ [ HL(0x1BBC), M(0x1BBC, 0xB) ], [ 0x6E, ], 7, [ (PC == 0x01), (L == 0xB), ], "LD L,(HL)" ],
            [ [ A(0xB) ], [ 0x6F, ], 4, [ (PC == 0x01), (L == 0xB), ], "LD L,A" ],

            [ [ IX(0xCAFE) ], [ 0xDD, 0xF9 ], 8, [ (PC == 0x02), (SP == 0xCAFE) ], "LD SP,IX"],
            [ [ IY(0xCAFE) ], [ 0xFD, 0xF9 ], 8, [ (PC == 0x02), (SP == 0xCAFE) ], "LD SP,IY"],

            [ [ HL(0x1BBC), B(0xB) ], [ 0x70, ], 7, [ (PC == 0x01), M[0x1BBC] == 0xB  ], "LD (HL),B" ],
            [ [ HL(0x1BBC), C(0xB) ], [ 0x71, ], 7, [ (PC == 0x01), M[0x1BBC] == 0xB  ], "LD (HL),C" ],
            [ [ HL(0x1BBC), D(0xB) ], [ 0x72, ], 7, [ (PC == 0x01), M[0x1BBC] == 0xB  ], "LD (HL),D" ],
            [ [ HL(0x1BBC), E(0xB) ], [ 0x73, ], 7, [ (PC == 0x01), M[0x1BBC] == 0xB  ], "LD (HL),E" ],
            [ [ HL(0x1BBC) ],         [ 0x74, ], 7, [ (PC == 0x01), M[0x1BBC] == 0x1B ], "LD (HL),H" ],
            [ [ HL(0x1BBC) ],         [ 0x75, ], 7, [ (PC == 0x01), M[0x1BBC] == 0xBC ], "LD (HL),L" ],
            [ [ HL(0x1BBC), A(0xB) ], [ 0x77, ], 7, [ (PC == 0x01), M[0x1BBC] == 0xB  ], "LD (HL),A" ],

            [ [ B(0xB) ], [ 0x78, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,B" ],
            [ [ C(0xB) ], [ 0x79, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,C" ],
            [ [ D(0xB) ], [ 0x7A, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,D" ],
            [ [ E(0xB) ], [ 0x7B, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,E" ],
            [ [ H(0xB) ], [ 0x7C, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,H" ],
            [ [ L(0xB) ], [ 0x7D, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,L" ],
            [ [ HL(0x1BBC), M(0x1BBC, 0xB) ], [ 0x7E, ], 7, [ (PC == 0x01), (A == 0xB), ], "LD L,(HL)" ],
            [ [ A(0xB) ], [ 0x7F, ], 4, [ (PC == 0x01), (A == 0xB), ], "LD L,A" ],

            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x46, 0x0C ], 19, [ (PC == 0x3), (B == 0x0B) ], "LD B,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x4E, 0x0C ], 19, [ (PC == 0x3), (C == 0x0B) ], "LD C,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x56, 0x0C ], 19, [ (PC == 0x3), (D == 0x0B) ], "LD D,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x5E, 0x0C ], 19, [ (PC == 0x3), (E == 0x0B) ], "LD E,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x66, 0x0C ], 19, [ (PC == 0x3), (H == 0x0B) ], "LD H,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x6E, 0x0C ], 19, [ (PC == 0x3), (L == 0x0B) ], "LD L,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x7E, 0x0C ], 19, [ (PC == 0x3), (A == 0x0B) ], "LD A,(IX+0CH)"],

            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x46, 0x0C ], 19, [ (PC == 0x3), (B == 0x0B) ], "LD B,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x4E, 0x0C ], 19, [ (PC == 0x3), (C == 0x0B) ], "LD C,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x56, 0x0C ], 19, [ (PC == 0x3), (D == 0x0B) ], "LD D,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x5E, 0x0C ], 19, [ (PC == 0x3), (E == 0x0B) ], "LD E,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x66, 0x0C ], 19, [ (PC == 0x3), (H == 0x0B) ], "LD H,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x6E, 0x0C ], 19, [ (PC == 0x3), (L == 0x0B) ], "LD L,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x7E, 0x0C ], 19, [ (PC == 0x3), (A == 0x0B) ], "LD A,(IY+0CH)"],

            [ [ B(0x0B), IX(0x1BB0) ], [ 0xDD, 0x70, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),B"],
            [ [ C(0x0B), IX(0x1BB0) ], [ 0xDD, 0x71, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),C"],
            [ [ D(0x0B), IX(0x1BB0) ], [ 0xDD, 0x72, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),D"],
            [ [ E(0x0B), IX(0x1BB0) ], [ 0xDD, 0x73, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),E"],
            [ [ H(0x0B), IX(0x1BB0) ], [ 0xDD, 0x74, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),H"],
            [ [ L(0x0B), IX(0x1BB0) ], [ 0xDD, 0x75, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),L"],
            [ [ A(0x0B), IX(0x1BB0) ], [ 0xDD, 0x77, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),A"],

            [ [ IX(0x1BB0) ], [ 0xDD, 0x36, 0x0C, 0x0B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),0BH"],
            [ [ IY(0x1BB0) ], [ 0xFD, 0x36, 0x0C, 0x0B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),0BH"],

            [ [ B(0x0B), IY(0x1BB0) ], [ 0xFD, 0x70, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),B"],
            [ [ C(0x0B), IY(0x1BB0) ], [ 0xFD, 0x71, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),C"],
            [ [ D(0x0B), IY(0x1BB0) ], [ 0xFD, 0x72, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),D"],
            [ [ E(0x0B), IY(0x1BB0) ], [ 0xFD, 0x73, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),E"],
            [ [ H(0x0B), IY(0x1BB0) ], [ 0xFD, 0x74, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),H"],
            [ [ L(0x0B), IY(0x1BB0) ], [ 0xFD, 0x75, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),L"],
            [ [ A(0x0B), IY(0x1BB0) ], [ 0xFD, 0x77, 0x0C ], 19, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),A"],

            [ [ BC(0xCAFE) ], [ 0xED, 0x43, 0xBC, 0x1B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),BC" ],
            [ [ DE(0xCAFE) ], [ 0xED, 0x53, 0xBC, 0x1B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),DE" ],
            [ [ SP(0xCAFE) ], [ 0xED, 0x73, 0xBC, 0x1B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),SP" ],
            [ [ IX(0xCAFE) ], [ 0xDD, 0x22, 0xBC, 0x1B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IX" ],
            [ [ IY(0xCAFE) ], [ 0xFD, 0x22, 0xBC, 0x1B ], 22, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IY" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_pop(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xC1, ],       10, [ (PC == 0x01), (SP == 0x1BBE), (BC == 0xCAFE) ], "POP BC" ],
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xD1, ],       10, [ (PC == 0x01), (SP == 0x1BBE), (DE == 0xCAFE) ], "POP DE" ],
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xE1, ],       10, [ (PC == 0x01), (SP == 0x1BBE), (HL == 0xCAFE) ], "POP HL" ],
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xF1, ],       10, [ (PC == 0x01), (SP == 0x1BBE), (AF == 0xCAFE) ], "POP AF" ],
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xDD, 0xE1, ], 14, [ (PC == 0x02), (SP == 0x1BBE), (IX == 0xCAFE) ], "POP IX" ],
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xFD, 0xE1, ], 14, [ (PC == 0x02), (SP == 0x1BBE), (IY == 0xCAFE) ], "POP IY" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_push(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ AF(0xCAFE), SP(0x1BBC) ], [ 0xF5, ],       10, [ (PC == 0x01), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH AF" ],
            [ [ BC(0xCAFE), SP(0x1BBC) ], [ 0xC5, ],       10, [ (PC == 0x01), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH BC" ],
            [ [ DE(0xCAFE), SP(0x1BBC) ], [ 0xD5, ],       10, [ (PC == 0x01), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH DE" ],
            [ [ HL(0xCAFE), SP(0x1BBC) ], [ 0xE5, ],       10, [ (PC == 0x01), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH HL" ],
            [ [ IX(0xCAFE), SP(0x1BBC) ], [ 0xDD, 0xE5, ], 14, [ (PC == 0x02), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH IX" ],
            [ [ IY(0xCAFE), SP(0x1BBC) ], [ 0xFD, 0xE5, ], 14, [ (PC == 0x02), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH IY" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ex(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ AF(0xA), ex, AF(0xB) ], [ 0x08 ], 4, [ (PC == 0x01), (AF == 0xA), ex, (AF == 0xB) ], "EX AF,AF'" ],
            [ [ DE(0xA), HL(0xB)],      [ 0xEB ], 4, [ (PC == 0x01), (DE == 0xB), (HL == 0xA) ],     "EX DE,HL" ],
            [ [ HL(0xCAFE), SP(0x1BBC), M(0x1BBC, 0x37), M(0x1BBD, 0x13),],   [ 0xE3 ], 19, [ (PC == 0x01), (HL == 0x1337), (SP == 0x1BBC), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "EX (SP),HL" ],
            [ [ IX(0xCAFE), SP(0x1BBC), M(0x1BBC, 0x37), M(0x1BBD, 0x13),],   [ 0xDD, 0xE3 ], 23, [ (PC==0x02), (IX==0x1337), (SP==0x1BBC), (M[0x1BBC]==0xFE), (M[0x1BBD]==0xCA) ], "EX (SP),IX" ],
            [ [ IY(0xCAFE), SP(0x1BBC), M(0x1BBC, 0x37), M(0x1BBD, 0x13),],   [ 0xFD, 0xE3 ], 23, [ (PC==0x02), (IY==0x1337), (SP==0x1BBC), (M[0x1BBC]==0xFE), (M[0x1BBD]==0xCA) ], "EX (SP),IY" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_exx(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        (pre, instructions, t_cycles, post, name) = [
            [ BC(0xCAFE), DE(0x1BBC), HL(0xDEAD), exx,  BC(0x1337), DE(0x8080), HL(0xF00F) ],
            [ 0xD9 ], 4,
            [ (BC == 0xCAFE), (DE == 0x1BBC), (HL == 0xDEAD), exx, (BC == 0x1337), (DE == 0x8080), (HL == 0xF00F) ],
            "EXX"
            ]

        self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ldi(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x02), A(0x00), M(0x1BBC, 0x2B) ], [ 0xED, 0xA0 ], 16, [ (PC==0x02),(HL==0x1BBD),(DE==0x2BBD),(BC==0x1),(M[0x2BBC]==0x2B), (F==0x2C) ], "LDI (nz, A==0x00)" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x02), A(0x08), M(0x1BBC, 0x2B) ], [ 0xED, 0xA0 ], 16, [ (PC==0x02),(HL==0x1BBD),(DE==0x2BBD),(BC==0x1),(M[0x2BBC]==0x2B), (F==0x24) ], "LDI (nz, A==0x08)" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x02), A(0x20), M(0x1BBC, 0x2B) ], [ 0xED, 0xA0 ], 16, [ (PC==0x02),(HL==0x1BBD),(DE==0x2BBD),(BC==0x1),(M[0x2BBC]==0x2B), (F==0x0C) ], "LDI (nz, A==0x20)" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x01), A(0x00), M(0x1BBC, 0x2B) ], [ 0xED, 0xA0 ], 16, [ (PC==0x02),(HL==0x1BBD),(DE==0x2BBD),(BC==0x0),(M[0x2BBC]==0x2B), (F==0x28) ], "LDI (z,  A==0z00)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ldir(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x2), M(0x1BBC, 0xB), F("V",1) ], [ 0xED, 0xB0 ], 21, [ (PC==0x00), (HL==0x1BBD), (DE==0x2BBD), (BC==0x1), (M[0x2BBC]==0xB), (F["V"]==1) ], "LDIR (count non-zero)" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x1), M(0x1BBC, 0xB), F("V",1) ], [ 0xED, 0xB0 ], 16, [ (PC==0x02), (HL==0x1BBD), (DE==0x2BBD), (BC==0x0), (M[0x2BBC]==0xB), (F["V"]==0) ], "LDIR (count zero)" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x2), M(0x1BBC, 0xB), M(0x1BBD, 0xC), F("V",1) ], [ 0xED, 0xB0 ], 37, [ (PC==0x02), (HL==0x1BBE), (DE==0x2BBE), (BC==0x0), (M[0x2BBC]==0xB), (M[0x2BBD]==0xC), (F["V"]==0) ], "LDIR (loop)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ldd(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x2), M(0x1BBC, 0xB), F("V",1) ], [ 0xED, 0xA8 ], 16, [ (PC==0x02), (HL==0x1BBB), (DE==0x2BBB), (BC==0x1), (M[0x2BBC]==0xB), (F["V"]==1) ], "LDI" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x1), M(0x1BBC, 0xB), F("V",1) ], [ 0xED, 0xA8 ], 16, [ (PC==0x02), (HL==0x1BBB), (DE==0x2BBB), (BC==0x0), (M[0x2BBC]==0xB), (F["V"]==0) ], "LDI" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_lddr(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x2), M(0x1BBC, 0xB), F("V",1) ], [ 0xED, 0xB8 ], 21, [ (PC==0x00), (HL==0x1BBB), (DE==0x2BBB), (BC==0x1), (M[0x2BBC]==0xB), (F["V"]==1) ], "LDIR (count non-zero)" ],
            [ [ HL(0x1BBC), DE(0x2BBC), BC(0x1), M(0x1BBC, 0xB), F("V",1) ], [ 0xED, 0xB8 ], 16, [ (PC==0x02), (HL==0x1BBB), (DE==0x2BBB), (BC==0x0), (M[0x2BBC]==0xB), (F["V"]==0) ], "LDIR (count zero)" ],
            [ [ HL(0x1BBD), DE(0x2BBD), BC(0x2), M(0x1BBC, 0xB), M(0x1BBD, 0xC), F("V",1) ], [ 0xED, 0xB8 ], 37, [ (PC==0x02), (HL==0x1BBB), (DE==0x2BBB), (BC==0x0), (M[0x2BBC]==0xB), (M[0x2BBD]==0xC), (F["V"]==0) ], "LDIR (loop)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_cpi(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), BC(0x2), M(0x1BBC, 0xFE), A(0x00) ], [ 0xED, 0xA1 ], 16, [ (PC==0x02), (HL==0x1BBD), (BC==0x1), (F==0x06) ], "CPI (ne)" ],
            [ [ HL(0x1BBC), BC(0x2), M(0x1BBC, 0xFE), A(0xFE) ], [ 0xED, 0xA1 ], 16, [ (PC==0x02), (HL==0x1BBD), (BC==0x1), (F==0x46) ], "CPI (eq)" ],
            [ [ HL(0x1BBC), BC(0x1), M(0x1BBC, 0xFE), A(0x00) ], [ 0xED, 0xA1 ], 16, [ (PC==0x02), (HL==0x1BBD), (BC==0x0), (F==0x02) ], "CPI (ne,last)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_cpir(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), BC(0x3), M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), A(0xCA) ], [ 0xED, 0xB1 ], 37, [ (PC==0x02), (HL==0x1BBE), (BC==0x1), (F==0x46) ], "CPIR (found after 2 cycles)" ],
            [ [ HL(0x1BBC), BC(0x3), M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), A(0x00) ], [ 0xED, 0xB1 ], 58, [ (PC==0x02), (HL==0x1BBF), (BC==0x0), (F==0x42) ], "CPIR (found after 3 cycles)" ],
            [ [ HL(0x1BBC), BC(0x3), M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), A(0xBA) ], [ 0xED, 0xB1 ], 58, [ (PC==0x02), (HL==0x1BBF), (BC==0x0), (F==0x2A) ], "CPIR (not found after 3 cycles)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_cpd(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), BC(0x2), M(0x1BBC, 0xFE), A(0x00) ], [ 0xED, 0xA9 ], 16, [ (PC==0x02), (HL==0x1BBB), (BC==0x1), (F==0x06) ], "CPD (ne)" ],
            [ [ HL(0x1BBC), BC(0x2), M(0x1BBC, 0xFE), A(0xFE) ], [ 0xED, 0xA9 ], 16, [ (PC==0x02), (HL==0x1BBB), (BC==0x1), (F==0x46) ], "CPD (eq)" ],
            [ [ HL(0x1BBC), BC(0x1), M(0x1BBC, 0xFE), A(0x00) ], [ 0xED, 0xA9 ], 16, [ (PC==0x02), (HL==0x1BBB), (BC==0x0), (F==0x02) ], "CPD (ne,last)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_cpdr(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBE), BC(0x3), M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), A(0xCA) ], [ 0xED, 0xB9 ], 37, [ (PC==0x02), (HL==0x1BBC), (BC==0x1), (F==0x46) ], "CPIR (found after 2 cycles)" ],
            [ [ HL(0x1BBE), BC(0x3), M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), A(0xFE) ], [ 0xED, 0xB9 ], 58, [ (PC==0x02), (HL==0x1BBB), (BC==0x0), (F==0x42) ], "CPIR (found after 3 cycles)" ],
            [ [ HL(0x1BBE), BC(0x3), M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), A(0xBA) ], [ 0xED, 0xB9 ], 58, [ (PC==0x02), (HL==0x1BBB), (BC==0x0), (F==0x2A) ], "CPIR (not found after 3 cycles)" ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_add8(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X,Y,f) in [ (0x0A, 0x0B, 0x10),
                         (0x40, 0x51, 0x84),
                         (0xFF, 0x02, 0x15),
                         (0xFF, 0x01, 0x55) ]:
            tests = [
                [ [ A(X), B(Y) ], [ 0x80 ], 4, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD B (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), C(Y) ], [ 0x81 ], 4, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD C (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), D(Y) ], [ 0x82 ], 4, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD D (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), E(Y) ], [ 0x83 ], 4, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD E (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), H(Y) ], [ 0x84 ], 4, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD H (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), L(Y) ], [ 0x85 ], 4, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD L (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC) ], [ 0x86 ], 7, [ (PC==0x01), (A == (X+Y)&0xFF), (F==f) ], "ADD (HL) (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X) ], [ 0xC6, Y ], 7, [ (PC==0x02), (A == (X+Y)&0xFF), (F==f) ], "ADD {:X}H (0x{:X} + 0x{:X})".format(Y,X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0) ], [ 0xDD, 0x86, 0x0C ], 19, [ (PC==0x03), (A == (X+Y)&0xFF), (F==f) ], "ADD (IX+0CH) (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0) ], [ 0xFD, 0x86, 0x0C ], 19, [ (PC==0x03), (A == (X+Y)&0xFF), (F==f) ], "ADD (IY+0CH) (0x{:X} + 0x{:X})".format(X,Y) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for (X,f) in [ (0x0A, 0x10),
                       (0x40, 0x84),
                       (0x81, 0x05),
                       (0x80, 0x45) ]:
            tests = [
                [ [ A(X) ], [ 0x87 ], 4, [ (PC==0x01), (A == (X+X)&0xFF), (F==f) ], "ADD A (0x{:X} + 0x{:X})".format(X,X) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_adc8(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X,Y,f,c) in [ (0x0A, 0x0B, 0x10, 0),
                           (0x0A, 0x0A, 0x10, 1),
                           (0x40, 0x51, 0x84, 0),
                           (0x40, 0x50, 0x84, 1),
                           (0xFF, 0x02, 0x15, 0),
                           (0xFF, 0x01, 0x15, 1),
                           (0xFF, 0x01, 0x55, 0),
                           (0xFF, 0x00, 0x55, 1) ]:
            tests = [
                [ [ A(X), B(Y), F(c) ], [ 0x88 ], 4, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC B (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), C(Y), F(c) ], [ 0x89 ], 4, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC C (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), D(Y), F(c) ], [ 0x8A ], 4, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC D (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), E(Y), F(c) ], [ 0x8B ], 4, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC E (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), H(Y), F(c) ], [ 0x8C ], 4, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC H (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), L(Y), F(c) ], [ 0x8D ], 4, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC L (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC), F(c) ], [ 0x8E ], 7, [ (PC==0x01), (A == (X+Y+c)&0xFF), (F==f) ], "ADC (HL) (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), F(c) ], [ 0xCE, Y ], 7, [ (PC==0x02), (A == (X+Y+c)&0xFF), (F==f) ], "ADC {:X}H (0x{:X} + 0x{:X} + {})".format(Y,X,Y,c) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0), F(c) ], [ 0xDD, 0x8E, 0x0C ], 19, [ (PC==0x03), (A == (X+Y+c)&0xFF), (F==f) ], "ADC (IX+0CH) (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0), F(c) ], [ 0xFD, 0x8E, 0x0C ], 19, [ (PC==0x03), (A == (X+Y+c)&0xFF), (F==f) ], "ADC (IY+0CH) (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for (X,f,c) in [ (0x0A, 0x10,0),
                         (0x0A, 0x10,1),
                         (0x40, 0x84,0),
                         (0x40, 0x84,1),
                         (0x81, 0x05,0),
                         (0x81, 0x05,1),
                         (0x80, 0x45,0),
                         (0x80, 0x05,1)]:
            tests = [
                [ [ A(X), F(c) ], [ 0x8F ], 4, [ (PC==0x01), (A == (X+X+c)&0xFF), (F==f) ], "ADC A (0x{:X} + 0x{:X} + {})".format(X,X,c) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_sub(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X, Y, f) in [ (0x0A, 0xF5, 0x07),
                           (0x40, 0xAF, 0x93),
                           (0xFF, 0xFE, 0x02),
                           (0xFF, 0xFF, 0x42) ]:
            tests = [
                [ [ A(X), B(Y) ], [ 0x90 ], 4, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB B (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), C(Y) ], [ 0x91 ], 4, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB C (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), D(Y) ], [ 0x92 ], 4, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB D (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), E(Y) ], [ 0x93 ], 4, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB E (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), H(Y) ], [ 0x94 ], 4, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB H (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), L(Y) ], [ 0x95 ], 4, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB L (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC) ], [ 0x96 ], 7, [ (PC==0x01), (A == (X-Y)&0xFF), (F==f) ], "SUB (HL) (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X) ], [ 0xD6, Y ], 7, [ (PC==0x02), (A == (X-Y)&0xFF), (F==f) ], "SUB {:X}H (0x{:X} - 0x{:X})".format(Y,X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0) ], [ 0xDD, 0x96, 0x0C ], 19, [ (PC==0x03), (A == (X-Y)&0xFF), (F==f) ], "SUB (IX+0CH) (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0) ], [ 0xFD, 0x96, 0x0C ], 19, [ (PC==0x03), (A == (X-Y)&0xFF), (F==f) ], "SUB (IY+0CH) (0x{:X} - 0x{:X})".format(X,Y) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for X in [ 0x00,
                   0x80,
                   0xFF ]:
            tests = [
                [ [ A(X) ], [ 0x97 ], 4, [ (PC==0x01), (A == 0x00), (F==0x42) ], "SUB A (0x{:X} - 0x{:X})".format(X,X) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_cp(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X, Y, f) in [ (0x0A, 0xF5, 0x07),
                            (0x40, 0xAF, 0x83),
                            (0xFF, 0xFE, 0x02),
                            (0xFF, 0xFF, 0x42) ]:
            tests = [
                [ [ A(X), B(Y) ], [ 0xB8 ], 4, [ (PC==0x01), (A == X), (F==f) ], "CP B (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), C(Y) ], [ 0xB9 ], 4, [ (PC==0x01), (A == X), (F==f) ], "CP C (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), D(Y) ], [ 0xBA ], 4, [ (PC==0x01), (A == X), (F==f) ], "CP D (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), E(Y) ], [ 0xBB ], 4, [ (PC==0x01), (A == X), (F==f) ], "CP E (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), H(Y) ], [ 0xBC ], 4, [ (PC==0x01), (A == X), (F==f) ], "CP H (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), L(Y) ], [ 0xBD ], 4, [ (PC==0x01), (A == X), (F==f) ], "CP L (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC) ], [ 0xBE ], 7, [ (PC==0x01), (A == X), (F==f) ], "CP (HL) (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X) ], [ 0xFE, Y ], 7, [ (PC==0x02), (A == X), (F==f) ], "CP {:X}H (0x{:X} - 0x{:X})".format(Y,X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0) ], [ 0xDD, 0xBE, 0x0C ], 19, [ (PC==0x03), (A == X), (F==f) ], "CP (IX+0CH) (0x{:X} - 0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0) ], [ 0xFD, 0xBE, 0x0C ], 19, [ (PC==0x03), (A == X), (F==f) ], "CP (IY+0CH) (0x{:X} - 0x{:X})".format(X,Y) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for X in [ 0x00,
                   0x80,
                   0xFF ]:
            tests = [
                [ [ A(X) ], [ 0xBF ], 4, [ (PC==0x01), (A == X), (F==0x42) ], "CP A (0x{:X} - 0x{:X})".format(X,X) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_sbc(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X, Y, f, c) in [ (0x0A, 0xF5, 0x07, 0),
                              (0x0A, 0xF5, 0x07, 1),
                              (0x40, 0xAF, 0x93, 0),
                              (0x40, 0xAF, 0x93, 1),
                              (0xFF, 0xFE, 0x02, 0),
                              (0xFF, 0xFE, 0x42, 1),
                              (0xFF, 0xFF, 0x42, 0),
                              (0xFF, 0xFF, 0xBB, 1) ]:
            tests = [
                [ [ A(X), B(Y), F(c) ], [ 0x98 ], 4, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC B (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), C(Y), F(c) ], [ 0x99 ], 4, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC C (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), D(Y), F(c) ], [ 0x9A ], 4, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC D (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), E(Y), F(c) ], [ 0x9B ], 4, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC E (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), H(Y), F(c) ], [ 0x9C ], 4, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC H (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), L(Y), F(c) ], [ 0x9D ], 4, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC L (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC), F(c) ], [ 0x9E ], 7, [ (PC==0x01), (A == (X-Y-c)&0xFF), (F==f) ], "SBC (HL) (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), F(c) ], [ 0xDE, Y ], 7, [ (PC==0x02), (A == (X-Y-c)&0xFF), (F==f) ], "SBC {:X}H (0x{:X} - 0x{:X} - {})".format(Y,X,Y,c) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0), F(c) ], [ 0xDD, 0x9E, 0x0C ], 19, [ (PC==0x03), (A == (X-Y-c)&0xFF), (F==f) ], "SBC (IX+0CH) (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0), F(c) ], [ 0xFD, 0x9E, 0x0C ], 19, [ (PC==0x03), (A == (X-Y-c)&0xFF), (F==f) ], "SBC (IY+0CH) (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for X in [ 0x00,
                   0x80,
                   0xFF ]:
            tests = [
                [ [ A(X), F(0) ], [ 0x9F ], 4, [ (PC==0x01), (A == 0),    (F==0x42) ], "SBC A (0x{:X} - 0x{:X} - 0)".format(X,X) ],
                [ [ A(X), F(1) ], [ 0x9F ], 4, [ (PC==0x01), (A == 0xFF), (F==0xBB) ], "SBC A (0x{:X} - 0x{:X} - 1)".format(X,X) ],
            ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_and(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X,Y, f) in [ (0x11, 0x45, 0x10),
                          (0x0A, 0xFF, 0x1C),
                          (0x0F, 0xF0, 0x54) ]:
            tests = [
                [ [ A(X), B(Y) ], [ 0xA0 ], 4, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND B (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), C(Y) ], [ 0xA1 ], 4, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND C (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), D(Y) ], [ 0xA2 ], 4, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND D (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), E(Y) ], [ 0xA3 ], 4, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND E (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), H(Y) ], [ 0xA4 ], 4, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND H (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), L(Y) ], [ 0xA5 ], 4, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND L (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC) ], [ 0xA6 ], 7, [ (PC==0x01), (A == (X&Y)), (F==f) ], "AND (HL) (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X) ], [ 0xE6, Y ], 7, [ (PC==0x02), (A == (X&Y)), (F==f) ], "AND 0x{:X} (0x{:X}&0x{:X})".format(Y,X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0) ], [ 0xDD, 0xA6, 0x0C ], 19, [ (PC==0x03), (A == (X&Y)), (F==f) ], "AND (IX+0CH) (0x{:X}&0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0) ], [ 0xFD, 0xA6, 0x0C ], 19, [ (PC==0x03), (A == (X&Y)), (F==f) ], "AND (IY+0CH) (0x{:X}&0x{:X})".format(X,Y) ],
                ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for (X, f) in [ (0x11, 0x14),
                        (0x0A, 0x1C), ]:
            tests = [
                [ [ A(X) ], [ 0xA7 ], 4, [ (PC==0x01), (A == X), (F==f) ], "AND A (0x{:X}&0x{:X})".format(X,X) ],
                ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_xor(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X,Y, f) in [ (0x11, 0x45, 0x00),
                          (0x0A, 0xFF, 0xA4),
                          (0x0F, 0xF0, 0xAC) ]:
            tests = [
                [ [ A(X), B(Y) ], [ 0xA8 ], 4, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR B (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), C(Y) ], [ 0xA9 ], 4, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR C (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), D(Y) ], [ 0xAA ], 4, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR D (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), E(Y) ], [ 0xAB ], 4, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR E (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), H(Y) ], [ 0xAC ], 4, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR H (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), L(Y) ], [ 0xAD ], 4, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR L (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC) ], [ 0xAE ], 7, [ (PC==0x01), (A == (X^Y)), (F==f) ], "XOR (HL) (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X) ], [ 0xEE, Y ], 7, [ (PC==0x02), (A == (X^Y)), (F==f) ], "XOR 0x{:X} (0x{:X}^0x{:X})".format(Y,X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0) ], [ 0xDD, 0xAE, 0x0C ], 19, [ (PC==0x03), (A == (X^Y)), (F==f) ], "XOR (IX+0CH) (0x{:X}^0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0) ], [ 0xFD, 0xAE, 0x0C ], 19, [ (PC==0x03), (A == (X^Y)), (F==f) ], "XOR (IY+0CH) (0x{:X}^0x{:X})".format(X,Y) ],
                ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for X in [ 0x11,
                   0x0A, ]:
            tests = [
                [ [ A(X) ], [ 0xAF ], 4, [ (PC==0x01), (A == 0x00), (F==0x44) ], "XOR A (0x{:X}^0x{:X})".format(X,X) ],
                ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_or(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X,Y, f) in [ (0x11, 0x45, 0x04),
                          (0x0A, 0xFF, 0xAC),
                          (0x0F, 0xF0, 0xAC) ]:
            tests = [
                [ [ A(X), B(Y) ], [ 0xB0 ], 4, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR B (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), C(Y) ], [ 0xB1 ], 4, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR C (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), D(Y) ], [ 0xB2 ], 4, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR D (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), E(Y) ], [ 0xB3 ], 4, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR E (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), H(Y) ], [ 0xB4 ], 4, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR H (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), L(Y) ], [ 0xB5 ], 4, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR L (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), HL(0x1BBC) ], [ 0xB6 ], 7, [ (PC==0x01), (A == (X|Y)), (F==f) ], "OR (HL) (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X) ], [ 0xF6, Y ], 7, [ (PC==0x02), (A == (X|Y)), (F==f) ], "OR 0x{:X} (0x{:X}|0x{:X})".format(Y,X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IX(0x1BB0) ], [ 0xDD, 0xB6, 0x0C ], 19, [ (PC==0x03), (A == (X|Y)), (F==f) ], "OR (IX+0CH) (0x{:X}|0x{:X})".format(X,Y) ],
                [ [ A(X), M(0x1BBC,Y), IY(0x1BB0) ], [ 0xFD, 0xB6, 0x0C ], 19, [ (PC==0x03), (A == (X|Y)), (F==f) ], "OR (IY+0CH) (0x{:X}|0x{:X})".format(X,Y) ],
                ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

        for (X, f) in [ (0x11, 0x04),
                        (0x0A, 0x0C), ]:
            tests = [
                [ [ A(X) ], [ 0xB7 ], 4, [ (PC==0x01), (A == X), (F==f) ], "OR A (0x{:X}|0x{:X})".format(X,X) ],
                ]

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)


    def test_inc(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for (X, f) in [ (0x00, 0x00),
                        (0x01, 0x00),
                        (0x0F, 0x10),
                        (0xFF, 0x54),
                        ]:
            tests += [
                [ [ B(X) ], [ 0x04 ], 4, [ (PC==0x01), (B == (X+1)&0xFF), (F==f) ], "INC B (0x{:X} + 1)".format(X) ],
                [ [ C(X) ], [ 0x0C ], 4, [ (PC==0x01), (C == (X+1)&0xFF), (F==f) ], "INC C (0x{:X} + 1)".format(X) ],
                [ [ D(X) ], [ 0x14 ], 4, [ (PC==0x01), (D == (X+1)&0xFF), (F==f) ], "INC D (0x{:X} + 1)".format(X) ],
                [ [ E(X) ], [ 0x1C ], 4, [ (PC==0x01), (E == (X+1)&0xFF), (F==f) ], "INC E (0x{:X} + 1)".format(X) ],
                [ [ H(X) ], [ 0x24 ], 4, [ (PC==0x01), (H == (X+1)&0xFF), (F==f) ], "INC H (0x{:X} + 1)".format(X) ],
                [ [ L(X) ], [ 0x2C ], 4, [ (PC==0x01), (L == (X+1)&0xFF), (F==f) ], "INC L (0x{:X} + 1)".format(X) ],
                [ [ M(0x1BBC,X), HL(0x1BBC) ], [ 0x34 ], 12, [ (PC==0x01), (M[0x1BBC] == (X+1)&0xFF), (F==f) ], "INC (HL) (0x{:X} + 1)".format(X) ],
                [ [ A(X) ], [ 0x3C ], 4, [ (PC==0x01), (A == (X+1)&0xFF), (F==f) ], "INC A (0x{:X} + 1)".format(X) ],
                [ [ M(0x1BBC,X), IX(0x1BB0) ], [ 0xDD, 0x34, 0x0C ], 23, [ (PC==0x03), (M[0x1BBC] == (X+1)&0xFF), (F==f) ], "INC (IX+0CH) (0x{:X} + 1)".format(X) ],
                [ [ M(0x1BBC,X), IY(0x1BB0) ], [ 0xFD, 0x34, 0x0C ], 23, [ (PC==0x03), (M[0x1BBC] == (X+1)&0xFF), (F==f) ], "INC (IY+0CH) (0x{:X} + 1)".format(X) ],
                ]

        for X in [ 0x0000,
                   0x0001,
                   0x00FF,
                   0x0100,
                   0xFF00,
                   0xFFFF ]:
            tests += [
                [ [ BC(X) ], [ 0x03 ], 4, [ (PC==0x01), (BC == (X+1)&0xFFFF) ], "INC BC (0x{:X} + 1)".format(X) ],
                [ [ DE(X) ], [ 0x13 ], 4, [ (PC==0x01), (DE == (X+1)&0xFFFF) ], "INC DE (0x{:X} + 1)".format(X) ],
                [ [ HL(X) ], [ 0x23 ], 4, [ (PC==0x01), (HL == (X+1)&0xFFFF) ], "INC HL (0x{:X} + 1)".format(X) ],
                [ [ SP(X) ], [ 0x33 ], 4, [ (PC==0x01), (SP == (X+1)&0xFFFF) ], "INC SP (0x{:X} + 1)".format(X) ],
                [ [ IX(X) ], [ 0xDD, 0x23 ], 8, [ (PC==0x02), (IX == (X+1)&0xFFFF) ], "INC IX (0x{:X} + 1)".format(X) ],
                [ [ IY(X) ], [ 0xFD, 0x23 ], 8, [ (PC==0x02), (IY == (X+1)&0xFFFF) ], "INC IY (0x{:X} + 1)".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_dec(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for (X, f) in [ (0x00, 0xBA),
                        (0x01, 0x42),
                        (0x02, 0x02),
                        (0x10, 0x1A),
                        ]:
            tests += [
                [ [ B(X) ], [ 0x05 ], 4, [ (PC==0x01), (B == (X-1)&0xFF), (F==f) ], "DEC B (0x{:X} - 1)".format(X) ],
                [ [ C(X) ], [ 0x0D ], 4, [ (PC==0x01), (C == (X-1)&0xFF), (F==f) ], "DEC C (0x{:X} - 1)".format(X) ],
                [ [ D(X) ], [ 0x15 ], 4, [ (PC==0x01), (D == (X-1)&0xFF), (F==f) ], "DEC D (0x{:X} - 1)".format(X) ],
                [ [ E(X) ], [ 0x1D ], 4, [ (PC==0x01), (E == (X-1)&0xFF), (F==f) ], "DEC E (0x{:X} - 1)".format(X) ],
                [ [ H(X) ], [ 0x25 ], 4, [ (PC==0x01), (H == (X-1)&0xFF), (F==f) ], "DEC H (0x{:X} - 1)".format(X) ],
                [ [ L(X) ], [ 0x2D ], 4, [ (PC==0x01), (L == (X-1)&0xFF), (F==f) ], "DEC L (0x{:X} - 1)".format(X) ],
                [ [ M(0x1BBC,X), HL(0x1BBC) ], [ 0x35 ], 12, [ (PC==0x01), (M[0x1BBC] == (X-1)&0xFF), (F==f) ], "DEC (HL) (0x{:X} - 1)".format(X) ],
                [ [ A(X) ], [ 0x3D ], 4, [ (PC==0x01), (A == (X-1)&0xFF), (F==f) ], "DEC A (0x{:X} - 1)".format(X) ],
                [ [ M(0x1BBC,X), IX(0x1BB0) ], [ 0xDD, 0x35, 0x0C ], 23, [ (PC==0x03), (M[0x1BBC] == (X-1)&0xFF), (F==f) ], "DEC (IX+0CH) (0x{:X} - 1)".format(X) ],
                [ [ M(0x1BBC,X), IY(0x1BB0) ], [ 0xFD, 0x35, 0x0C ], 23, [ (PC==0x03), (M[0x1BBC] == (X-1)&0xFF), (F==f) ], "DEC (IY+0CH) (0x{:X} - 1)".format(X) ],
                ]

        for X in [ 0x0000,
                    0x0001,
                    0x00FF,
                    0x0100,
                    0xFF00,
                    0xFFFF ]:
            tests += [
                [ [ BC(X) ], [ 0x0B ], 4, [ (PC==0x01), (BC == (X-1)&0xFFFF) ], "DEC BC (0x{:X} - 1)".format(X) ],
                [ [ DE(X) ], [ 0x1B ], 4, [ (PC==0x01), (DE == (X-1)&0xFFFF) ], "DEC DE (0x{:X} - 1)".format(X) ],
                [ [ HL(X) ], [ 0x2B ], 4, [ (PC==0x01), (HL == (X-1)&0xFFFF) ], "DEC HL (0x{:X} - 1)".format(X) ],
                [ [ SP(X) ], [ 0x3B ], 4, [ (PC==0x01), (SP == (X-1)&0xFFFF) ], "DEC SP (0x{:X} - 1)".format(X) ],
                [ [ IX(X) ], [ 0xDD, 0x2B ], 8, [ (PC==0x02), (IX == (X-1)&0xFFFF) ], "DEC IX (0x{:X} - 1)".format(X) ],
                [ [ IY(X) ], [ 0xFD, 0x2B ], 8, [ (PC==0x02), (IY == (X-1)&0xFFFF) ], "DEC IY (0x{:X} - 1)".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_daa(self):
        def bcd(n):
            return (((int(n/10)%10) << 4) + (n%10))&0xFF
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for x in range(0,100):
            for y in range(0,100):
                X = bcd(x)
                Y = bcd(y)
                h = 1 if ((x%10) + (y%10)) > 0xF else 0
                h_ = 1 if ((x%10) - (y%10)) < 0 else 0
                c = 1 if (X + Y) > 0xFF else 0
                c_ = 1 if (X - Y) < 0 else 0
                tests += [
                    [ [ A((X + Y)&0xFF), F((h << 4) + c) ],          [ 0x27 ], 4, [ (PC==0x01), (A == bcd(x+y)) ], "DAA (after {} + {})".format(x,y) ],
                    [ [ A((X - Y)&0xFF), F((h_ << 4) + c_ + 0x02) ], [ 0x27 ], 4, [ (PC==0x01), (A == bcd(x-y)) ], "DAA (after {} - {})".format(x,y) ],
                ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_cpl(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for X in range(0,256):
            tests += [
                [ [ A(X) ], [ 0x2F ], 4, [ (PC==0x01), (A == (~X)&0xFF) ], "CPL (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_neg(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for X in range(0,256):
            tests += [
                [ [ A(X) ], [ 0xED, 0x44 ], 8, [ (PC==0x02), (A == (256 - X)&0xFF) ], "NEG (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ccf(self):
        def ccf(x):
            if x&0x01:
                x &= 0xFE
            else:
                x |= 0x01
            if x&0x10:
                x &= 0xEF
            else:
                x |= 0x10
            x &= 0xFD
            return x
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for X in range(0,256):
            tests += [
                [ [ F(X) ], [ 0x3F ], 4, [ (PC==0x01), (F == ccf(X)) ], "CCF (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_scf(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for X in range(0,256):
            for Y in [ (1 << n) | (1 << m) for n,m in zip(range(0,8), range(0,8)) ]:
                tests += [
                    [ [ F(X), A(Y) ], [ 0x37 ], 4, [ (PC==0x01), (F == ((X&0xC4) | (Y&0x28) | 0x01)) ], "SCF (of 0x{:X})".format(X) ],
                ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_add16(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for (X,Y,f) in [ (0x000A, 0x000B, 0x00),
                         (0x0040, 0x0051, 0x00),
                         (0x00FF, 0x0002, 0x00),
                         (0x00FF, 0x0001, 0x00),
                         (0x0100, 0x0001, 0x00),
                         (0xFF00, 0x0100, 0x11),
                         (0xFFFF, 0x0001, 0x11),
                         ]:
            tests += [
                [ [ BC(X), HL(Y) ], [ 0x09 ],       11, [ (PC==0x01), (HL == (X+Y)&0xFFFF), (F==f) ], "ADD HL,BC (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ DE(X), HL(Y) ], [ 0x19 ],       11, [ (PC==0x01), (HL == (X+Y)&0xFFFF), (F==f) ], "ADD HL,DE (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ SP(X), HL(Y) ], [ 0x39 ],       11, [ (PC==0x01), (HL == (X+Y)&0xFFFF), (F==f) ], "ADD HL,SP (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ BC(X), IX(Y) ], [ 0xDD, 0x09 ], 15, [ (PC==0x02), (IX == (X+Y)&0xFFFF), (F==f) ], "ADD IX,BC (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ DE(X), IX(Y) ], [ 0xDD, 0x19 ], 15, [ (PC==0x02), (IX == (X+Y)&0xFFFF), (F==f) ], "ADD IX,DE (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ SP(X), IX(Y) ], [ 0xDD, 0x39 ], 15, [ (PC==0x02), (IX == (X+Y)&0xFFFF), (F==f) ], "ADD IX,SP (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ BC(X), IY(Y) ], [ 0xFD, 0x09 ], 15, [ (PC==0x02), (IY == (X+Y)&0xFFFF), (F==f) ], "ADD IY,BC (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ DE(X), IY(Y) ], [ 0xFD, 0x19 ], 15, [ (PC==0x02), (IY == (X+Y)&0xFFFF), (F==f) ], "ADD IY,DE (0x{:X} + 0x{:X})".format(X,Y) ],
                [ [ SP(X), IY(Y) ], [ 0xFD, 0x39 ], 15, [ (PC==0x02), (IY == (X+Y)&0xFFFF), (F==f) ], "ADD IY,SP (0x{:X} + 0x{:X})".format(X,Y) ],
            ]

        for (X,f) in [ (0x000A, 0x00),
                       (0x0040, 0x00),
                       (0x00FF, 0x00),
                       (0x0100, 0x00),
                       (0xFF00, 0x39),
                       (0xFFFF, 0x39) ]:
            tests += [
                [ [ HL(X) ], [ 0x29 ],       11, [ (PC==0x01), (HL == (X+X)&0xFFFF), (F==f) ], "ADD HL,HL (0x{:X} + 0x{:X})".format(X,X) ],
                [ [ IX(X) ], [ 0xDD, 0x29 ], 15, [ (PC==0x02), (IX == (X+X)&0xFFFF), (F==f) ], "ADD IX,IX (0x{:X} + 0x{:X})".format(X,X) ],
                [ [ IY(X) ], [ 0xFD, 0x29 ], 15, [ (PC==0x02), (IY == (X+X)&0xFFFF), (F==f) ], "ADD IY,IY (0x{:X} + 0x{:X})".format(X,X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_adc16(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for (X,Y,c,f) in [ (0x000A, 0x000B, 0, 0x00),
                           (0x0040, 0x0051, 0, 0x00),
                           (0x00FF, 0x0002, 0, 0x00),
                           (0x00FF, 0x0001, 0, 0x00),
                           (0x0100, 0x0001, 0, 0x00),
                           (0xFF00, 0x0100, 0, 0x55),
                           (0xFFFF, 0x0001, 0, 0x55),
                           (0x000A, 0x000A, 1, 0x00),
                           (0x0040, 0x0050, 1, 0x00),
                           (0x00FF, 0x0001, 1, 0x00),
                           (0x00FF, 0x0000, 1, 0x00),
                           (0x0100, 0x0000, 1, 0x00),
                           (0xFF00, 0x00FF, 1, 0x55),
                           (0xFFFF, 0x0000, 1, 0x55),
                         ]:
            tests += [
                [ [ BC(X), HL(Y), F(c) ], [ 0xED, 0x4A ], 15, [ (PC==0x02), (HL == (X+Y+c)&0xFFFF), (F==f) ], "ADC HL,BC (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ DE(X), HL(Y), F(c) ], [ 0xED, 0x5A ], 15, [ (PC==0x02), (HL == (X+Y+c)&0xFFFF), (F==f) ], "ADC HL,DE (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
                [ [ SP(X), HL(Y), F(c) ], [ 0xED, 0x7A ], 15, [ (PC==0x02), (HL == (X+Y+c)&0xFFFF), (F==f) ], "ADC HL,SP (0x{:X} + 0x{:X} + {})".format(X,Y,c) ],
            ]

        for (X,c,f) in [ (0x000A, 0, 0x00),
                         (0x0040, 0, 0x00),
                         (0x00FF, 0, 0x00),
                         (0x0100, 0, 0x00),
                         (0xFF00, 0, 0xBD),
                         (0xFFFF, 0, 0xBD),
                         (0x000A, 1, 0x00),
                         (0x0040, 1, 0x00),
                         (0x00FF, 1, 0x00),
                         (0x0100, 1, 0x00),
                         (0xFF00, 1, 0xBD),
                         (0xFFFF, 1, 0xBD)]:
            tests += [
                [ [ HL(X), F(c) ], [ 0xED, 0x6A ], 15, [ (PC==0x02), (HL == (X+X+c)&0xFFFF), (F==f) ], "ADC HL,HL (0x{:X} + 0x{:X} + {})".format(X,X,c) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_sbc16(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = []
        for (X,Y,c,f) in [ (0x000A, 0x000B, 0, 0xAE),
                           (0x0040, 0x0051, 0, 0xAE),
                           (0x00FF, 0x0002, 0, 0x17),
                           (0x00FF, 0x0001, 0, 0x17),
                           (0x0100, 0x0001, 0, 0x17),
                           (0xFF00, 0x0100, 0, 0xBF),
                           (0xFFFF, 0x0001, 0, 0xBF),
                           (0x000A, 0x000A, 1, 0xAE),
                           (0x0040, 0x0050, 1, 0xAE),
                           (0x00FF, 0x0001, 1, 0x17),
                           (0x00FF, 0x0000, 1, 0x02),
                           (0x0100, 0x0000, 1, 0x02),
                           (0xFF00, 0x00FF, 1, 0xBF),
                           (0xFFFF, 0x0000, 1, 0xAE),
                         ]:
            tests += [
                [ [ BC(Y), HL(X), F(c) ], [ 0xED, 0x42 ], 15, [ (PC==0x02), (HL == (X-Y-c)&0xFFFF), (F==f) ], "SBC HL,BC (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ DE(Y), HL(X), F(c) ], [ 0xED, 0x52 ], 15, [ (PC==0x02), (HL == (X-Y-c)&0xFFFF), (F==f) ], "SBC HL,DE (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
                [ [ SP(Y), HL(X), F(c) ], [ 0xED, 0x72 ], 15, [ (PC==0x02), (HL == (X-Y-c)&0xFFFF), (F==f) ], "SBC HL,SP (0x{:X} - 0x{:X} - {})".format(X,Y,c) ],
            ]

        for (X,c,f) in [ (0x000A, 0, 0x57),
                         (0x0040, 0, 0x57),
                         (0x00FF, 0, 0x57),
                         (0x0100, 0, 0x57),
                         (0xFF00, 0, 0x57),
                         (0xFFFF, 0, 0x57),
                         (0x000A, 1, 0xAE),
                         (0x0040, 1, 0xAE),
                         (0x00FF, 1, 0xAE),
                         (0x0100, 1, 0xAE),
                         (0xFF00, 1, 0xAE),
                         (0xFFFF, 1, 0xAE)]:
            tests += [
                [ [ HL(X), F(c) ], [ 0xED, 0x62 ], 15, [ (PC==0x02), (HL == (-c)&0xFFFF), (F==f) ], "SBC HL,HL (0x{:X} - 0x{:X} - {})".format(X,X,c) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rlca(self):
        tests = []
        for (X,f) in [  (0x00, 0x00),
                        (0x01, 0x00),
                        (0x80, 0x01),
                        (0xF0, 0x21),
                        (0xFF, 0x29),
                        (0x7F, 0x28)
                    ]:
            tests += [
                [ [ A(X) ], [ 0x07 ], 4, [ (A == ((X << 1) + (X >> 7))&0xFF), (F == f) ], "RLCA (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rrca(self):
        tests = []
        for (X,f) in [  (0x00, 0x00),
                        (0x01, 0x01),
                        (0x80, 0x00),
                        (0xF0, 0x28),
                        (0xFF, 0x29),
                        (0x7F, 0x29)
                    ]:
            tests += [
                [ [ A(X) ], [ 0x0F ], 4, [ (A == ((X >> 1) + ((X&0x1) << 7))&0xFF), (F == f) ], "RRCA (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rla(self):
        tests = []
        for (X,c,f) in [(0x00, 0, 0x00),
                        (0x00, 1, 0x00),
                        (0x01, 0, 0x00),
                        (0x01, 1, 0x00),
                        (0x80, 0, 0x01),
                        (0x80, 1, 0x01),
                        (0xF0, 0, 0x21),
                        (0xF0, 1, 0x21),
                        (0xFF, 0, 0x29),
                        (0xFF, 1, 0x29),
                        (0x7F, 0, 0x28),
                        (0x7F, 1, 0x28)
                    ]:
            tests += [
                [ [ A(X), F(c) ], [ 0x17 ], 4, [ (A == ((X << 1) + c)&0xFF), (F == f) ], "RLA (of 0x{:X} with C={})".format(X,c) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rra(self):
        tests = []
        for (X,c,f) in [(0x00, 0, 0x00),
                        (0x00, 1, 0x00),
                        (0x01, 0, 0x01),
                        (0x01, 1, 0x01),
                        (0x80, 0, 0x00),
                        (0x80, 1, 0x00),
                        (0xF0, 0, 0x28),
                        (0xF0, 1, 0x28),
                        (0xFF, 0, 0x29),
                        (0xFF, 1, 0x29),
                        (0x7F, 0, 0x29),
                        (0x7F, 1, 0x29)
                    ]:
            tests += [
                [ [ A(X), F(c) ], [ 0x1F ], 4, [ (A == ((X >> 1) + (c << 7))&0xFF), (F == f) ], "RRA (of 0x{:X} with C={})".format(X,c) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rlc(self):
        tests = []
        for (X,f) in [  (0x00, 0x00),
                            (0x01, 0x00),
                            (0x80, 0x01),
                            (0xF0, 0x21),
                            (0xFF, 0x29),
                            (0x7F, 0x28) ]:
            for (r,i) in [ ('B', 0x00),
                        ('C', 0x01),
                        ('D', 0x02),
                        ('E', 0x03),
                        ('H', 0x04),
                        ('L', 0x05),
                        ('A', 0x07) ]:
                tests += [
                    [ [ set_register_to(r,X) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X << 1) + (X >> 7))&0xFF), (F == f) ], "RLC {} (of 0x{:X})".format(r,X) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC) ], [ 0xCB, 0x06 ], 15, [ (M[0x1BBC] == ((X << 1) + (X >> 7))&0xFF), (F == f) ], "RLC (HL) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IX(0x1BB0) ], [ 0xDD, 0xCB, 0x0C, 0x06 ], 23, [ (M[0x1BBC] == ((X << 1) + (X >> 7))&0xFF), (F == f) ], "RLC (IX+0CH) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IY(0x1BB0) ], [ 0xFD, 0xCB, 0x0C, 0x06 ], 23, [ (M[0x1BBC] == ((X << 1) + (X >> 7))&0xFF), (F == f) ], "RLC (IY+0CH) (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rrc(self):
        tests = []
        for (X,f) in [  (0x00, 0x00),
                        (0x01, 0x01),
                        (0x80, 0x00),
                        (0xF0, 0x28),
                        (0xFF, 0x29),
                        (0x7F, 0x29) ]:
            for (r,i) in [ ('B', 0x08),
                           ('C', 0x09),
                           ('D', 0x0A),
                           ('E', 0x0B),
                           ('H', 0x0C),
                           ('L', 0x0D),
                           ('A', 0x0F) ]:
                tests += [
                    [ [ set_register_to(r,X) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X >> 1) + (X << 7))&0xFF), (F == f) ], "RRC {} (of 0x{:X})".format(r,X) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC) ], [ 0xCB, 0x0E ], 15, [ (M[0x1BBC] == ((X >> 1) + (X << 7))&0xFF), (F == f) ], "RRC (HL) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IX(0x1BB0) ], [ 0xDD, 0xCB, 0x0C, 0x0E ], 23, [ (M[0x1BBC] == ((X >> 1) + (X << 7))&0xFF), (F == f) ], "RRC (IX+0CH) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IY(0x1BB0) ], [ 0xFD, 0xCB, 0x0C, 0x0E ], 23, [ (M[0x1BBC] == ((X >> 1) + (X << 7))&0xFF), (F == f) ], "RRC (IY+0CH) (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rl(self):
        tests = []
        for (X,c,f) in [(0x00, 0, 0x00),
                        (0x00, 1, 0x00),
                        (0x01, 0, 0x00),
                        (0x01, 1, 0x00),
                        (0x80, 0, 0x01),
                        (0x80, 1, 0x01),
                        (0xF0, 0, 0x21),
                        (0xF0, 1, 0x21),
                        (0xFF, 0, 0x29),
                        (0xFF, 1, 0x29),
                        (0x7F, 0, 0x28),
                        (0x7F, 1, 0x28)
                    ]:
            for (r,i) in [ ('B', 0x10),
                           ('C', 0x11),
                           ('D', 0x12),
                           ('E', 0x13),
                           ('H', 0x14),
                           ('L', 0x15),
                           ('A', 0x17) ]:
                tests += [
                    [ [ set_register_to(r,X), F(c) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X << 1) + c)&0xFF), (F == f) ], "RL {} (of 0x{:X} with C={})".format(r,X,c) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC), F(c) ], [ 0xCB, 0x16 ], 15, [ (M[0x1BBC] == ((X << 1) + c)&0xFF), (F == f) ], "RL (HL) (of 0x{:X} with C={})".format(X,c) ],
                [ [ M(0x1BBC, X), IX(0x1BB0), F(c) ], [ 0xDD, 0xCB, 0x0C, 0x16 ], 23, [ (M[0x1BBC] == ((X << 1) + c)&0xFF), (F == f) ], "RL (IX+0CH) (of 0x{:X} with C={})".format(X,c) ],
                [ [ M(0x1BBC, X), IY(0x1BB0), F(c) ], [ 0xFD, 0xCB, 0x0C, 0x16 ], 23, [ (M[0x1BBC] == ((X << 1) + c)&0xFF), (F == f) ], "RL (IY+0CH) (of 0x{:X} with C={})".format(X,c) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rr(self):
        tests = []
        for (X,c,f) in [(0x00, 0, 0x00),
                        (0x00, 1, 0x00),
                        (0x01, 0, 0x01),
                        (0x01, 1, 0x01),
                        (0x80, 0, 0x00),
                        (0x80, 1, 0x00),
                        (0xF0, 0, 0x28),
                        (0xF0, 1, 0x28),
                        (0xFF, 0, 0x29),
                        (0xFF, 1, 0x29),
                        (0x7F, 0, 0x29),
                        (0x7F, 1, 0x29)
                    ]:
            for (r,i) in [ ('B', 0x18),
                           ('C', 0x19),
                           ('D', 0x1A),
                           ('E', 0x1B),
                           ('H', 0x1C),
                           ('L', 0x1D),
                           ('A', 0x1F) ]:
                tests += [
                    [ [ set_register_to(r,X), F(c) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X >> 1) + (c << 7))&0xFF), (F == f) ], "RR {} (of 0x{:X} with C={})".format(r,X,c) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC), F(c) ], [ 0xCB, 0x1E ], 15, [ (M[0x1BBC] == ((X >> 1) + (c << 7))&0xFF), (F == f) ], "RR (HL) (of 0x{:X} with C={})".format(X,c) ],
                [ [ M(0x1BBC, X), IX(0x1BB0), F(c) ], [ 0xDD, 0xCB, 0x0C, 0x1E ], 23, [ (M[0x1BBC] == ((X >> 1) + (c << 7))&0xFF), (F == f) ], "RR (IX+0CH) (of 0x{:X} with C={})".format(X,c) ],
                [ [ M(0x1BBC, X), IY(0x1BB0), F(c) ], [ 0xFD, 0xCB, 0x0C, 0x1E ], 23, [ (M[0x1BBC] == ((X >> 1) + (c << 7))&0xFF), (F == f) ], "RR (IY+0CH) (of 0x{:X} with C={})".format(X,c) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_sla(self):
        tests = []
        for (X,f) in [(0x00, 0x00),
                      (0x01, 0x00),
                      (0x80, 0x01),
                      (0xF0, 0x21),
                      (0xFF, 0x29),
                      (0x7F, 0x28), ]:
            for (r,i) in [ ('B', 0x20),
                           ('C', 0x21),
                           ('D', 0x22),
                           ('E', 0x23),
                           ('H', 0x24),
                           ('L', 0x25),
                           ('A', 0x27) ]:
                tests += [
                    [ [ set_register_to(r,X) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X << 1))&0xFF), (F == f) ], "SLA {} (of 0x{:X})".format(r,X) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC) ], [ 0xCB, 0x26 ],             15, [ (M[0x1BBC] == (X << 1)&0xFF), (F == f) ], "SLA (HL) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IX(0x1BB0) ], [ 0xDD, 0xCB, 0x0C, 0x26 ], 23, [ (M[0x1BBC] == (X << 1)&0xFF), (F == f) ], "SLA (IX+0CH) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IY(0x1BB0) ], [ 0xFD, 0xCB, 0x0C, 0x26 ], 23, [ (M[0x1BBC] == (X << 1)&0xFF), (F == f) ], "SLA (IY+0CH) (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_sra(self):
        tests = []
        for (X,f) in [(0x00, 0x00),
                      (0x01, 0x01),
                      (0x80, 0x00),
                      (0xF0, 0x28),
                      (0xFF, 0x29),
                      (0x7F, 0x29) ]:
            for (r,i) in [ ('B', 0x28),
                           ('C', 0x29),
                           ('D', 0x2A),
                           ('E', 0x2B),
                           ('H', 0x2C),
                           ('L', 0x2D),
                           ('A', 0x2F) ]:
                tests += [
                    [ [ set_register_to(r,X) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X >> 1) | (X&0x80))&0xFF), (F == f) ], "SRA {} (of 0x{:X})".format(r,X) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC) ], [ 0xCB, 0x2E ],             15, [ (M[0x1BBC] == ((X >> 1) | (X&0x80))&0xFF), (F == f) ], "SRA (HL) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IX(0x1BB0) ], [ 0xDD, 0xCB, 0x0C, 0x2E ], 23, [ (M[0x1BBC] == ((X >> 1) | (X&0x80))&0xFF), (F == f) ], "SRA (IX+0CH) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IY(0x1BB0) ], [ 0xFD, 0xCB, 0x0C, 0x2E ], 23, [ (M[0x1BBC] == ((X >> 1) | (X&0x80))&0xFF), (F == f) ], "SRA (IY+0CH) (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_sl1(self):
        tests = []
        for (X,f) in [(0x00, 0x00),
                      (0x01, 0x00),
                      (0x80, 0x01),
                      (0xF0, 0x21),
                      (0xFF, 0x29),
                      (0x7F, 0x28), ]:
            for (r,i) in [ ('B', 0x30),
                           ('C', 0x31),
                           ('D', 0x32),
                           ('E', 0x33),
                           ('H', 0x34),
                           ('L', 0x35),
                           ('A', 0x37) ]:
                tests += [
                    [ [ set_register_to(r,X) ], [ 0xCB, i ], 8, [ expect_register_equal(r, ((X << 1) + 1)&0xFF), (F == f) ], "SL1 {} (of 0x{:X})".format(r,X) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC) ], [ 0xCB, 0x36 ],             15, [ (M[0x1BBC] == ((X << 1) + 1)&0xFF), (F == f) ], "SL1 (HL) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IX(0x1BB0) ], [ 0xDD, 0xCB, 0x0C, 0x36 ], 23, [ (M[0x1BBC] == ((X << 1) + 1)&0xFF), (F == f) ], "SL1 (IX+0CH) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IY(0x1BB0) ], [ 0xFD, 0xCB, 0x0C, 0x36 ], 23, [ (M[0x1BBC] == ((X << 1) + 1)&0xFF), (F == f) ], "SL1 (IY+0CH) (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_srl(self):
        tests = []
        for (X,f) in [(0x00, 0x00),
                      (0x01, 0x01),
                      (0x80, 0x00),
                      (0xF0, 0x28),
                      (0xFF, 0x29),
                      (0x7F, 0x29) ]:
            for (r,i) in [ ('B', 0x38),
                           ('C', 0x39),
                           ('D', 0x3A),
                           ('E', 0x3B),
                           ('H', 0x3C),
                           ('L', 0x3D),
                           ('A', 0x3F) ]:
                tests += [
                    [ [ set_register_to(r,X) ], [ 0xCB, i ], 8, [ expect_register_equal(r, (X >> 1)), (F == f) ], "SRL {} (of 0x{:X})".format(r,X) ],
                ]
            tests += [
                [ [ M(0x1BBC, X), HL(0x1BBC) ], [ 0xCB, 0x3E ],             15, [ (M[0x1BBC] == (X >> 1)&0xFF), (F == f) ], "SRL (HL) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IX(0x1BB0) ], [ 0xDD, 0xCB, 0x0C, 0x3E ], 23, [ (M[0x1BBC] == (X >> 1)&0xFF), (F == f) ], "SRL (IX+0CH) (of 0x{:X})".format(X) ],
                [ [ M(0x1BBC, X), IY(0x1BB0) ], [ 0xFD, 0xCB, 0x0C, 0x3E ], 23, [ (M[0x1BBC] == (X >> 1)&0xFF), (F == f) ], "SRL (IY+0CH) (of 0x{:X})".format(X) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rld(self):
        tests = [
            [ [ A(0xF1), M(0x1BBC,0x23), HL(0x1BBC) ], [ 0xED, 0x6F ], 18, [ (A == 0x02), (M[0x1BBC] == 0x31), (F == 0x00) ], "RLD (of 0xF1 and 0x23)".format() ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rrd(self):
        tests = [
            [ [ A(0xF1), M(0x1BBC,0x23), HL(0x1BBC) ], [ 0xED, 0x67 ], 18, [ (A == 0x03), (M[0x1BBC] == 0x12), (F == 0x04) ], "RRD (of 0xF1 and 0x23)".format() ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_bit(self):
        tests = []
        for X in range(0,256):
            for b in range(0,8):
                f = ((1 - ((X >> b)&0x1))*0x44) + 0x10 + ((X&(1 << b))&0xA8)
                for (reg, r) in [ ('B', 0x0), ('C', 0x1), ('D',0x2), ('E',0x3), ('H',0x4), ('L',0x5), ('A',0x7) ]:
                    i = 0x40 + (b << 3) + r
                    tests += [
                        [ [ set_register_to(reg,X) ], [ 0xCB, i ], 8, [ expect_register_equal(reg, X), (F == f) ], "BIT {},{} (of 0x{:X})".format(b,reg,X) ],
                    ]

                tests += [
                    [ [ HL(0x1BBC), M(0x1BBC, X) ], [ 0xCB, (0x46 + (b << 3)) ], 12, [ (M[0x1BBC] == X), (F == f) ], "BIT {},(HL) (of 0x{:X})".format(b,X) ],
                    [ [ IX(0x1BB0), M(0x1BBC, X) ], [ 0xDD, 0xCB, 0xC, (0x46 + (b << 3)) ], 20, [ (M[0x1BBC] == X), (F == f) ], "BIT {},(IX+0C) (of 0x{:X})".format(b,X) ],
                    [ [ IY(0x1BB0), M(0x1BBC, X) ], [ 0xFD, 0xCB, 0xC, (0x46 + (b << 3)) ], 20, [ (M[0x1BBC] == X), (F == f) ], "BIT {},(IY+0C) (of 0x{:X})".format(b,X) ],
                ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_res(self):
        tests = []
        for b in range(0,8):
            for (reg, r) in [ ('B', 0x0), ('C', 0x1), ('D',0x2), ('E',0x3), ('H',0x4), ('L',0x5), ('A',0x7) ]:
                i = 0x80 + (b << 3) + r
                tests += [
                    [ [ set_register_to(reg,0xFF) ], [ 0xCB, i ], 8, [ expect_register_equal(reg, 0xFF - (1 << b)) ], "RES {},{}".format(b,reg) ],
                ]

            tests += [
                [ [ HL(0x1BBC), M(0x1BBC, 0xFF) ], [ 0xCB, (0x86 + (b << 3)) ], 15, [ (M[0x1BBC] == (0xFF - (1 << b))) ], "RES {},(HL)".format(b) ],
                [ [ IX(0x1BB0), M(0x1BBC, 0xFF) ], [ 0xDD, 0xCB, 0xC, (0x86 + (b << 3)) ], 23, [ (M[0x1BBC] == (0xFF - (1 << b))) ], "RES {},(IX+0C)".format(b) ],
                [ [ IY(0x1BB0), M(0x1BBC, 0xFF) ], [ 0xFD, 0xCB, 0xC, (0x86 + (b << 3)) ], 23, [ (M[0x1BBC] == (0xFF - (1 << b))) ], "RES {},(IY+0C)".format(b) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_set(self):
        tests = []
        for b in range(0,8):
            for (reg, r) in [ ('B', 0x0), ('C', 0x1), ('D',0x2), ('E',0x3), ('H',0x4), ('L',0x5), ('A',0x7) ]:
                i = 0xC0 + (b << 3) + r
                tests += [
                    [ [ set_register_to(reg,0x00) ], [ 0xCB, i ], 8, [ expect_register_equal(reg, (1 << b)) ], "SET {},{}".format(b,reg) ],
                ]

            tests += [
                [ [ HL(0x1BBC), M(0x1BBC, 0x00) ], [ 0xCB, (0xC6 + (b << 3)) ], 15, [ (M[0x1BBC] == (1 << b)) ], "SET {},(HL)".format(b) ],
                [ [ IX(0x1BB0), M(0x1BBC, 0x00) ], [ 0xDD, 0xCB, 0xC, (0xC6 + (b << 3)) ], 23, [ (M[0x1BBC] == (1 << b)) ], "SET {},(IX+0C)".format(b) ],
                [ [ IY(0x1BB0), M(0x1BBC, 0x00) ], [ 0xFD, 0xCB, 0xC, (0xC6 + (b << 3)) ], 23, [ (M[0x1BBC] == (1 << b)) ], "SET {},(IY+0C)".format(b) ],
            ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_jp(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [],             [ 0xC3, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP 01BBCH" ],
            [ [ F(0x00) ],    [ 0xDA, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP C,01BBCH (no jump)" ],
            [ [ F(0x01) ],    [ 0xDA, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP C,01BBCH (jump)" ],
            [ [ F(0x01) ],    [ 0xD2, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP NC,01BBCH (no jump)" ],
            [ [ F(0x00) ],    [ 0xD2, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP NC,01BBCH (jump)" ],
            [ [ F(0x00) ],    [ 0xCA, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP Z,01BBCH (no jump)" ],
            [ [ F(0x40) ],    [ 0xCA, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP Z,01BBCH (jump)" ],
            [ [ F(0x40) ],    [ 0xC2, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP NZ,01BBCH (no jump)" ],
            [ [ F(0x00) ],    [ 0xC2, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP NZ,01BBCH (jump)" ],
            [ [ F(0x00) ],    [ 0xEA, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP PE,01BBCH (no jump)" ],
            [ [ F(0x04) ],    [ 0xEA, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP PE,01BBCH (jump)" ],
            [ [ F(0x04) ],    [ 0xE2, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP PO,01BBCH (no jump)" ],
            [ [ F(0x00) ],    [ 0xE2, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP PO,01BBCH (jump)" ],
            [ [ F(0x00) ],    [ 0xFA, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP M,01BBCH (no jump)" ],
            [ [ F(0x80) ],    [ 0xFA, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP M,01BBCH (jump)" ],
            [ [ F(0x80) ],    [ 0xF2, 0xBC, 0x1B ], 10, [ (PC == 0x0003) ], "JP P,01BBCH (no jump)" ],
            [ [ F(0x00) ],    [ 0xF2, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "JP P,01BBCH (jump)" ],
            [ [ HL(0x1BBC) ], [ 0xE9 ],              4, [ (PC == 0x1BBC) ], "JP (HL)" ],
            [ [ IX(0x1BBC) ], [ 0xDD, 0xE9 ],        8, [ (PC == 0x1BBC) ], "JP (IX)" ],
            [ [ IY(0x1BBC) ], [ 0xFD, 0xE9 ],        8, [ (PC == 0x1BBC) ], "JP (IY)" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_jr(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [],          [ 0x18, 0x08 ], 12, [ (PC == 0x000A) ], "JR 0AH" ],
            [ [ F(0x00) ], [ 0x38, 0x08 ],  7, [ (PC == 0x0002) ], "JR C,0AH (no jump)" ],
            [ [ F(0x01) ], [ 0x38, 0x08 ], 12, [ (PC == 0x000A) ], "JR C,0AH (jump)" ],
            [ [ F(0x01) ], [ 0x30, 0x08 ],  7, [ (PC == 0x0002) ], "JR NC,0AH (no jump)" ],
            [ [ F(0x00) ], [ 0x30, 0x08 ], 12, [ (PC == 0x000A) ], "JR NC,0AH (jump)" ],
            [ [ F(0x00) ], [ 0x28, 0x08 ],  7, [ (PC == 0x0002) ], "JR Z,0AH (no jump)" ],
            [ [ F(0x40) ], [ 0x28, 0x08 ], 12, [ (PC == 0x000A) ], "JR Z,0AH (jump)" ],
            [ [ F(0x40) ], [ 0x20, 0x08 ],  7, [ (PC == 0x0002) ], "JR NZ,0AH (no jump)" ],
            [ [ F(0x00) ], [ 0x20, 0x08 ], 12, [ (PC == 0x000A) ], "JR NZ,0AH (jump)" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_djnz(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ B(0x02) ], [ 0x10, 0x08 ], 13, [ (PC == 0x000A), (B == 0x01) ], "DJNZ 0AH (with B == 0x02)" ],
            [ [ B(0x01) ], [ 0x10, 0x08 ],  8, [ (PC == 0x0002), (B == 0x00) ], "DJNZ 0AH (with B == 0x01)" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_call(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ PC(0x1231), SP(0x2BBC) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xCD, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL 1BBCH" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xDC, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL C,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x01) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xDC, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL C,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x01) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xD4, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL NC,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xD4, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL NC,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xCC, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL Z,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x40) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xCC, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL Z,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x40) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xC4, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL NZ,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xC4, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL NZ,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xEC, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL PE,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x04) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xEC, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL PE,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x04) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xE4, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL PO,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xE4, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL PO,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xFC, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL M,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x80) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xFC, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL M,1BBCH (jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x80) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xF4, 0xBC, 0x1B ], 10, [ (PC == 0x1234), (SP == 0x2BBC), ], "CALL P,1BBCH (no jump)" ],
            [ [ PC(0x1231), SP(0x2BBC), F(0x00) ],  [ 0xFF for _ in range(0,0x1231) ] + [ 0xF4, 0xBC, 0x1B ], 17, [ (PC == 0x1BBC), (SP == 0x2BBA), (M[0x2BBB] == 0x12), (M[0x2BBA] == 0x34) ], "CALL P,1BBCH (jump)" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ret(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B) ],  [ 0xC9 ], 10, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B) ],  [ 0xED, 0x4D ], 14, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RETI" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), begin_nmi, ],  [ 0xED, 0x45 ], 14, [ (PC == 0x1BBC), (SP == 0x2BBE), (expect_int_enabled) ], "RETN" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x01) ],  [ 0xD8 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET C (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xD8 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET C (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xD0 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET NC (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x01) ],  [ 0xD0 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET NC (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x40) ],  [ 0xC8 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET Z (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xC8 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET Z (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xC0 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET NZ (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x40) ],  [ 0xC0 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET NZ (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x04) ],  [ 0xE8 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET PE (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xE8 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET PE (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xE0 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET PO (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x04) ],  [ 0xE0 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET PO (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x80) ],  [ 0xF8 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET M (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xF8 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET M (no jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x00) ],  [ 0xF0 ], 11, [ (PC == 0x1BBC), (SP == 0x2BBE) ], "RET P (jump)" ],
            [ [ SP(0x2BBC), M(0x2BBC,0xBC), M(0x2BBD,0x1B), F(0x80) ],  [ 0xF0 ],  5, [ (PC == 0x0001), (SP == 0x2BBC) ], "RET P (no jump)" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_rst(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xC7 ], 11, [ (PC == 0x0000), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 00H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xCF ], 11, [ (PC == 0x0008), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 08H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xD7 ], 11, [ (PC == 0x0010), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 10H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xDF ], 11, [ (PC == 0x0018), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 18H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xE7 ], 11, [ (PC == 0x0020), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 20H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xEF ], 11, [ (PC == 0x0028), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 28H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xF7 ], 11, [ (PC == 0x0030), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 30H" ],
            [ [ PC(0x1233), SP(0x1BBC) ], ([ 0xFF ]*0x1233) + [ 0xFF ], 11, [ (PC == 0x0038), (SP == 0x1BBA), (M[0x1BBA] == 0x34), (M[0x1BBB] == 0x12) ], "RST 38H" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_in(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ A(0x55), IN(0xAB) ],          [ 0xDB, 0xFE ], 11, [ (A == 0xAB), (IN == 0x55) ], "IN A,FEH" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x40 ], 12, [ (B == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN B,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x48 ], 12, [ (C == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN C,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x50 ], 12, [ (D == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN D,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x58 ], 12, [ (E == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN E,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x60 ], 12, [ (H == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN H,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x68 ], 12, [ (L == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN L,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x70 ], 12, [              (IN == 0x55), (F == 0xA9) ], "IN F,(C)" ],
            [ [ B(0x55), C(0xFE), IN(0xAB) ], [ 0xED, 0x78 ], 12, [ (A == 0xAB), (IN == 0x55), (F == 0xA8) ], "IN A,(C)" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ini(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ IN(0xAB), HL(0x1BBC), B(0x2), C(0xFE) ], [ 0xED, 0xA2 ], 16, [ (M[0x1BBC] == 0xAB), (IN == 0x02), (HL == 0x1BBD), (B == 0x01), (F == 0x00) ], "INI" ],
            [ [ IN(0xAB), HL(0x1BBC), B(0x1), C(0xFE) ], [ 0xED, 0xA2 ], 16, [ (M[0x1BBC] == 0xAB), (IN == 0x01), (HL == 0x1BBD), (B == 0x00), (F == 0x44) ], "INI" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_inir(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ IN(0xAB), HL(0x1BBC), B(0x2), C(0xFE) ], [ 0xED, 0xB2 ], 21, [ (PC == 0x00), (M[0x1BBC] == 0xAB), (IN == 0x02), (HL == 0x1BBD), (B == 0x01), (F == 0x00) ], "INIR" ],
            [ [ IN(0xAB), HL(0x1BBC), B(0x1), C(0xFE) ], [ 0xED, 0xB2 ], 16, [ (PC == 0x02), (M[0x1BBC] == 0xAB), (IN == 0x01), (HL == 0x1BBD), (B == 0x00), (F == 0x44) ], "INIR" ],
            [ [ IN(0xAB), HL(0x1BBC), B(0x2), C(0xFE) ], [ 0xED, 0xB2 ], 37, [ (PC == 0x02), (M[0x1BBC] == 0xAB), (M[0x1BBD] == 0xAB), (IN == 0x01), (HL == 0x1BBE), (B == 0x00), (F == 0x44)], "INIR" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_ind(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ IN(0xAB), HL(0x1BBC), B(0x2), C(0xFE) ], [ 0xED, 0xAA ], 16, [ (M[0x1BBC] == 0xAB), (IN == 0x02), (HL == 0x1BBB), (B == 0x01), (F == 0x00) ], "INI" ],
            [ [ IN(0xAB), HL(0x1BBC), B(0x1), C(0xFE) ], [ 0xED, 0xAA ], 16, [ (M[0x1BBC] == 0xAB), (IN == 0x01), (HL == 0x1BBB), (B == 0x00), (F == 0x44) ], "INI" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_indr(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ IN(0xAB), HL(0x1BBC), B(0x2), C(0xFE) ], [ 0xED, 0xBA ], 21, [ (PC == 0x00), (M[0x1BBC] == 0xAB), (IN == 0x02), (HL == 0x1BBB), (B == 0x01), (F == 0x00) ], "INIR" ],
            [ [ IN(0xAB), HL(0x1BBC), B(0x1), C(0xFE) ], [ 0xED, 0xBA ], 16, [ (PC == 0x02), (M[0x1BBC] == 0xAB), (IN == 0x01), (HL == 0x1BBB), (B == 0x00), (F == 0x44) ], "INIR" ],
            [ [ IN(0xAB), HL(0x1BBC), B(0x2), C(0xFE) ], [ 0xED, 0xBA ], 37, [ (PC == 0x02), (M[0x1BBC] == 0xAB), (M[0x1BBB] == 0xAB), (IN == 0x01), (HL == 0x1BBA), (B == 0x00), (F == 0x44)], "INIR" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_out(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ A(0x55) ],                   [ 0xD3, 0xFA ], 11, [ (OUT == (0x55, 0x55)) ], "OUT (FEH),A" ],
            [ [ B(0x55), C(0xFA) ],          [ 0xED, 0x41 ], 12, [ (OUT == (0x55, 0x55)) ], "OUT (C),B" ],
            [ [ B(0x55), C(0xFA) ],          [ 0xED, 0x49 ], 12, [ (OUT == (0x55, 0xFA)) ], "OUT (C),C" ],
            [ [ B(0x55), C(0xFA), D(0xAB) ], [ 0xED, 0x51 ], 12, [ (OUT == (0x55, 0xAB)) ], "OUT (C),D" ],
            [ [ B(0x55), C(0xFA), E(0xAB) ], [ 0xED, 0x59 ], 12, [ (OUT == (0x55, 0xAB)) ], "OUT (C),E" ],
            [ [ B(0x55), C(0xFA), H(0xAB) ], [ 0xED, 0x61 ], 12, [ (OUT == (0x55, 0xAB)) ], "OUT (C),H" ],
            [ [ B(0x55), C(0xFA), L(0xAB) ], [ 0xED, 0x69 ], 12, [ (OUT == (0x55, 0xAB)) ], "OUT (C),L" ],
            [ [ B(0x55), C(0xFA), F(0xAB) ], [ 0xED, 0x71 ], 12, [ (OUT == (0x55, 0xAB)) ], "OUT (C),F" ],
            [ [ B(0x55), C(0xFA), A(0xAB) ], [ 0xED, 0x79 ], 12, [ (OUT == (0x55, 0xAB)) ], "OUT (C),A" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_outi(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), B(0x2), C(0xFA), M(0x1BBC,0xAB) ], [ 0xED, 0xA3 ], 16, [ (OUT == (0x02,0xAB)), (HL == 0x1BBD), (B == 0x01), (F == 0x00) ], "OUTI" ],
            [ [ HL(0x1BBC), B(0x1), C(0xFA), M(0x1BBC,0xAB) ], [ 0xED, 0xA3 ], 16, [ (OUT == (0x01,0xAB)), (HL == 0x1BBD), (B == 0x00), (F == 0x44) ], "OUTI" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_outir(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), B(0x2), C(0xFA), M(0x1BBC,0xAB) ],                 [ 0xED, 0xB3 ], 21, [ (PC == 0x00), (OUT == (0x02,0xAB)), (HL == 0x1BBD), (B == 0x01), (F == 0x00) ], "OUTIR" ],
            [ [ HL(0x1BBC), B(0x1), C(0xFA), M(0x1BBC,0xAB) ],                 [ 0xED, 0xB3 ], 16, [ (PC == 0x02), (OUT == (0x01,0xAB)), (HL == 0x1BBD), (B == 0x00), (F == 0x44) ], "OUTIR" ],
            [ [ HL(0x1BBC), B(0x2), C(0xFA), M(0x1BBC,0xAB), M(0x1BBD,0xCD) ], [ 0xED, 0xB3 ], 37, [ (PC == 0x02), (OUT == (0x01,0xCD)), (HL == 0x1BBE), (B == 0x00), (F == 0x44) ], "OUTIR" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_outd(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), B(0x2), C(0xFA), M(0x1BBC,0xAB) ], [ 0xED, 0xAB ], 16, [ (OUT == (0x02,0xAB)), (HL == 0x1BBB), (B == 0x01), (F == 0x00) ], "OUTD" ],
            [ [ HL(0x1BBC), B(0x1), C(0xFA), M(0x1BBC,0xAB) ], [ 0xED, 0xAB ], 16, [ (OUT == (0x01,0xAB)), (HL == 0x1BBB), (B == 0x00), (F == 0x44) ], "OUTD" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_outdr(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [ HL(0x1BBC), B(0x2), C(0xFA), M(0x1BBC,0xAB) ],                 [ 0xED, 0xBB ], 21, [ (PC == 0x00), (OUT == (0x02,0xAB)), (HL == 0x1BBB), (B == 0x01), (F == 0x00) ], "OUTDR" ],
            [ [ HL(0x1BBC), B(0x1), C(0xFA), M(0x1BBC,0xAB) ],                 [ 0xED, 0xBB ], 16, [ (PC == 0x02), (OUT == (0x01,0xAB)), (HL == 0x1BBB), (B == 0x00), (F == 0x44) ], "OUTDR" ],
            [ [ HL(0x1BBC), B(0x2), C(0xFA), M(0x1BBC,0xAB), M(0x1BBB,0xCD) ], [ 0xED, 0xBB ], 37, [ (PC == 0x02), (OUT == (0x01,0xCD)), (HL == 0x1BBA), (B == 0x00), (F == 0x44) ], "OUTDR" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_halt(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [], [ 0x76, 0xFF, 0xFF ], 100, [ (PC == 0x00) ], "HALT" ],
        ]

        for (pre, instructions, t_cycles, post, name) in tests:
            self.execute_instructions(pre, instructions, t_cycles, post, name)        
