__all__ = [ "MachineState", "OCF", "UnrecognisedInstructionError" ]

class UnrecognisedInstructionError(Exception):
    def __init__(self, inst):
        self.inst = inst
        super(UnrecognisedInstructionError, self).__init__("Unrecognised Instruction 0x{:X}".format(inst))


# Actions which can be triggered at end of machine states

def MB():
    """This can be set as the action for an OPCODE that's actually the first byte of a multibyte sequence."""
    raise Exception("Tried to execute the special MB action used to signal multibyte OPCODES")

def JP(state, target):
    """Jump to the second parameter (an address)"""
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

def add_register(r):
    """Load a value from the specified register and add it to the parameter"""
    def _inner(state, d):
        return getattr(state.cpu.reg, r) + d
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
        if MB in actions:
            inst = (inst, self.cpu.membus.read(PC + 1))
            (extra_clocks, actions, states) = decode_instruction(inst)
            self.cpu.reg.PC = PC + 2
        else:
            self.cpu.reg.PC = PC + 1
        states = [ state().setcpu(self.cpu) for state in states ]
        yield

        for n in range(0,extra_clocks-1):
            yield

        self.pipeline.extend(states)
        for action in actions:
            action(self)
        raise StopIteration

def OD(compound=None, action=None, key="value", signed=False):
    class _OD(MachineState):
        """This state fetches an data byte from memory and advances the PC in 3 t-cycles.
        Initialisation Parameters:
        - Optionally: 'compound' a method that takes two parameters (new, old) used to combine
        the old value of 'value' with the new one.
        - Optionally: 'action' a method which takes a two parameters, the state and a single integer. 
        It will be called with the final value of 'value' as the last operation in the state. 
        - Optionally: 'signed', set to True if the input should be interpreted as 2's complement
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
            self.signed   = signed
            super(_OD, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            PC = self.cpu.reg.PC
            yield
            D = self.cpu.membus.read(PC)
            if signed and D >= 0x80:
                D = D - 0x100
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
        - 'address' : the address read from plus one
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
            self.kwargs['address'] = self.address + 1
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
        - 'address': the address that was written to plus one (useful for 16-bit writes)
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
            super(_MW, self).__init__()

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
            self.kwargs['address'] = self.address + 1
            raise StopIteration
        
    return _MW

def SR(compound=None, action=None):
    class _SR(MachineState):
        """This state fetches a data byte from memory at the top of the stack and increments the stack pointer:
        Initialisation Parameters:
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
        - Increments SP
        Returned Values:
        - None
        Time Taken:
        - 3 clock cycles"""

        def __init__(self):
            self.compound = compound
            self.action   = action
            super(_SR, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            self.address = self.cpu.reg.SP
            yield

            D = self.cpu.membus.read(self.address)
            yield

            if 'value' in self.kwargs and self.coumpound is not None:
                D = self.compound(D, self.kwargs['value'])
            self.kwargs['value'] = D
            self.cpu.reg.SP = self.cpu.reg.SP + 1
            if self.action is not None:
                self.action(self, D)
            raise StopIteration

    return _SR

def SW(source):
    class _SW(MachineState):
        """This state decrements the stack pointer and writes a data byte to memory at the top of the stack:
        Initialisation Parameters:
        - Mandatory: 'source' the register from which to take the value
        Args In:
        - None
        Args Out:
        - None
        Side Effects:
        - Decrements SP
        Returned Values:
        - None
        Time Taken:
        - 3 clock cycles"""

        def __init__(self):
            self.source = source
            super(_SW, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            self.cpu.reg.SP = self.cpu.reg.SP - 1
            yield

            self.address = self.cpu.reg.SP
            yield

            self.cpu.membus.write(self.address, getattr(self.cpu.reg, self.source))
            raise StopIteration

    return _SW

def IO(ticks, locked, transform=None, action=None, key="value"):
    class _IO(MachineState):
        """This state does nothing but take in and pass on args, apply transform to them and perform action
        Initialisation Parameters:
        - Mandatory : 'ticks', the time taken
        - Mandatory : 'locked', true if other states can't access memory whilst this is active
        - Optionally: 'transform' a method which will be called with this state and a cascaded in 'value' or a dictionary mapping args to methods
        - Optionally: 'action' a side effect called last thing in the state
        Args In:
        - Optionally: Any
        Args Out:
        - Anything passed in will be passed out
        Side Effects:
        - 'action' is called
        Returned Values:
        - None
        Time Taken:
        - variable"""

        def __init__(self):
            self.ticks  = ticks
            self.locked = locked
            self.transform = transform
            self.action   = action
            self.key      = key
            super(_IO, self).__init__()

        def fetchlocked(self):
            return self.locked

        def run(self):
            for key in self.kwargs:
                if callable(self.transform) and key == self.key:
                    self.kwargs[key] = self.transform(self, self.kwargs[key])
                elif isinstance(self.transform, dict) and key in self.transform:
                    self.kwargs[key] = self.transform[key](self, self.kwargs[key])
            for n in range(0,self.ticks - 1):
                yield
            if callable(self.action):
                self.action(self)
            raise StopIteration
        
    return _IO

def high_after_low(x,y):
    return ((x << 8) | y)

INSTRUCTION_STATES = {
    # Single bytes opcodes
    0x00 : (0, [],                  [] ),                                                             # NOP
    0x01 : (0, [],                  [ OD(), OD(compound=high_after_low, action=LDr('BC')) ]),         # LD BC,nn
    0x02 : (0, [],                  [ MW(indirect="BC", source="A") ]),                               # LD (BC),A
    0x06 : (0, [],                  [ OD(action=LDr('B')), ]),                                        # LD B,n
    0x0E : (0, [],                  [ OD(action=LDr('C')), ]),                                        # LD C,n
    0x0A : (0, [],                  [ MR(indirect="BC", action=LDr("A")) ]),                          # LD A,(BC)
    0x11 : (0, [],                  [ OD(), OD(compound=high_after_low, action=LDr('DE')) ]),         # LD DE,nn
    0x12 : (0, [],                  [ MW(indirect="DE", source="A") ]),                               # LD (DE),A
    0x16 : (0, [],                  [ OD(action=LDr('D')), ]),                                        # LD D,n
    0x1A : (0, [],                  [ MR(indirect="DE", action=LDr("A")) ]),                          # LD A,(DE)
    0x1E : (0, [],                  [ OD(action=LDr('E')), ]),                                        # LD E,n
    0x21 : (0, [],                  [ OD(), OD(compound=high_after_low, action=LDr('HL')) ]),         # LD HL,nn
    0x22 : (0, [],                  [ OD(key="address"),
                                        OD(key="address",
                                        compound=high_after_low),
                                        MW(source="L"), MW(source="H") ]),                            # LD (nn),HL
    0x26 : (0, [],                  [ OD(action=LDr('H')), ]),                                        # LD H,n
    0x2A : (0, [],                  [ OD(key="address"),
                                        OD(key="address", compound=high_after_low),
                                        MR(action=LDr('L')), MR(action=LDr('H')) ]),                  # LD HL,(nn)
    0x2E : (0, [],                  [ OD(action=LDr('L')), ]),                                        # LD L,n
    0x31 : (0, [],                  [ OD(), OD(compound=high_after_low, action=LDr('SP')) ]),         # LD SP,nn
    0x32 : (0, [],                  [ OD(key="address"), OD(compound=high_after_low,key="address"),
                                          MW(source="A") ]),                                          # LD (nn),A
    0x3A : (0, [],                  [ OD(key="address"), OD(compound=high_after_low,key="address"),
                                          MR(action=LDr("A")) ]),                                     # LD A,(nn)
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
    0x71 : (0, [],                  [ MW(indirect="HL", source="C") ]),                               # LD (HL),C
    0x72 : (0, [],                  [ MW(indirect="HL", source="D") ]),                               # LD (HL),D
    0x73 : (0, [],                  [ MW(indirect="HL", source="E") ]),                               # LD (HL),E
    0x74 : (0, [],                  [ MW(indirect="HL", source="H") ]),                               # LD (HL),H
    0x75 : (0, [],                  [ MW(indirect="HL", source="L") ]),                               # LD (HL),L
    0x77 : (0, [],                  [ MW(indirect="HL", source="A") ]),                               # LD (HL),A
    0x78 : (0, [ LDrs('A', 'B'), ], [] ),                                                             # LD A,B
    0x79 : (0, [ LDrs('A', 'C'), ], [] ),                                                             # LD A,C
    0x7A : (0, [ LDrs('A', 'D'), ], [] ),                                                             # LD A,D
    0x7B : (0, [ LDrs('A', 'E'), ], [] ),                                                             # LD A,E
    0x7C : (0, [ LDrs('A', 'H'), ], [] ),                                                             # LD A,H
    0x7D : (0, [ LDrs('A', 'L'), ], [] ),                                                             # LD A,L
    0x7E : (0, [],                  [ MR(indirect="HL", action=LDr("A")) ]),                          # LD A, (HL)
    0x7F : (0, [ LDrs('A', 'A'), ], [] ),                                                             # LD A,A
    0xC1 : (0, [],                  [ SR(), SR(compound=high_after_low, action=LDr("BC")) ]),         # POP BC
    0xC3 : (0, [],                  [ OD(), OD(compound=high_after_low, action=JP) ]),                # JP nn
    0xC5 : (1, [],                  [ SW(source="B"), SW(source="C") ]),                              # PUSH BC
    0xD1 : (0, [],                  [ SR(), SR(compound=high_after_low, action=LDr("DE")) ]),         # POP DE
    0xD5 : (1, [],                  [ SW(source="D"), SW(source="E") ]),                              # PUSH DE
    0xE1 : (0, [],                  [ SR(), SR(compound=high_after_low, action=LDr("HL")) ]),         # POP HL
    0xE5 : (1, [],                  [ SW(source="H"), SW(source="L") ]),                              # PUSH HL
    0xED : (0, [MB], []),                                                                             # -- Byte one of multibyte OPCODE
    0xDD : (0, [MB], []),                                                                             # -- Byte one of multibyte OPCODE
    0xF1 : (0, [],                  [ SR(), SR(compound=high_after_low, action=LDr("AF")) ]),         # POP AF
    0xF5 : (1, [],                  [ SW(source="A"), SW(source="F") ]),                              # PUSH AF
    0xF9 : (0, [ LDrs('SP', 'HL') ], []),                                                             # LD SP,HL 
    0xFD : (0, [MB], []),                                                                             # -- Byte one of multibyte OPCODE

    # Multibyte opcodes
    (0xDD, 0x21) : (0, [],                [ OD(), OD(compound=high_after_low, action=LDr('IX')) ]),   # LD IX,nn
    (0xDD, 0x22) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="IXL"),
                                            MW(source="IXH")]),                                       # LD (nn),IX
    (0xDD, 0x2A) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('IXL')), MR(action=LDr('IXH')) ]),          # LD IX,(nn)
    (0xDD, 0x36) : (0, [],                [ OD(key='address', signed=True),
                                                OD(key='value'),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW() ]),                                              # LD (IX+d),n
    (0xDD, 0x46) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("B")) ]),                               # LD B,(IX+d)
    (0xDD, 0x4E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("C")) ]),                               # LD C,(IX+d)
    (0xDD, 0x56) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("D")) ]),                               # LD D,(IX+d)
    (0xDD, 0x5E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("E")) ]),                               # LD E,(IX+d)
    (0xDD, 0x66) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("H")) ]),                               # LD H,(IX+d)
    (0xDD, 0x6E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("L")) ]),                               # LD L,(IX+d)
    (0xDD, 0x70) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="B") ]),                                    # LD (IX+d),B
    (0xDD, 0x71) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="C") ]),                                    # LD (IX+d),C
    (0xDD, 0x72) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="D") ]),                                    # LD (IX+d),D
    (0xDD, 0x73) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="E") ]),                                    # LD (IX+d),E
    (0xDD, 0x74) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="H") ]),                                    # LD (IX+d),H
    (0xDD, 0x75) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="L") ]),                                    # LD (IX+d),L
    (0xDD, 0x77) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MW(source="A") ]),                                    # LD (IX+d),A
    (0xDD, 0x7E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IX') }),
                                                MR(action=LDr("A")) ]),                               # LD A,(IX+d)
    (0xDD, 0xE1) : (0, [],                [ SR(), SR(compound=high_after_low, action=LDr("IX")) ]),   # POP IX
    (0xDD, 0xE5) : (1, [],                [ SW(source="IXH"), SW(source="IXL") ]),                    # PUSH IX
    (0xDD, 0xF9) : (0, [LDrs('SP','IX'),],[]),                                                        # LD SP,IX
    (0xED, 0x43) : (0, [],                [ OD(key="address"),
                                            OD(key="address",
                                            compound=high_after_low),
                                            MW(source="C"), MW(source="B") ]),                        # LD (nn),BC
    (0xED, 0x47) : (0, [LDrs('I', 'A'),], []),                                                        # LD I,A
    (0xED, 0x4B) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('C')), MR(action=LDr('B')) ]),              # LD BC,(nn)
    (0xED, 0x4F) : (0, [LDrs('I', 'R'),], []),                                                        # LD R,A
    (0xED, 0x53) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="E"),
                                            MW(source="D") ]),                                        # LD (nn),DE
    (0xED, 0x57) : (0, [LDrs('A', 'I'),], []),                                                        # LD A,I
    (0xED, 0x5B) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('E')), MR(action=LDr('D')) ]),              # LD DE,(nn)
    (0xED, 0x5F) : (0, [LDrs('A', 'R'),], []),                                                        # LD A,R
    (0xED, 0x73) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="SPL"),
                                            MW(source="SPH") ]),                                      # LD (nn),SP
    (0xED, 0x7B) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('SPL')), MR(action=LDr('SPH')) ]),          # LD SP,(nn)
    (0xFD, 0x21) : (0, [],                [ OD(), OD(compound=high_after_low, action=LDr('IY')) ]),   # LD IY,nn
    (0xFD, 0x22) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="IYL"),
                                            MW(source="IYH") ]),                                      # LD (nn),IY
    (0xDD, 0x2A) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('IYL')), MR(action=LDr('IYH')) ]),          # LD IY,(nn)
    (0xFD, 0x36) : (0, [],                [ OD(key='address', signed=True),
                                                OD(key='value'),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW() ]),                                              # LD (IY+d),n
    (0xFD, 0x46) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("B")) ]),                               # LD B,(IY+d)
    (0xFD, 0x4E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("C")) ]),                               # LD C,(IY+d)
    (0xFD, 0x56) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("D")) ]),                               # LD D,(IY+d)
    (0xFD, 0x5E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("E")) ]),                               # LD E,(IY+d)
    (0xFD, 0x66) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("H")) ]),                               # LD H,(IY+d)
    (0xFD, 0x6E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("L")) ]),                               # LD L,(IY+d)
    (0xFD, 0x70) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="B") ]),                                    # LD (IY+d),B
    (0xFD, 0x71) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="C") ]),                                    # LD (IY+d),C
    (0xFD, 0x72) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="D") ]),                                    # LD (IY+d),D
    (0xFD, 0x73) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="E") ]),                                    # LD (IY+d),E
    (0xFD, 0x74) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="H") ]),                                    # LD (IY+d),H
    (0xFD, 0x75) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="L") ]),                                    # LD (IY+d),L
    (0xFD, 0x77) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MW(source="A") ]),                                    # LD (IY+d),A
    (0xFD, 0x7E) : (0, [],                [ OD(key='address', signed=True),
                                                IO(5, True, transform={ 'address' : add_register('IY') }),
                                                MR(action=LDr("A")) ]),                               # LD A,(IY+d)
    (0xFD, 0xE1) : (0, [],                [ SR(), SR(compound=high_after_low, action=LDr("IY")) ]),   # POP IY
    (0xFD, 0xE5) : (1, [],                [ SW(source="IYH"), SW(source="IYL") ]),                    # PUSH IY
    (0xFD, 0xF9) : (0, [LDrs('SP','IY'),],[]),                                                        # LD SP,IY
    }

def decode_instruction(instruction):
    """Decode an instruction code and return a tuple of:
    (extra_time_for_OCF, [list of callables as side-effects of OCF], [ list of new machine states to add to pipeline ])"""
    if instruction in INSTRUCTION_STATES:
        return INSTRUCTION_STATES[instruction]
    raise UnrecognisedInstructionError(instruction)