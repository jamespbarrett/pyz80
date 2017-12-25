import unittest
import mock

from pyz80.machinestates import decode_instruction
from pyz80.machinestates import INSTRUCTION_STATES

from pyz80.cpu import *
from pyz80.memorybus import MemoryBus, ROM
from pyz80.iobus import IOBus

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
        membus = MemoryBus()
        iobus  = IOBus()
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

    def test_jp(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        tests = [
            [ [], [ 0xC3, 0xBC, 0x1B ], 10, [ (PC == 0x1BBC) ], "PUSH AF" ],
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

    def test_add(self):
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

    def test_adc(self):
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
        for (X, f) in [ (0x00, 0x00),
                        (0x01, 0x00),
                        (0x0F, 0x10),
                        (0xFF, 0x54),
                        ]:
            tests = [
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

            for (pre, instructions, t_cycles, post, name) in tests:
                self.execute_instructions(pre, instructions, t_cycles, post, name)

    def test_dec(self):
        # actions taken first, instructions to execute, t-cycles to run for, expected conditions post, name
        for (X, f) in [ (0x00, 0xBA),
                        (0x01, 0x42),
                        (0x02, 0x02),
                        (0x10, 0x1A),
                        ]:
            tests = [
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
