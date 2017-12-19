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

class REG(object):
    def __init__(self, r):
        self.r = r

    def __call__(self, value):
        return set_register_to(self.r, value)

    def __eq__(self, other):
        return expect_register_equal(self.r, other)

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
            [ [ I(0xB) ], [ 0xED, 0x57 ], 4, [ (PC == 0x02), (A == 0xB) ], "LD A,I" ],
            [ [ R(0xB) ], [ 0xED, 0x5F ], 4, [ (PC == 0x02), (A == 0xB) ], "LD A,R" ],
            [ [ A(0xB) ], [ 0xED, 0x47 ], 4, [ (PC == 0x02), (I == 0xB) ], "LD I,A" ],
            [ [ A(0xB) ], [ 0xED, 0x4F ], 4, [ (PC == 0x02), (R == 0xB) ], "LD R,A" ],

            [ [], [ 0x01, 0xBC, 0x1B ], 10, [ (PC == 0x03), (BC == 0x1BBC), ], "LD BC,1BBCH" ],
            [ [], [ 0x11, 0xBC, 0x1B ], 10, [ (PC == 0x03), (DE == 0x1BBC), ], "LD DE,1BBCH" ],
            [ [], [ 0x21, 0xBC, 0x1B ], 10, [ (PC == 0x03), (HL == 0x1BBC), ], "LD HL,1BBCH" ],
            [ [], [ 0x31, 0xBC, 0x1B ], 10, [ (PC == 0x03), (SP == 0x1BBC), ], "LD SP,1BBCH" ],
            [ [], [ 0xDD, 0x21, 0xBC, 0x1B ], 10, [ (PC == 0x04), (IX == 0x1BBC), ], "LD IX,1BBCH" ],
            [ [], [ 0xFD, 0x21, 0xBC, 0x1B ], 10, [ (PC == 0x04), (IY == 0x1BBC), ], "LD IY,1BBCH" ],

            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0x2A, 0xBC, 0x1B ],       16, [ (PC == 0x03), (HL == 0xCAFE) ], "LD HL,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xED, 0x4B, 0xBC, 0x1B ], 16, [ (PC == 0x04), (BC == 0xCAFE) ], "LD BC,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xED, 0x5B, 0xBC, 0x1B ], 16, [ (PC == 0x04), (DE == 0xCAFE) ], "LD DE,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xED, 0x7B, 0xBC, 0x1B ], 16, [ (PC == 0x04), (SP == 0xCAFE) ], "LD SP,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xDD, 0x2A, 0xBC, 0x1B ], 16, [ (PC == 0x04), (IX == 0xCAFE) ], "LD IX,(1BBCH)" ],
            [ [ M(0x1BBC,0xFE), M(0x1BBD,0xCA) ], [ 0xFD, 0x2A, 0xBC, 0x1B ], 16, [ (PC == 0x04), (IY == 0xCAFE) ], "LD IY,(1BBCH)" ],

            [ [ BC(0xCAFE) ], [ 0xED, 0x43, 0xBC, 0x1B ], 16, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),BC" ],
            [ [ DE(0xCAFE) ], [ 0xED, 0x53, 0xBC, 0x1B ], 16, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),DE" ],
            [ [ HL(0xCAFE) ], [ 0x22, 0xBC, 0x1B ],       16, [ (PC == 0x03), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),HL" ],
            [ [ SP(0xCAFE) ], [ 0xED, 0x73, 0xBC, 0x1B ], 16, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),SP" ],
            [ [ IX(0xCAFE) ], [ 0xDD, 0x22, 0xBC, 0x1B ], 16, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IX" ],
            [ [ IY(0xCAFE) ], [ 0xFD, 0x22, 0xBC, 0x1B ], 16, [ (PC == 0x04), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IY" ],

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

            [ [ IX(0xCAFE) ], [ 0xDD, 0xF9 ], 4, [ (PC == 0x02), (SP == 0xCAFE) ], "LD SP,IX"],
            [ [ IY(0xCAFE) ], [ 0xFD, 0xF9 ], 4, [ (PC == 0x02), (SP == 0xCAFE) ], "LD SP,IY"],

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

            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x46, 0x0C ], 15, [ (PC == 0x3), (B == 0x0B) ], "LD B,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x4E, 0x0C ], 15, [ (PC == 0x3), (C == 0x0B) ], "LD C,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x56, 0x0C ], 15, [ (PC == 0x3), (D == 0x0B) ], "LD D,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x5E, 0x0C ], 15, [ (PC == 0x3), (E == 0x0B) ], "LD E,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x66, 0x0C ], 15, [ (PC == 0x3), (H == 0x0B) ], "LD H,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x6E, 0x0C ], 15, [ (PC == 0x3), (L == 0x0B) ], "LD L,(IX+0CH)"],
            [ [ M(0x1BBC, 0x0B), IX(0x1BB0) ], [ 0xDD, 0x7E, 0x0C ], 15, [ (PC == 0x3), (A == 0x0B) ], "LD A,(IX+0CH)"],

            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x46, 0x0C ], 15, [ (PC == 0x3), (B == 0x0B) ], "LD B,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x4E, 0x0C ], 15, [ (PC == 0x3), (C == 0x0B) ], "LD C,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x56, 0x0C ], 15, [ (PC == 0x3), (D == 0x0B) ], "LD D,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x5E, 0x0C ], 15, [ (PC == 0x3), (E == 0x0B) ], "LD E,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x66, 0x0C ], 15, [ (PC == 0x3), (H == 0x0B) ], "LD H,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x6E, 0x0C ], 15, [ (PC == 0x3), (L == 0x0B) ], "LD L,(IY+0CH)"],
            [ [ M(0x1BBC, 0x0B), IY(0x1BB0) ], [ 0xFD, 0x7E, 0x0C ], 15, [ (PC == 0x3), (A == 0x0B) ], "LD A,(IY+0CH)"],

            [ [ B(0x0B), IX(0x1BB0) ], [ 0xDD, 0x70, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),B"],
            [ [ C(0x0B), IX(0x1BB0) ], [ 0xDD, 0x71, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),C"],
            [ [ D(0x0B), IX(0x1BB0) ], [ 0xDD, 0x72, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),D"],
            [ [ E(0x0B), IX(0x1BB0) ], [ 0xDD, 0x73, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),E"],
            [ [ H(0x0B), IX(0x1BB0) ], [ 0xDD, 0x74, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),H"],
            [ [ L(0x0B), IX(0x1BB0) ], [ 0xDD, 0x75, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),L"],
            [ [ A(0x0B), IX(0x1BB0) ], [ 0xDD, 0x77, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),A"],

            [ [ IX(0x1BB0) ], [ 0xDD, 0x36, 0x0C, 0x0B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0x0B) ], "LD (IX+0CH),0BH"],
            [ [ IY(0x1BB0) ], [ 0xFD, 0x36, 0x0C, 0x0B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),0BH"],

            [ [ B(0x0B), IY(0x1BB0) ], [ 0xFD, 0x70, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),B"],
            [ [ C(0x0B), IY(0x1BB0) ], [ 0xFD, 0x71, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),C"],
            [ [ D(0x0B), IY(0x1BB0) ], [ 0xFD, 0x72, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),D"],
            [ [ E(0x0B), IY(0x1BB0) ], [ 0xFD, 0x73, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),E"],
            [ [ H(0x0B), IY(0x1BB0) ], [ 0xFD, 0x74, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),H"],
            [ [ L(0x0B), IY(0x1BB0) ], [ 0xFD, 0x75, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),L"],
            [ [ A(0x0B), IY(0x1BB0) ], [ 0xFD, 0x77, 0x0C ], 15, [ (PC == 0x3), (M[0x1BBC] == 0x0B) ], "LD (IY+0CH),A"],

            [ [ BC(0xCAFE) ], [ 0xED, 0x43, 0xBC, 0x1B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),BC" ],
            [ [ DE(0xCAFE) ], [ 0xED, 0x53, 0xBC, 0x1B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),DE" ],
            [ [ SP(0xCAFE) ], [ 0xED, 0x73, 0xBC, 0x1B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),SP" ],
            [ [ IX(0xCAFE) ], [ 0xDD, 0x22, 0xBC, 0x1B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IX" ],
            [ [ IY(0xCAFE) ], [ 0xFD, 0x22, 0xBC, 0x1B ], 18, [ (PC == 0x4), (M[0x1BBC] == 0xFE), (M[0x1BBD] == 0xCA) ], "LD (1BBCH),IY" ],
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
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xDD, 0xE1, ], 10, [ (PC == 0x02), (SP == 0x1BBE), (IX == 0xCAFE) ], "POP IX" ],
            [ [ M(0x1BBC, 0xFE), M(0x1BBD, 0xCA), SP(0x1BBC) ], [ 0xFD, 0xE1, ], 10, [ (PC == 0x02), (SP == 0x1BBE), (IY == 0xCAFE) ], "POP IY" ],
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
            [ [ IX(0xCAFE), SP(0x1BBC) ], [ 0xDD, 0xE5, ], 10, [ (PC == 0x02), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH IX" ],
            [ [ IY(0xCAFE), SP(0x1BBC) ], [ 0xFD, 0xE5, ], 10, [ (PC == 0x02), (SP == 0x1BBA), (M[0x1BBA] == 0xFE), (M[0x1BBB] == 0xCA) ], "PUSH IY" ],
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
