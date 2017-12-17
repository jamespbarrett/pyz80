__all__ = [ "MachineState", "OCF", "UnrecognisedInstructionError" ]

class UnrecognisedInstructionError(Exception):
    def __init__(self, inst):
        self.inst = inst
        super(UnrecognisedInstructionError, self).__init__("Unrecognised Instruction 0x{:X}".format(inst))


# Actions which can be triggered at end of machine states

def JP(state, target):
    """Jump to the second parameter (an address)"""
    print "!!!!JUMP TO {:X}!!!".format(target)
    state.cpu.reg.PC = target

def LDr(reg):
    """Load into the specified register"""
    def _inner(state, value):
        setattr(state.cpu.reg, reg, value)
    return _inner

def LDrs(r,s):
    """Load from the specified register into the specified register"""
    def _inner(state):
        setattr(state.cpu.reg, r, getattr(state.cpu.reg, s))
    return _inner

# Machine States

class MachineState(object):
    def __init__(self):
        """Descendent classes may add extra parameters here, which are values set at decode time."""
        self.cpu          = None
        self.iter         = self.run()
        self.pipeline     = None
        self.args         = []
        self.kwargs       = {}
        self.return_value = None

    def setcpu(self, cpu):
        self.cpu = cpu
        return self

    def fetchlocked(self):
        """Returns True if a pipeline containing this machine state should block the state machine from
        starting a new OCF pipeline."""
        return False

    def run(self):
        """Should be a generator function. Don't yield values (they'll be ignored).
        Can set a return value for self.clock in self.return_value. In addition when
        this generator exits the value of self.args and self.kwargs will be transferred
        to the next state in the pipeline. This is useful for passing values on."""
        raise StopIteration
        yield None

    def clock(self, pipeline):
        self.pipeline = pipeline
        try:
            return self.iter.next()
        except StopIteration:
            self.pipeline.pop(0)
            if len(self.pipeline) > 0:
                self.pipeline[0].args   = self.args
                self.pipeline[0].kwargs = self.kwargs
            return self.return_value

class OCF(MachineState):
    """This state fetches an OP Code from memory and advances the PC in 4 t-cycles.
    Args In:
    - None
    Args Out:
    - None
    Side Effects:
    - Increments PC
    - Decodes OP-Code and adds new machine states to the pipeline if required
    Returned Values:
    - None
    Time Taken:
    - 4 clock cycles, or more if decode indicates there should be."""

    def fetchlocked(self):
        return True

    def run(self):
        PC = self.cpu.reg.PC
        yield

        inst = self.cpu.membus.read(PC)
        yield

        (extra_clocks, actions, states) = decode_instruction(inst)
        states = [ state().setcpu(self.cpu) for state in states ]
        self.cpu.reg.PC = PC + 1
        yield

        for n in range(0,extra_clocks-1):
            yield

        self.pipeline.extend(states)
        for action in actions:
            action(self)
        raise StopIteration

def OD(compound=None, action=None, key="value"):
    class _OD(MachineState):
        """This state fetches an data byte from memory and advances the PC in 3 t-cycles.
        Initialisation Parameters:
        - Optionally: 'compound' a method that takes two parameters (new, old) used to combine
        the old value of 'value' with the new one.
        - Optionally: 'action' a method which takes a two parameters, the state and a single integer. 
        It will be called with the final value of 'value' as the last operation in the state. 
        Args In:
        - Optionally: 'value' a single integer cascaded from a previous state
        Args Out:
        - 'value' : a integer cascaded to the next state
        Side Effects:
        - Increments PC, calls 'action'
        Returned Values:
        - None
        Time Taken:
        - 3 clock cycles"""

        def __init__(self):
            self.key      = key
            self.compound = compound
            self.action   = action
            super(_OD, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            PC = self.cpu.reg.PC
            yield
            D = self.cpu.membus.read(PC)
            yield
            self.cpu.reg.PC = PC + 1
            if self.key in self.kwargs and self.compound is not None:
                D = self.compound(D, self.kwargs[self.key])
            self.kwargs[self.key] = D
            if self.action is not None:
                self.action(self, D)
            raise StopIteration
    return _OD

def MR(address=None, indirect=None, compound=None, action=None):
    class _MR(MachineState):
        """This state fetches a data byte from memory at a specified address (possibly using register indirect or indexed addressing):
        Initialisation Parameters:
        - Optionally: 'address' the address in memory to load from
        - Optionally: 'indirect' the name of the register to take the address from
        - Optionally: 'compound' a method that takes two parameters (new, old) used to combine
        the old value of 'value' with the new one.
        - Optionally: 'action' a method which takes a two parameters, the state and a single integer. 
        It will be called with the final value of 'value' as the last operation in the state. 
        Args In:
        - Optionally: 'value' a single integer cascaded from a previous state
        Args Out:
        - 'value' : the contents of the memory read, cascaded to the next state
        Side Effects:
        - Calls 'action'
        Returned Values:
        - None
        Time Taken:
        - 3 clock cycles"""

        def __init__(self):
            self.address  = address
            self.indirect = indirect
            self.compound = compound
            self.action   = action
            super(_MR, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            if self.address is None:
                if self.indirect is None:
                    if 'address' not in self.kwargs:
                        raise Exception("MR without either address of indirect specified")
                    else:
                        self.address = self.kwargs['address']
                else:
                    self.address = getattr(self.cpu.reg, self.indirect)
            yield

            D = self.cpu.membus.read(self.address)
            yield

            if 'value' in self.kwargs and self.coumpound is not None:
                D = self.compound(D, self.kwargs['value'])
            self.kwargs['value'] = D
            if self.action is not None:
                self.action(self, D)
            raise StopIteration

    return _MR

def MW(address=None, indirect=None, value=None, source=None):
    class _MW(MachineState):
        """This state writes a data byte to memory at a specified address (possibly using register indirect or indexed addressing):
        Initialisation Parameters:
        - Optionally: 'address' the address in memory to write to
        - Optionally: 'indirect' the name of the register to take the address from
        - Optionally: 'value' the value to write.
        - Optionally: 'source' a register from which to obtain the value to write. (if Neither value nor source is specified it will be cascaded in)
        Args In:
        - Optionally: 'value' a single integer cascaded from a previous state
        - Optionally: 'address' a single integer cascaded from a previous state
        Args Out:
        - None
        Side Effects:
        - None
        Returned Values:
        - None
        Time Taken:
        - 3 clock cycles"""

        def __init__(self):
            self.address  = address
            self.indirect = indirect
            self.value    = value
            self.action   = action
            self.source   = source
            super(_MR, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            if self.address is None:
                if self.indirect is None:
                    if 'address' not in self.kwargs:
                        raise Exception("MR without either address of indirect specified")
                    else:
                        self.address = self.kwargs['address']
                else:
                    self.address = getattr(self.cpu.reg, self.indirect)
            yield

            if self.value is None:
                if self.source is None:
                    if 'value' not in self.kwargs:
                        raise Exception("MR without either value or source specified")
                    else:
                        self.value = self.kwargs['value']
                else:
                    self.value = getattr(self.cpu.reg, self.source)
            yield

            self.cpu.membus.write(self.address, self.value)
            raise StopIteration

    return _MW

INSTRUCTION_STATES = {
    0x00 : (0, [],                  [] ),                                                             # NOP
    0x06 : (0, [],                  [ OD(action=LDr('B')), ]),                                        # LD B,n
    0x0E : (0, [],                  [ OD(action=LDr('C')), ]),                                        # LD C,n
    0x0A : (0, [],                  [ MR(indirect="BC", action=LDr("A")) ]),                          # LD A,(BC)
    0x16 : (0, [],                  [ OD(action=LDr('D')), ]),                                        # LD D,n
    0x1A : (0, [],                  [ MR(indirect="DE", action=LDr("A")) ]),                          # LD A,(DE)
    0x1E : (0, [],                  [ OD(action=LDr('E')), ]),                                        # LD E,n
    0x26 : (0, [],                  [ OD(action=LDr('H')), ]),                                        # LD H,n
    0x2E : (0, [],                  [ OD(action=LDr('L')), ]),                                        # LD L,n
    0x3A : (0, [],                  [ OD(key="address"), OD(compound=(lambda x,y : ((x << 8) + y)),key="address"), MR(action=LDr("A")) ]), # LD A,(nn)
    0x3E : (0, [],                  [ OD(action=LDr('A')), ]),                                        # LD A,n
    0x40 : (0, [ LDrs('B', 'B'), ], [] ),                                                             # LD B,B
    0x41 : (0, [ LDrs('B', 'C'), ], [] ),                                                             # LD B,C
    0x42 : (0, [ LDrs('B', 'D'), ], [] ),                                                             # LD B,D
    0x43 : (0, [ LDrs('B', 'E'), ], [] ),                                                             # LD B,E
    0x44 : (0, [ LDrs('B', 'H'), ], [] ),                                                             # LD B,H
    0x45 : (0, [ LDrs('B', 'L'), ], [] ),                                                             # LD B,L
    0x46 : (0, [],                  [ MR(indirect="HL", action=LDr("B")) ]),                          # LD B,(HL)
    0x47 : (0, [ LDrs('B', 'A'), ], [] ),                                                             # LD B,A
    0x48 : (0, [ LDrs('C', 'B'), ], [] ),                                                             # LD C,B
    0x49 : (0, [ LDrs('C', 'C'), ], [] ),                                                             # LD C,C
    0x4A : (0, [ LDrs('C', 'D'), ], [] ),                                                             # LD C,D
    0x4B : (0, [ LDrs('C', 'E'), ], [] ),                                                             # LD C,E
    0x4C : (0, [ LDrs('C', 'H'), ], [] ),                                                             # LD C,H
    0x4D : (0, [ LDrs('C', 'L'), ], [] ),                                                             # LD C,L
    0x4E : (0, [],                  [ MR(indirect="HL", action=LDr("C")) ]),                          # LD C,(HL)
    0x4F : (0, [ LDrs('C', 'A'), ], [] ),                                                             # LD C,A
    0x50 : (0, [ LDrs('D', 'B'), ], [] ),                                                             # LD D,B
    0x51 : (0, [ LDrs('D', 'C'), ], [] ),                                                             # LD D,C
    0x52 : (0, [ LDrs('D', 'D'), ], [] ),                                                             # LD D,D
    0x53 : (0, [ LDrs('D', 'E'), ], [] ),                                                             # LD D,E
    0x54 : (0, [ LDrs('D', 'H'), ], [] ),                                                             # LD D,H
    0x55 : (0, [ LDrs('D', 'L'), ], [] ),                                                             # LD D,L
    0x56 : (0, [],                  [ MR(indirect="HL", action=LDr("D")) ]),                          # LD D,(HL)
    0x57 : (0, [ LDrs('D', 'A'), ], [] ),                                                             # LD D,A
    0x58 : (0, [ LDrs('E', 'B'), ], [] ),                                                             # LD E,B
    0x59 : (0, [ LDrs('E', 'C'), ], [] ),                                                             # LD E,C
    0x5A : (0, [ LDrs('E', 'D'), ], [] ),                                                             # LD E,D
    0x5B : (0, [ LDrs('E', 'E'), ], [] ),                                                             # LD E,E
    0x5C : (0, [ LDrs('E', 'H'), ], [] ),                                                             # LD E,H
    0x5D : (0, [ LDrs('E', 'L'), ], [] ),                                                             # LD E,L
    0x5E : (0, [],                  [ MR(indirect="HL", action=LDr("E")) ]),                          # LD E,(HL)
    0x5F : (0, [ LDrs('E', 'A'), ], [] ),                                                             # LD E,A
    0x60 : (0, [ LDrs('H', 'B'), ], [] ),                                                             # LD H,B
    0x61 : (0, [ LDrs('H', 'C'), ], [] ),                                                             # LD H,C
    0x62 : (0, [ LDrs('H', 'D'), ], [] ),                                                             # LD H,D
    0x63 : (0, [ LDrs('H', 'E'), ], [] ),                                                             # LD H,E
    0x64 : (0, [ LDrs('H', 'H'), ], [] ),                                                             # LD H,H
    0x65 : (0, [ LDrs('H', 'L'), ], [] ),                                                             # LD H,L
    0x66 : (0, [],                  [ MR(indirect="HL", action=LDr("H")) ]),                          # LD H,(HL)
    0x67 : (0, [ LDrs('H', 'A'), ], [] ),                                                             # LD H,A
    0x68 : (0, [ LDrs('L', 'B'), ], [] ),                                                             # LD L,B
    0x69 : (0, [ LDrs('L', 'C'), ], [] ),                                                             # LD L,C
    0x6A : (0, [ LDrs('L', 'D'), ], [] ),                                                             # LD L,D
    0x6B : (0, [ LDrs('L', 'E'), ], [] ),                                                             # LD L,E
    0x6C : (0, [ LDrs('L', 'H'), ], [] ),                                                             # LD L,H
    0x6D : (0, [ LDrs('L', 'L'), ], [] ),                                                             # LD L,L
    0x6E : (0, [],                  [ MR(indirect="HL", action=LDr("L")) ]),                          # LD L,(HL)
    0x6F : (0, [ LDrs('L', 'A'), ], [] ),                                                             # LD L,A
    0x70 : (0, [],                  [ MW(indirect="HL", source="B") ]),                               # LD (HL),B
    0x78 : (0, [ LDrs('A', 'B'), ], [] ),                                                             # LD A,B
    0x79 : (0, [ LDrs('A', 'C'), ], [] ),                                                             # LD A,C
    0x7A : (0, [ LDrs('A', 'D'), ], [] ),                                                             # LD A,D
    0x7B : (0, [ LDrs('A', 'E'), ], [] ),                                                             # LD A,E
    0x7C : (0, [ LDrs('A', 'H'), ], [] ),                                                             # LD A,H
    0x7D : (0, [ LDrs('A', 'L'), ], [] ),                                                             # LD A,L
    0x7E : (0, [],                  [ MR(indirect="HL", action=LDr("A")) ]),                          # LD A, (HL)
    0x7F : (0, [ LDrs('A', 'A'), ], [] ),                                                             # LD A,A
    0xC3 : (0, [],                  [ OD(), OD(compound=(lambda x,y : ((x << 8) + y)), action=JP) ]), # JP n n
    }

def decode_instruction(instruction):
    """Decode an instruction code and return a tuple of:
    (extra_time_for_OCF, [list of callables as side-effects of OCF], [ list of new machine states to add to pipeline ])"""
    if instruction in INSTRUCTION_STATES:
        return INSTRUCTION_STATES[instruction]
    raise UnrecognisedInstructionError(instruction)
