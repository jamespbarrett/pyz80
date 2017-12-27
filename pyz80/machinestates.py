__all__ = [ "MachineState", "OCF", "UnrecognisedInstructionError" ]

class UnrecognisedInstructionError(Exception):
    def __init__(self, inst):
        self.inst = inst
        if isinstance(inst, tuple):
            inst = "(" + ', '.join('0x{:X}'.format(i) for i in inst) + ")"
        else:
            inst = "0x{:X}".format(inst)
        super(UnrecognisedInstructionError, self).__init__("Unrecognised Instruction {}".format(inst))


# Actions which can be triggered at end of machine states

def JP(value=None, key=None, source=None):
    """Jump to the second parameter (an address)"""
    def _inner(state, *args):
        if callable(value):
            target = value(state)
        elif value is not None:
            target = value
        elif source is not None:
            target = getattr(state.cpu.reg, source)
        elif key is not None:
            target = state.kwargs[key]
        elif len(args) > 0:
            target = args[0]
        else:
            target = state.kwargs["value"]
        state.cpu.reg.PC = target
    return _inner

def JR(value=None, key="value"):
    """Jump to PC plus the second parameter (an address) (or other source if provided)"""
    def _inner(state, *args):
        if callable(value):
            target = value(state)
        elif value is not None:
            target = value
        elif len(args) > 0:
            target = args[0]
        else:
            target = state.kwargs[key]
        state.cpu.reg.PC += target
    return _inner

def LDr(reg, value=None, key="value"):
    """Load into the specified register"""
    def _inner(state, *args):
        if callable(value):
            v = value(state, *args)
        elif value is not None:
            v = value
        elif len(args) > 0:
            v = args[0]
        else:
            v = state.kwargs[key]
        setattr(state.cpu.reg, reg, v)
    return _inner

def LDrs(r,s):
    """Load from the specified register into the specified register"""
    def _inner(state, *args):
        setattr(state.cpu.reg, r, getattr(state.cpu.reg, s))
    return _inner

def RRr(n,reg=None, value=None):
    """Load the value from the specified register and store as a key in the kwargs of the state"""
    def _inner(state, *args):
        if reg is not None:
            v = getattr(state.cpu.reg, reg)
        elif callable(value):
            v = value(state, *args)
        elif value is not None:
            v = value
        elif len(args) > 0:
            v = args[0]
        else:
            raise Exception
        state.kwargs[n] = v
    return _inner

def EX(a=None, b=None):
    """Exchange the AF and AF' registers"""
    def _inner(state, *args):
        if a is None or b is None:
            state.cpu.reg.ex()
        else:
            tmp = getattr(state.cpu.reg, a)
            setattr(state.cpu.reg, a, getattr(state.cpu.reg, b))
            setattr(state.cpu.reg, b, tmp)
    return _inner

def EXX():
    """Exchange the working registers with their shadows"""
    def _inner(state, *args):
        state.cpu.reg.exx()
    return _inner

def add_register(r):
    """Load a value from the specified register and add it to the parameter"""
    def _inner(state, d, *args):
        return getattr(state.cpu.reg, r) + d
    return _inner

def subfrom(r="A"):
    """Subtract the value from the value in a register (A by default)."""
    def _inner(state, d, *args):
        return getattr(state.cpu.reg, r) - d
    return _inner

def do_each(*actions):
    """Perform a series of actions."""
    def _inner(state, *args):
        for action in actions:
            action(state, *args)
    return _inner

def inc(reg):
    """Increment a register"""
    def _inner(state, *args):
        if len(reg) % 2 == 0:
            setattr(state.cpu.reg, reg, (getattr(state.cpu.reg, reg) + 1)&0xFFFF)
        else:
            setattr(state.cpu.reg, reg, (getattr(state.cpu.reg, reg) + 1)&0xFF)
    return _inner

def dec(reg):
    """Decrement a register"""
    def _inner(state, *args):
        if len(reg)%2 == 0:
            setattr(state.cpu.reg, reg, (0xFFFF + getattr(state.cpu.reg, reg))&0xFFFF)
        else:
            setattr(state.cpu.reg, reg, (0xFF + getattr(state.cpu.reg, reg))&0xFF)
    return _inner

def on_zero(reg, action):
    """Only take action if register is zero"""
    def _inner(state, *args):
        if getattr(state.cpu.reg, reg) == 0:
            action(state, *args)
    return _inner

def on_flag(flag, action):
    """Only take action is flag is set"""
    def _inner(state, *args):
        if state.cpu.reg.getflag(flag) == 1:
            action(state, *args)
    return _inner

def unless_flag(flag, action):
    """Only take action is flag is not set"""
    def _inner(state, *args):
        if state.cpu.reg.getflag(flag) == 0:
            action(state, *args)
    return _inner

def on_condition(condition , action):
    """Only take the action is the condition returns True"""
    def _inner(state, *args):
        if condition(state, *args):
            action(state, *args)
    return _inner

def force_flag(flag, value):
    """Clear a flag"""
    def _inner(state, *args):
        if callable(value):
            v = value(state, *args)
        else:
            v = value
        if v == 0:
            state.cpu.reg.resetflag(flag)
        else:
            state.cpu.reg.setflag(flag)
    return _inner

def clear_flag(flag):
    """Clear a flag"""
    def _inner(state, *args):
        state.cpu.reg.resetflag(flag)
    return _inner

def early_abort():
    """Abort instruction"""
    def _inner(state, *args):
        while len(state.pipeline) > 1:
            state.pipeline.pop()
    return _inner

def set_flags(flags="SZ5-3---", key="value", source=None, value=None, dest=None):
    """Set the flags register according to the passed value"""
    def _inner(state, *args):
        if value is not None:
            if callable(value):
                D = value(state, *args)
            else:
                D = value
        elif source is not None:
            D = getattr(state.cpu.reg, source)
        elif len(args) > 0:
            D = args[0]
            print D
        else:
            D = state.kwargs[key]
        d = D&0xFF

        if flags[0] == 'S':
            if (d >> 7)&0x1 == 1:
                state.cpu.reg.setflag('S')
            else:
                state.cpu.reg.resetflag('S')
        if flags[1] == 'Z':
            if (d == 0):
                state.cpu.reg.setflag('Z')
            else:
                state.cpu.reg.resetflag('Z')
        if flags[2] == '5':
            if (d >> 5)&0x1 == 1:
                state.cpu.reg.setflag('5')
            else:
                state.cpu.reg.resetflag('5')
        if flags[4] == '3':
            if (d >> 3)&0x1 == 1:
                state.cpu.reg.setflag('3')
            else:
                state.cpu.reg.resetflag('3')
        if flags[5] == '*':
            if state.cpu.iff2 == 1:
                state.cpu.reg.setflag('P')
            else:
                state.cpu.reg.resetflag('P')
        elif flags[5] == "V":
            if D > 127 or D < -128:
                state.cpu.reg.setflag("V")
            else:
                state.cpu.reg.resetflag("V")
        elif flags[5] == "P":
            p = d
            while p > 1:
                p = (p&0x1) ^ (p >> 1)
            if p == 0:
                state.cpu.reg.setflag("P")
            else:
                state.cpu.reg.resetflag("P")
        if flags[7] == 'C':
            if D > 255 or D < 0:
                state.cpu.reg.setflag("C")
            else:
                state.cpu.reg.resetflag("C")
        for n in range(0,7):
            if flags[7-n] == '1':
                state.cpu.reg.F = state.cpu.reg.F | (1 << n)
            elif flags[7-n] == '0':
                state.cpu.reg.F = state.cpu.reg.F & (0xFF - (1 << n))
        if key is not None:
            state.kwargs[key] = d
        if dest is not None:
            setattr(state.cpu.reg, dest, d)
    return _inner

def daa():
    def _inner(state, *args):
        A = state.cpu.reg.A
        C = (state.cpu.reg.F >> 0)&0x1
        H = (state.cpu.reg.F >> 4)&0x1
        N = (state.cpu.reg.F >> 1)&0x1

        if N == 0:
            F = 0
            if A&0xF > 9 or H != 0:
                A += 0x06
            if (A>>4) > 9 or C != 0:
                A += 0x60
                F = 0x01
        else:
            F = 0
            if (A&0xF) > 9 or H != 0:
                A -= 0x06
            if (A>>4) > 9 or C != 0:
                A -= 0x60
                F = 0x01
        A &= 0xFF
        F |= (N << 1)
        F |= (A&0xA8)
        if A == 0x00:
            F |= 0x40
        state.cpu.reg.A = A
        state.cpu.reg.F = F
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

def high_after_low(x,y):
    return ((x << 8) | y)

def OCF(prefix=None):
    class _OCF(MachineState):
        """This state fetches an OP Code from memory and advances the PC in 4 t-cycles.
        Initialisation Parameters:
        - Optionally: 'prefix' for a multibyte op-code this will be prefixed to what is loaded
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

        def __init__(self):
            self.prefix = prefix
            super(_OCF,self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            PC = self.cpu.reg.PC
            yield

            inst = self.cpu.membus.read(PC)
            if isinstance(self.prefix, int):
                inst = (self.prefix, inst)
            elif isinstance(self.prefix, tuple):
                inst = tuple(list(self.prefix) + [ inst ])
            yield

            (extra_clocks, actions, states) = decode_instruction(inst)
            self.cpu.reg.PC = PC + 1
            states = [ state().setcpu(self.cpu) for state in states ]
            yield

            for n in range(0,extra_clocks-1):
                yield

            self.pipeline.extend(states)
            for action in actions:
                action(self)
            raise StopIteration
    return _OCF

def OD(compound=high_after_low, action=None, key="value", signed=False):
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
            if self.action is not None:
                self.action(self, D)
            else:
                self.kwargs[self.key] = D
            raise StopIteration
    return _OD

def MR(address=None, indirect=None, compound=high_after_low, action=None, incaddr=True, verbose=False):
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
            self.incaddr  = incaddr
            self.verbose  = verbose
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
                        if self.verbose:
                            print "MR: Address 0x{:X} taken from kwargs[{}]".format(self.address, 'address')
                else:
                    self.address = getattr(self.cpu.reg, self.indirect)
                    if self.verbose:
                        print "MR: Address 0x{:X} taken from register {}".format(self.address, self.indirect)
            yield

            D = self.cpu.membus.read(self.address)
            if self.verbose:
                print "MR: Data 0x{:X} read from address 0x{:X}".format(D, self.address)
            yield

            if 'value' in self.kwargs and self.compound is not None:
                D = self.compound(D, self.kwargs['value'])
                if self.verbose:
                    print "MR: Compound data with 0x{:X} to get 0x{:X}".format(self.kwargs['value'], D)
            if self.incaddr:
                self.kwargs['address'] = self.address + 1
                if self.verbose:
                    print "MR: Increment address to 0x{:X}".format(self.kwargs['address'])
            if self.action is not None:
                self.action(self, D)
                if self.verbose:
                    print "MR: Performing Action"
            else:
                self.kwargs['value'] = D
                if self.verbose:
                    print "MR: Setting 'value' in kwargs to 0x{:X}".format(D)
            raise StopIteration

    return _MR

def MW(address=None, indirect=None, value=None, source=None, action=None, extra=0, verbose=False):
    class _MW(MachineState):
        """This state writes a data byte to memory at a specified address (possibly using register indirect or indexed addressing):
        Initialisation Parameters:
        - Optionally: 'address' the address in memory to write to
        - Optionally: 'indirect' the name of the register to take the address from
        - Optionally: 'value' the value to write.
        - Optionally: 'source' a register from which to obtain the value to write. (if Neither value nor source is specified it will be cascaded in)
        - Optionally: 'action' an action to be taken at the end of the state
        - Optionally: 'extra' a number of extra t-cycles to wait for
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
            self.source   = source
            self.action   = action
            self.extra    = extra
            self.verbose  = verbose
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
                        if self.verbose:
                            print "MW: Address 0x{:X} from kwargs".format(self.address)
                else:
                    self.address = getattr(self.cpu.reg, self.indirect)
                    if self.verbose:
                        print "MW: Address 0x{:X} from register {}".format(self.address, self.indirect)
            yield

            if self.value is None:
                if self.source is None:
                    if 'value' not in self.kwargs:
                        raise Exception("MR without either value or source specified")
                    else:
                        self.value = self.kwargs['value']
                        if self.verbose:
                            print "MW: Value 0x{:X} from kwargs".format(self.value)
                else:
                    self.value = getattr(self.cpu.reg, self.source)
                    if self.verbose:
                        print "MW: Value 0x{:X} from register {}".format(self.value, self.source)
            elif callable(self.value):
                self.value = self.value(self)
                if self.verbose:
                    print "MW: Value 0x{:X} from callable".format(self.value)
            yield

            self.cpu.membus.write(self.address, self.value)
            if self.verbose:
                print "MW: Writing 0x{:X} to 0x{:X}".format(self.value, self.address)
            self.kwargs['address'] = self.address + 1
            if self.verbose:
                print "MW: Increment Address to 0x{:X}".format(self.kwargs['address'])

            for n in range(0,self.extra):
                yield

            if self.action is not None:
                self.action(self, self.value)
                if self.verbose:
                    print "MW: Taking action"
            raise StopIteration
        
    return _MW

def SR(compound=high_after_low, action=None, extra=0):
    class _SR(MachineState):
        """This state fetches a data byte from memory at the top of the stack and increments the stack pointer:
        Initialisation Parameters:
        - Optionally: 'compound' a method that takes two parameters (new, old) used to combine
        the old value of 'value' with the new one.
        - Optionally: 'action' a method which takes a two parameters, the state and a single integer. 
        It will be called with the final value of 'value' as the last operation in the state. 
        - Optionally: 'extra' a number of extra t-cycles to wait for
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
            self.extra    = extra
            super(_SR, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            self.address = self.cpu.reg.SP
            yield

            D = self.cpu.membus.read(self.address)
            yield

            for n in range(0,self.extra):
                yield

            if 'value' in self.kwargs and self.compound is not None:
                D = self.compound(D, self.kwargs['value'])
            self.kwargs['value'] = D
            self.cpu.reg.SP = self.cpu.reg.SP + 1
            if self.action is not None:
                self.action(self, D)
            raise StopIteration

    return _SR

def SW(source=None, key='value', extra=0, action=None):
    class _SW(MachineState):
        """This state decrements the stack pointer and writes a data byte to memory at the top of the stack:
        Initialisation Parameters:
        - Optionally: 'source' the register from which to take the value
        - Optionally: 'key' a key to use instead of 'value' to access the data to be written
        - Optionally: 'extra' a number of extra t-cycles to wait for
        Args In:
        - Possibly a value if none is specified by source
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
            self.key    = key
            self.extra  = extra
            self.action = action
            super(_SW, self).__init__()

        def fetchlocked(self):
            return True

        def run(self):
            self.cpu.reg.SP = self.cpu.reg.SP - 1
            yield

            for n in range(0,self.extra):
                yield

            self.address = self.cpu.reg.SP
            yield

            if self.source is not None:
                D = getattr(self.cpu.reg, self.source)
            else:
                D = self.kwargs[self.key]

            self.cpu.membus.write(self.address, D)

            if self.action is not None:
                self.action(self, D)
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

def ADC16(reg):
    """This instruction gets messy in the table, so we use this function to template it"""
    return [ RRr('value',   'HL'),
             RRr('summand', reg),
             force_flag('H', lambda  state : 1 if (((state.kwargs['summand']>>8)&0xF)+((state.kwargs['value']>>8)&0xF)+
                                                       (((state.kwargs['summand']&0xFF) + (state.kwargs['value']&0xFF)
                                                             +state.cpu.reg.getflag('C'))>>8) > 0xF) else 0),
             LDr('HL', value=lambda state : (state.kwargs['summand'] + state.kwargs['value'] + state.cpu.reg.getflag('C'))&0xFFFF),
             set_flags("S-5-3V0C", value=lambda state : (state.kwargs['summand'] >> 8) + (state.kwargs['value']>>8) +
                           (((state.kwargs['summand']&0xFF) + (state.kwargs['value']&0xFF) + state.cpu.reg.getflag('C'))>>8)),
             force_flag('Z', value=lambda state : 1 if state.cpu.reg.HL == 0x0000 else 0),]

def SBC16(reg):
    """This instruction gets messy in the table, so we use this function to template it"""
    return [ RRr('value',   'HL'),
             RRr('summand', value=lambda state : (-getattr(state.cpu.reg,reg))&0xFFFF),
             force_flag('H', lambda  state : 1 if (((state.kwargs['summand']>>8)&0xF)+((state.kwargs['value']>>8)&0xF)+
                                                       (((state.kwargs['summand']&0xFF) + (state.kwargs['value']&0xFF)
                                                             -state.cpu.reg.getflag('C'))>>8) > 0xF) else 0),
             LDr('HL', value=lambda state : (state.kwargs['summand'] + state.kwargs['value'] - state.cpu.reg.getflag('C'))&0xFFFF),
             set_flags("S-5-3V1C", value=lambda state : (state.kwargs['summand'] >> 8) + (state.kwargs['value']>>8) +
                           (((state.kwargs['summand']&0xFF) + (state.kwargs['value']&0xFF) - state.cpu.reg.getflag('C'))>>8)),
             force_flag('Z', value=lambda state : 1 if state.cpu.reg.HL == 0x0000 else 0),]

def RLC(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) << 1) | (getattr(state.cpu.reg,reg) >> 7), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v << 1) | (v >> 7), key=key)

def RL(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) << 1) | (state.cpu.reg.getflag('C')), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v << 1) | (state.cpu.reg.getflag('C')), key=key)

def RRC(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) >> 1) | ((getattr(state.cpu.reg,reg)&0x01) << 7) | ((getattr(state.cpu.reg,reg)&0x01) << 8), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v >> 1) | ((v&0x01) << 7) | ((v&0x01) << 8), key=key)

def RR(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) >> 1) | (state.cpu.reg.getflag('C') << 7) | ((getattr(state.cpu.reg,reg)&0x01) << 8), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v >> 1) | (state.cpu.reg.getflag('C') << 7) | ((v&0x01) << 8), key=key)

def SLA(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) << 1), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v << 1), key=key)

def SRA(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) >> 1) | (getattr(state.cpu.reg,reg)&0x80) | ((getattr(state.cpu.reg,reg)&0x01) << 8), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v >> 1) | (v&0x80) | ((v&0x01) << 8), key=key)

def SL1(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) << 1) | 0x01, dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v << 1) | 0x01, key=key)

def SRL(reg=None, key='value'):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("--503-0C", value=lambda state : (getattr(state.cpu.reg,reg) >> 1) | ((getattr(state.cpu.reg,reg)&0x01) << 8), dest=reg)
    else:
        return set_flags("--503-0C", value=lambda state,v : (v >> 1) | ((v&0x01) << 8), key=key)

def BIT(n, reg=None):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return set_flags("SZ513P0-", value=lambda state : (getattr(state.cpu.reg,reg)&(1 << n)))
    else:
        return set_flags("SZ513P0-", value=lambda state,v : (v&(1 << n)))

def RES(n, reg=None, key="value"):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return LDr(reg, value=lambda state : (getattr(state.cpu.reg,reg)&(0xFF - (1 << n))))
    else:
        return RRr(key, value=lambda state,v : (v&(0xFF - (1 << n))))

def SET(n, reg=None, key="value"):
    """This instruction gets a little messy in the table, so this helps simplify it."""
    if reg is not None:
        return LDr(reg, value=lambda state : (getattr(state.cpu.reg,reg)|(1 << n)))
    else:
        return RRr(key, value=lambda state,v : (v|(1 << n)))

INSTRUCTION_STATES = {
    # Single bytes opcodes
    0x00 : (0, [],                  [] ),                                                             # NOP
    0x01 : (0, [],                  [ OD(), OD(action=LDr('BC')) ]),                                  # LD BC,nn
    0x02 : (0, [],                  [ MW(indirect="BC", source="A") ]),                               # LD (BC),A
    0x03 : (0, [ LDr('BC', value=lambda state : (state.cpu.reg.BC + 1)&0xFFFF) ],
                                    [] ),                                                             # INC BC
    0x04 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.B)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.B + 1, key="value"), LDr('B') ],
                                    [] ),                                                             # INC B
    0x05 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.B)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5-3V1-", value=lambda state : state.cpu.reg.B - 1, key="value"), LDr('B') ],
                                    [] ),                                                             # DEC B
    0x06 : (0, [],                  [ OD(action=LDr('B')), ]),                                        # LD B,n
    0x07 : (0, [ RLC("A") ],        []),                                                              # RLCA
    0x08 : (0, [ EX() ],            []),                                                              # EX AF,AF'
    0x09 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.B)&0xF)+((state.cpu.reg.H)&0xF)+((state.cpu.reg.C+state.cpu.reg.L)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.B + state.cpu.reg.H + ((state.cpu.reg.C+state.cpu.reg.L)>>8)),
                 LDr('HL', value=lambda state : (state.cpu.reg.HL + state.cpu.reg.BC)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD HL,BC
    0x0B : (0, [ LDr('BC', value=lambda state : (state.cpu.reg.BC - 1)&0xFFFF) ],
                                    [] ),                                                             # DEC BC
    0x0C : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.C)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.C + 1, key="value"), LDr('C') ],
                                    [] ),                                                             # INC C
    0x0D : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.C)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5H3V1-", value=lambda state : state.cpu.reg.C - 1, key="value"), LDr('C') ],
                                    [] ),                                                             # DEC C
    0x0E : (0, [],                  [ OD(action=LDr('C')), ]),                                        # LD C,n
    0x0F : (0, [ set_flags("--503-0C", value=lambda state : (state.cpu.reg.A >> 1) | ((state.cpu.reg.A&0x01) << 7) | ((state.cpu.reg.A&0x01) << 8), dest="A") ],
                                    []),                                                              # RRCA
    0x0A : (0, [],                  [ MR(indirect="BC", action=LDr("A")) ]),                          # LD A,(BC)
    0x10 : (1, [],                  [ OD(action=do_each(LDr("B", value=lambda state,v: (state.cpu.reg.B-1)&0xFF),
                                                        on_condition(lambda state,v : (state.cpu.reg.B == 0x00), early_abort()),
                                                        RRr("value"))),
                                      IO(5, True, action=JR()) ]),                                    # DJNZ
    0x11 : (0, [],                  [ OD(), OD(action=LDr('DE')) ]),                                  # LD DE,nn
    0x12 : (0, [],                  [ MW(indirect="DE", source="A") ]),                               # LD (DE),A
    0x13 : (0, [ LDr('DE', value=lambda state : (state.cpu.reg.DE + 1)&0xFFFF) ],
                                    [] ),                                                             # INC DE
    0x14 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.D)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.D + 1, key="value"), LDr('D') ],
                                    [] ),                                                             # INC D
    0x15 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.D)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5H3V1-", value=lambda state : state.cpu.reg.D - 1, key="value"), LDr('D') ],
                                    [] ),                                                             # DEC D
    0x16 : (0, [],                  [ OD(action=LDr('D')), ]),                                        # LD D,n
    0x17 : (0, [ RL("A") ],         []),                                                              # RLA
    0x18 : (0, [],                  [ OD(signed=True), IO(5, True, action=JR()) ]),                   # JR nn
    0x19 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.D)&0xF)+((state.cpu.reg.H)&0xF)+((state.cpu.reg.E+state.cpu.reg.L)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.D + state.cpu.reg.H + ((state.cpu.reg.E+state.cpu.reg.L)>>8)),
                 LDr('HL', value=lambda state : (state.cpu.reg.HL + state.cpu.reg.DE)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD HL,DE
    0x1B : (0, [ LDr('DE', value=lambda state : (state.cpu.reg.DE - 1)&0xFFFF) ],
                                    [] ),                                                             # DEC DE
    0x1A : (0, [],                  [ MR(indirect="DE", action=LDr("A")) ]),                          # LD A,(DE)
    0x1C : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.E)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.E + 1, key="value"), LDr('E') ],
                                    [] ),                                                             # INC E
    0x1D : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.E)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5H3V1-", value=lambda state : state.cpu.reg.E - 1, key="value"), LDr('E') ],
                                    [] ),                                                             # DEC E
    0x1E : (0, [],                  [ OD(action=LDr('E')), ]),                                        # LD E,n
    0x1F : (0, [ RR("A") ],         []),                                                              # RRA
    0x20 : (0, [],                  [ OD(signed=True, action=do_each(RRr("value"), on_flag("Z", early_abort()))),
                                      IO(5, True, action=JR()) ]),                                    # JR NZ,nn
    0x21 : (0, [],                  [ OD(), OD(action=LDr('HL')) ]),                                  # LD HL,nn
    0x22 : (0, [],                  [ OD(key="address"),
                                        OD(key="address",
                                        compound=high_after_low),
                                        MW(source="L"), MW(source="H") ]),                            # LD (nn),HL
    0x23 : (0, [ LDr('HL', value=lambda state : (state.cpu.reg.HL + 1)&0xFFFF) ],
                                    [] ),                                                             # INC HL
    0x24 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.H)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.H + 1, key="value"), LDr('H') ],
                                    [] ),                                                             # INC H
    0x25 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.H)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5H3V1-", value=lambda state : state.cpu.reg.H - 1, key="value"), LDr('H') ],
                                    [] ),                                                             # DEC H
    0x26 : (0, [],                  [ OD(action=LDr('H')), ]),                                        # LD H,n
    0x27 : (0, [ daa() ],                  []),                                                       # DAA
    0x28 : (0, [],                  [ OD(signed=True, action=do_each(RRr("value"), unless_flag("Z", early_abort()))),
                                      IO(5, True, action=JR()) ]),                                    # JR Z,nn
    0x29 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.H)&0xF)+((state.cpu.reg.H)&0xF)+((state.cpu.reg.L+state.cpu.reg.L)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.H + state.cpu.reg.H + ((state.cpu.reg.L+state.cpu.reg.L)>>8)),
                 LDr('HL', value=lambda state : (state.cpu.reg.HL + state.cpu.reg.HL)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD HL,HL
    0x2A : (0, [],                  [ OD(key="address"),
                                      OD(key="address", compound=high_after_low),
                                      MR(action=LDr('L')), MR(action=LDr('H')) ]),                    # LD HL,(nn)
    0x2B : (0, [ LDr('HL', value=lambda state : (state.cpu.reg.HL - 1)&0xFFFF) ],
                                    [] ),                                                             # DEC HL
    0x2C : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.L)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.L + 1, key="value"), LDr('L') ],
                                    [] ),                                                             # INC L
    0x2D : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.L)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5H3V1-", value=lambda state : state.cpu.reg.L - 1, key="value"), LDr('L') ],
                                    [] ),                                                             # DEC L
    0x2E : (0, [],                  [ OD(action=LDr('L')), ]),                                        # LD L,n
    0x2F : (0, [ set_flags("--*1*-1-", source='A'), LDr('A', value=lambda state : (~(state.cpu.reg.A))&0xFF) ],
                                    []),                                                              # CPL
    0x30 : (0, [],                  [ OD(signed=True, action=do_each(RRr("value"), on_flag("C", early_abort()))),
                                      IO(5, True, action=JR()) ]),                                    # JR NC,nn
    0x31 : (0, [],                  [ OD(), OD(action=LDr('SP')) ]),                                  # LD SP,nn
    0x32 : (0, [],                  [ OD(key="address"), OD(compound=high_after_low,key="address"),
                                          MW(source="A") ]),                                          # LD (nn),A
    0x33 : (0, [ LDr('SP', value=lambda state : (state.cpu.reg.SP + 1)&0xFFFF) ],
                                    [] ),                                                             # INC SP
    0x34 : (0, [],                  [ MR(indirect="HL",
                                        action=do_each(force_flag('H', lambda  state,v : 1 if ((v&0xF)+1 > 0xF) else 0),
                                                      set_flags("SZ5-3V0-",
                                                        value=lambda state, v : v+1,
                                                        key="value"))),
                                      MW(indirect="HL" )] ),                                          # INC (HL)
    0x35 : (0, [],                  [ MR(indirect="HL",
                                        action=do_each(
                                            force_flag('H', lambda  state,v : 1 if ((v&0xF)-1 < 0x0) else 0),
                                            set_flags("SZ5H3V1-",
                                                        value=lambda state, v : v-1,
                                                        key="value"))),
                                      MW(indirect="HL" )] ),                                          # DEC (HL)
    0x36 : (0, [],                  [ OD(), MW(indirect="HL") ]),                                     # LD (HL),n
    0x37 : (0, [ LDr('F', value=lambda state : (state.cpu.reg.F&0xC4)|(state.cpu.reg.A&0x28)|(0x01)) ],
                                    [] ),                                                             # SCF
    0x38 : (0, [],                  [ OD(signed=True, action=do_each(RRr("value"), unless_flag("C", early_abort()))),
                                      IO(5, True, action=JR()) ]),                                    # JR C,nn
    0x39 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.SPH)&0xF)+((state.cpu.reg.H)&0xF)+((state.cpu.reg.SPL+state.cpu.reg.L)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.SPH + state.cpu.reg.H + ((state.cpu.reg.SPL+state.cpu.reg.L)>>8)),
                 LDr('HL', value=lambda state : (state.cpu.reg.SP + state.cpu.reg.HL)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD HL,SP
    0x3B : (0, [ LDr('SP', value=lambda state : (state.cpu.reg.SP - 1)&0xFFFF) ],
                                    [] ),                                                             # DEC SP
    0x3C : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+1 > 0xF) else 0),
                 set_flags("SZ5-3V0-", value=lambda state : state.cpu.reg.A + 1, key="value"), LDr('A') ],
                                    [] ),                                                             # INC A
    0x3D : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-1 < 0x0) else 0),
                 set_flags("SZ5H3V1-", value=lambda state : state.cpu.reg.A - 1, key="value"), LDr('A') ],
                                    [] ),                                                             # DEC A
    0x3A : (0, [],                  [ OD(key="address"), OD(compound=high_after_low,key="address"),
                                          MR(action=LDr("A")) ]),                                     # LD A,(nn)
    0x3E : (0, [],                  [ OD(action=LDr('A')), ]),                                        # LD A,n
    0x3F : (0, [ LDr('F', value=lambda state : (state.cpu.reg.F&0xEC)|(~state.cpu.reg.F&0x11)) ],
                                    [] ),                                                             # CCF
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
    0x80 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.B)&0xF) > 0xF) else 0),
                 set_flags("SZ5-3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.B, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD B
    0x81 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.C)&0xF) > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.C, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD C
    0x82 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.D)&0xF) > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.D, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD D
    0x83 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.E)&0xF) > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.E, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD E
    0x84 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.H)&0xF) > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.H, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD H
    0x85 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.L)&0xF) > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.L, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD L
    0x86 : (0, [],                  [ MR(indirect="HL",
                                        action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF) > 0xF) else 0),
                                            set_flags("SZ5H3V0C",
                                                        value=lambda state, v : state.cpu.reg.A + v,
                                                        dest="A"))) ] ),                              # ADD (HL)
    0x87 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.A)&0xF) > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.A, key="value"),
                 LDr('A') ],        [] ),                                                             # ADD A
    0x88 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.B)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.B + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC B
    0x89 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.C)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.C + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC C
    0x8A : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.D)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.D + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC D
    0x8B : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.E)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.E + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC E
    0x8C : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.H)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.H + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC H
    0x8D : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.L)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.L + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC L
    0x8E : (0, [],                  [ MR(indirect="HL",
                                        action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                                            set_flags("SZ5H3V0C",
                                                        value=lambda state, v : state.cpu.reg.A + v + state.cpu.reg.getflag('C'),
                                                        dest="A"))) ] ),                               # ADC (HL)
    0x8F : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)+((state.cpu.reg.A)&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                 set_flags("SZ5H3V0C", value=lambda state : state.cpu.reg.A + state.cpu.reg.A + state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # ADC A
    0x90 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.B)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.B, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB B
    0x91 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.C)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.C, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB C
    0x92 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.D)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.D, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB D
    0x93 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.E)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.E, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB E
    0x94 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.H)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.H, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB H
    0x95 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.L)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.L, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB L
    0x96 : (0, [],                  [ MR(indirect="HL",
                                        action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) < 0x0) else 0),
                                            set_flags("SZ5H3V1C",
                                                        value=lambda state, v : state.cpu.reg.A - v,
                                                        dest="A"))) ] ),                               # SUB (HL)
    0x97 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.A)&0xF) < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.A, key="value"),
                 LDr('A') ],        [] ),                                                             # SUB A
    0x98 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.B)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.B - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC B
    0x99 : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.C)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.C - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC C
    0x9A : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.D)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.D - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC D
    0x9B : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.E)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.E - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC E
    0x9C : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.H)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.H - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC H
    0x9D : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.L)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.L - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC L
    0x9E : (0, [],                  [ MR(indirect="HL",
                                        action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                                            set_flags("SZ5H3V1C",
                                                        value=lambda state, v : state.cpu.reg.A - v - state.cpu.reg.getflag('C'),
                                                        dest="A"))) ] ),                               # SBC (HL)
    0x9F : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.A)&0xF)-((state.cpu.reg.A)&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                 set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.A - state.cpu.reg.getflag('C'), key="value"),
                 LDr('A') ],        [] ),                                                             # SBC A
    0xA0 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.B, key="value"),
                 LDr('A') ],        [] ),                                                             # AND B
    0xA1 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.C, key="value"),
                 LDr('A') ],        [] ),                                                             # AND C
    0xA2 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.D, key="value"),
                 LDr('A') ],        [] ),                                                             # AND D
    0xA3 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.E, key="value"),
                 LDr('A') ],        [] ),                                                             # AND E
    0xA4 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.H, key="value"),
                 LDr('A') ],        [] ),                                                             # AND H
    0xA5 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.L, key="value"),
                 LDr('A') ],        [] ),                                                             # AND L
    0xA6 : (0, [],                  [ MR(indirect="HL",
                                        action=set_flags("SZ513P00",
                                                        value=lambda state, v : state.cpu.reg.A & v,
                                                        dest="A")) ] ),                               # AND (HL)
    0xA7 : (0, [ set_flags("SZ513P00", value=lambda state : state.cpu.reg.A & state.cpu.reg.A, key="value"),
                 LDr('A') ],        [] ),                                                             # AND A
    0xA8 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.B, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR B
    0xA9 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.C, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR C
    0xAA : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.D, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR D
    0xAB : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.E, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR E
    0xAC : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.H, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR H
    0xAD : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.L, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR L
    0xAE : (0, [],                  [ MR(indirect="HL",
                                        action=set_flags("SZ503P00",
                                                        value=lambda state, v : state.cpu.reg.A ^ v,
                                                        dest="A")) ] ),                               # XOR (HL)
    0xAF : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A ^ state.cpu.reg.A, key="value"),
                 LDr('A') ],        [] ),                                                             # XOR A
    0xB0 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.B, key="value"),
                 LDr('A') ],        [] ),                                                             # OR B
    0xB1 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.C, key="value"),
                 LDr('A') ],        [] ),                                                             # OR C
    0xB2 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.D, key="value"),
                 LDr('A') ],        [] ),                                                             # OR D
    0xB3 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.E, key="value"),
                 LDr('A') ],        [] ),                                                             # OR E
    0xB4 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.H, key="value"),
                 LDr('A') ],        [] ),                                                             # OR H
    0xB5 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.L, key="value"),
                 LDr('A') ],        [] ),                                                             # OR L
    0xB6 : (0, [],                  [ MR(indirect="HL",
                                        action=set_flags("SZ503P00",
                                                        value=lambda state, v : state.cpu.reg.A | v,
                                                        dest="A")) ] ),                               # OR (HL)
    0xB7 : (0, [ set_flags("SZ503P00", value=lambda state : state.cpu.reg.A | state.cpu.reg.A, key="value"),
                 LDr('A') ],        [] ),                                                             # OR A
    0xB8 : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.B, key="value") ],
                                    [] ),                                                             # CP B
    0xB9 : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.C, key="value"), ],
                                    [] ),                                                             # CP C
    0xBA : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.D, key="value"), ],
                                    [] ),                                                             # CP D
    0xBB : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.E, key="value"), ],
                                    [] ),                                                             # CP E
    0xBC : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.H, key="value"), ],
                                    [] ),                                                             # CP H
    0xBD : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.L, key="value"), ],
                                    [] ),                                                             # CP L
    0xBE : (0, [],                  [ MR(indirect="HL",
                                        action=set_flags("SZ5H3V1C",
                                                        value=lambda state, v : state.cpu.reg.A - v,)
                                                                 ) ] ),                               # CP (HL)
    0xBF : (0, [ set_flags("SZ5H3V1C", value=lambda state : state.cpu.reg.A - state.cpu.reg.A, key="value"), ],
                                    [] ),                                                             # CP A
    0xC0 : (1, [ on_flag('Z', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET NZ
    0xC1 : (0, [],                  [ SR(), SR(action=LDr("BC")) ]),                                  # POP BC
    0xC2 : (0, [],                  [ OD(), OD(action=unless_flag("Z",JP())) ]),                      # JP NZ,nn
    0xC3 : (0, [],                  [ OD(), OD(action=JP()) ]),                                       # JP nn
    0xC4 : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              on_flag("Z", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL NZ,nn
    0xC5 : (1, [],                  [ SW(source="B"), SW(source="C") ]),                              # PUSH BC
    0xC6 : (0, [],                  [ OD(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF) > 0xF) else 0),
                                                set_flags("SZ5H3V0C",
                                                        value=lambda state, v : state.cpu.reg.A + v,
                                                        dest="A"))) ] ),                              # ADD n
    0xC8 : (1, [ unless_flag('Z', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET NZ
    0xC9 : (0, [],                  [ SR(), SR(action=JP()) ]),                                       # RET
    0xCA : (0, [],                  [ OD(), OD(action=on_flag("Z",JP())) ]),                          # JP Z,nn
    0xCB : (0, [],                  [ OCF(prefix=0xCB) ]),                                            # -- Byte one of multibyte OPCODE
    0xCC : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              unless_flag("Z", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL Z,nn
    0xCD : (0, [],                  [ OD(), OD(action=RRr("target")),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL nn
    0xCE : (0, [],                  [ OD(action=do_each(force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                                                        set_flags("SZ5H3V0C",
                                                        value=lambda state, v : state.cpu.reg.A + v + state.cpu.reg.getflag('C'),
                                                        dest="A"))) ] ),                              # ADC n
    0xD0 : (1, [ on_flag('C', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET NC
    0xD1 : (0, [],                  [ SR(), SR(action=LDr("DE")) ]),                                  # POP DE
    0xD2 : (0, [],                  [ OD(), OD(action=unless_flag("C",JP())) ]),                      # JP NC,nn
    0xD4 : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              on_flag("C", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL NC,nn
    0xD5 : (1, [],                  [ SW(source="D"), SW(source="E") ]),                              # PUSH DE
    0xD6 : (0, [],                  [ OD(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) < 0x0) else 0),
                                                set_flags("SZ5H3V1C",
                                                        value=lambda state, v : state.cpu.reg.A - v,
                                                        dest="A"))) ] ),                              # SUB n
    0xD8 : (1, [ unless_flag('C', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET C
    0xDA : (0, [],                  [ OD(), OD(action=on_flag("C",JP())) ]),                          # JP C,nn
    0xDC : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              unless_flag("C", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL C,nn
    0xDE : (0, [],                  [ OD(action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                                            set_flags("SZ5H3V1C",
                                                        value=lambda state, v : state.cpu.reg.A - v - state.cpu.reg.getflag('C'),
                                                        dest="A"))) ] ),                               # SBC n
    0xD9 : (0, [ EXX() ],           []),                                                              # EXX
    0xE0 : (1, [ on_flag('P', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET PO
    0xE1 : (0, [],                  [ SR(), SR(action=LDr("HL")) ]),                                  # POP HL
    0xE2 : (0, [],                  [ OD(), OD(action=unless_flag("P",JP())) ]),                      # JP PO,nn
    0xE3 : (0, [ RRr('H','H'), RRr('L','L') ],  [ SR(), SR(action=LDr("HL"), extra=1),
                                                      SW(key="H"), SW(key="L", extra=2) ]),           # EX (SP),HL
    0xE4 : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              on_flag("P", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL PO,nn
    0xE5 : (1, [],                  [ SW(source="H"), SW(source="L") ]),                              # PUSH HL
    0xE6 : (0, [],                  [ OD(action=set_flags("SZ513P00",
                                                        value=lambda state, v : state.cpu.reg.A & v,
                                                        dest="A")) ] ),                               # AND n
    0xE8 : (1, [ unless_flag('P', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET PE
    0xE9 : (0, [ JP(source="HL") ], []),                                                              # JP (HL)
    0xEC : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              unless_flag("P", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL PE,nn
    0xEE : (0, [],                  [ OD(action=set_flags("SZ503P00",
                                                        value=lambda state, v : state.cpu.reg.A ^ v,
                                                        dest="A")) ] ),                               # XOR n
    0xEA : (0, [],                  [ OD(), OD(action=on_flag("P",JP())) ]),                          # JP PE,nn
    0xEB : (0, [ EX('DE', 'HL') ],  []),                                                              # EX DE,HL
    0xED : (0, [],                  [ OCF(prefix=0xED) ]),                                            # -- Byte one of multibyte OPCODE
    0xDD : (0, [],                  [ OCF(prefix=0xDD) ]),                                            # -- Byte one of multibyte OPCODE
    0xF0 : (1, [ on_flag('S', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET P
    0xF1 : (0, [],                  [ SR(), SR(action=LDr("AF")) ]),                                  # POP AF
    0xF2 : (0, [],                  [ OD(), OD(action=unless_flag("S",JP())) ]),                      # JP P,nn
    0xF4 : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              on_flag("S", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL P,nn
    0xF5 : (1, [],                  [ SW(source="A"), SW(source="F") ]),                              # PUSH AF
    0xF6 : (0, [],                  [ OD(action=set_flags("SZ503P00",
                                                        value=lambda state, v : state.cpu.reg.A | v,
                                                        dest="A")) ] ),                               # OR n
    0xF8 : (1, [ unless_flag('S', early_abort()) ],
                                    [ SR(), SR(action=JP()) ]),                                       # RET M
    0xF9 : (0, [ LDrs('SP', 'HL') ], []),                                                             # LD SP,HL
    0xFA : (0, [],                  [ OD(), OD(action=on_flag("S",JP())) ]),                          # JP M,nn
    0xFC : (0, [],                  [ OD(), OD(action=do_each(RRr("target"),
                                                              unless_flag("S", early_abort()))),
                                      SW(source="PCH"), SW(source="PCL", action=JP(key="target")) ]), # CALL M,nn
    0xFD : (0, [],                  [ OCF(prefix=0xFD) ]),                                            # -- Byte one of multibyte OPCODE
    0xFE : (0, [],                  [ OD(action=set_flags("SZ5H3V1C",
                                                        value=lambda state, v : state.cpu.reg.A - v,
                                                        )) ] ),                                       # CP n

    # Multibyte opcodes
    (0xCB, 0x00) : (0, [ RLC("B") ],            []),                                                      # RLC B
    (0xCB, 0x01) : (0, [ RLC("C") ],            []),                                                      # RLC C
    (0xCB, 0x02) : (0, [ RLC("D") ],            []),                                                      # RLC D
    (0xCB, 0x03) : (0, [ RLC("E") ],            []),                                                      # RLC E
    (0xCB, 0x04) : (0, [ RLC("H") ],            []),                                                      # RLC H
    (0xCB, 0x05) : (0, [ RLC("L") ],            []),                                                      # RLC L
    (0xCB, 0x06) : (0, [],                      [ MR(indirect="HL", action=RLC()), MW(indirect="HL") ]),  # RLC (HL)
    (0xCB, 0x07) : (0, [ RLC("A") ],            []),                                                      # RLC A
    (0xCB, 0x08) : (0, [ RRC("B") ],            []),                                                      # RRC B
    (0xCB, 0x09) : (0, [ RRC("C") ],            []),                                                      # RRC C
    (0xCB, 0x0A) : (0, [ RRC("D") ],            []),                                                      # RRC D
    (0xCB, 0x0B) : (0, [ RRC("E") ],            []),                                                      # RRC E
    (0xCB, 0x0C) : (0, [ RRC("H") ],            []),                                                      # RRC H
    (0xCB, 0x0D) : (0, [ RRC("L") ],            []),                                                      # RRC L
    (0xCB, 0x0E) : (0, [],                      [ MR(indirect="HL", action=RRC()), MW(indirect="HL") ]),  # RRC (HL)
    (0xCB, 0x0F) : (0, [ RRC("A") ],            []),                                                      # RRC A
    (0xCB, 0x10) : (0, [ RL("B") ],             []),                                                      # RL B
    (0xCB, 0x11) : (0, [ RL("C") ],             []),                                                      # RL C
    (0xCB, 0x12) : (0, [ RL("D") ],             []),                                                      # RL D
    (0xCB, 0x13) : (0, [ RL("E") ],             []),                                                      # RL E
    (0xCB, 0x14) : (0, [ RL("H") ],             []),                                                      # RL H
    (0xCB, 0x15) : (0, [ RL("L") ],             []),                                                      # RL L
    (0xCB, 0x16) : (0, [],                      [ MR(indirect="HL", action=RL()), MW(indirect="HL") ]),   # RL (HL)
    (0xCB, 0x17) : (0, [ RL("A") ],             []),                                                      # RL A
    (0xCB, 0x18) : (0, [ RR("B") ],             []),                                                      # RR B
    (0xCB, 0x19) : (0, [ RR("C") ],             []),                                                      # RR C
    (0xCB, 0x1A) : (0, [ RR("D") ],             []),                                                      # RR D
    (0xCB, 0x1B) : (0, [ RR("E") ],             []),                                                      # RR E
    (0xCB, 0x1C) : (0, [ RR("H") ],             []),                                                      # RR H
    (0xCB, 0x1D) : (0, [ RR("L") ],             []),                                                      # RR L
    (0xCB, 0x1E) : (0, [],                      [ MR(indirect="HL", action=RR()), MW(indirect="HL") ]),   # RR (HL)
    (0xCB, 0x1F) : (0, [ RR("A") ],             []),                                                      # RR A
    (0xCB, 0x20) : (0, [ SLA("B") ],            []),                                                      # SLA B
    (0xCB, 0x21) : (0, [ SLA("C") ],            []),                                                      # SLA C
    (0xCB, 0x22) : (0, [ SLA("D") ],            []),                                                      # SLA D
    (0xCB, 0x23) : (0, [ SLA("E") ],            []),                                                      # SLA E
    (0xCB, 0x24) : (0, [ SLA("H") ],            []),                                                      # SLA H
    (0xCB, 0x25) : (0, [ SLA("L") ],            []),                                                      # SLA L
    (0xCB, 0x26) : (0, [],                      [ MR(indirect="HL", action=SLA()), MW(indirect="HL") ]),  # SLA (HL)
    (0xCB, 0x27) : (0, [ SLA("A") ],            []),                                                      # SLA A
    (0xCB, 0x28) : (0, [ SRA("B") ],            []),                                                      # SRA B
    (0xCB, 0x29) : (0, [ SRA("C") ],            []),                                                      # SRA C
    (0xCB, 0x2A) : (0, [ SRA("D") ],            []),                                                      # SRA D
    (0xCB, 0x2B) : (0, [ SRA("E") ],            []),                                                      # SRA E
    (0xCB, 0x2C) : (0, [ SRA("H") ],            []),                                                      # SRA H
    (0xCB, 0x2D) : (0, [ SRA("L") ],            []),                                                      # SRA L
    (0xCB, 0x2E) : (0, [],                      [ MR(indirect="HL", action=SRA()), MW(indirect="HL") ]),  # SRA (HL)
    (0xCB, 0x2F) : (0, [ SRA("A") ],            []),                                                      # SRA A
    (0xCB, 0x30) : (0, [ SL1("B") ],            []),                                                      # SL1 B (undocumemnted)
    (0xCB, 0x31) : (0, [ SL1("C") ],            []),                                                      # SL1 C (undocumemnted)
    (0xCB, 0x32) : (0, [ SL1("D") ],            []),                                                      # SL1 D (undocumemnted)
    (0xCB, 0x33) : (0, [ SL1("E") ],            []),                                                      # SL1 E (undocumemnted)
    (0xCB, 0x34) : (0, [ SL1("H") ],            []),                                                      # SL1 H (undocumemnted)
    (0xCB, 0x35) : (0, [ SL1("L") ],            []),                                                      # SL1 L (undocumemnted)
    (0xCB, 0x36) : (0, [],                      [ MR(indirect="HL", action=SL1()), MW(indirect="HL") ]),  # SL1 (HL) (undocumemnted)
    (0xCB, 0x37) : (0, [ SL1("A") ],            []),                                                      # SL1 A (undocumemnted)
    (0xCB, 0x38) : (0, [ SRL("B") ],            []),                                                      # SRL B
    (0xCB, 0x39) : (0, [ SRL("C") ],            []),                                                      # SRL C
    (0xCB, 0x3A) : (0, [ SRL("D") ],            []),                                                      # SRL D
    (0xCB, 0x3B) : (0, [ SRL("E") ],            []),                                                      # SRL E
    (0xCB, 0x3C) : (0, [ SRL("H") ],            []),                                                      # SRL H
    (0xCB, 0x3D) : (0, [ SRL("L") ],            []),                                                      # SRL L
    (0xCB, 0x3E) : (0, [],                      [ MR(indirect="HL", action=SRL()), MW(indirect="HL") ]),  # SRL (HL)
    (0xCB, 0x3F) : (0, [ SRL("A") ],            []),                                                      # SRL A
    (0xCB, 0x40) : (0, [ BIT(0, "B") ],         []),                                                      # BIT 0,B
    (0xCB, 0x41) : (0, [ BIT(0, "C") ],         []),                                                      # BIT 0,C
    (0xCB, 0x42) : (0, [ BIT(0, "D") ],         []),                                                      # BIT 0,D
    (0xCB, 0x43) : (0, [ BIT(0, "E") ],         []),                                                      # BIT 0,E
    (0xCB, 0x44) : (0, [ BIT(0, "H") ],         []),                                                      # BIT 0,H
    (0xCB, 0x45) : (0, [ BIT(0, "L") ],         []),                                                      # BIT 0,L
    (0xCB, 0x46) : (0, [],                      [ MR(indirect="HL", action=BIT(0)) ]),                    # BIT 0,(HL)
    (0xCB, 0x47) : (0, [ BIT(0, "A") ],         []),                                                      # BIT 0,A
    (0xCB, 0x48) : (0, [ BIT(1, "B") ],         []),                                                      # BIT 1,B
    (0xCB, 0x49) : (0, [ BIT(1, "C") ],         []),                                                      # BIT 1,C
    (0xCB, 0x4A) : (0, [ BIT(1, "D") ],         []),                                                      # BIT 1,D
    (0xCB, 0x4B) : (0, [ BIT(1, "E") ],         []),                                                      # BIT 1,E
    (0xCB, 0x4C) : (0, [ BIT(1, "H") ],         []),                                                      # BIT 1,H
    (0xCB, 0x4D) : (0, [ BIT(1, "L") ],         []),                                                      # BIT 1,L
    (0xCB, 0x4E) : (0, [],                      [ MR(indirect="HL", action=BIT(1)) ]),                    # BIT 1,(HL)
    (0xCB, 0x4F) : (0, [ BIT(1, "A") ],         []),                                                      # BIT 1,A
    (0xCB, 0x50) : (0, [ BIT(2, "B") ],         []),                                                      # BIT 2,B
    (0xCB, 0x51) : (0, [ BIT(2, "C") ],         []),                                                      # BIT 2,C
    (0xCB, 0x52) : (0, [ BIT(2, "D") ],         []),                                                      # BIT 2,D
    (0xCB, 0x53) : (0, [ BIT(2, "E") ],         []),                                                      # BIT 2,E
    (0xCB, 0x54) : (0, [ BIT(2, "H") ],         []),                                                      # BIT 2,H
    (0xCB, 0x55) : (0, [ BIT(2, "L") ],         []),                                                      # BIT 2,L
    (0xCB, 0x56) : (0, [],                      [ MR(indirect="HL", action=BIT(2)) ]),                    # BIT 2,(HL)
    (0xCB, 0x57) : (0, [ BIT(2, "A") ],         []),                                                      # BIT 2,A
    (0xCB, 0x58) : (0, [ BIT(3, "B") ],         []),                                                      # BIT 3,B
    (0xCB, 0x59) : (0, [ BIT(3, "C") ],         []),                                                      # BIT 3,C
    (0xCB, 0x5A) : (0, [ BIT(3, "D") ],         []),                                                      # BIT 3,D
    (0xCB, 0x5B) : (0, [ BIT(3, "E") ],         []),                                                      # BIT 3,E
    (0xCB, 0x5C) : (0, [ BIT(3, "H") ],         []),                                                      # BIT 3,H
    (0xCB, 0x5D) : (0, [ BIT(3, "L") ],         []),                                                      # BIT 3,L
    (0xCB, 0x5E) : (0, [],                      [ MR(indirect="HL", action=BIT(3)) ]),                    # BIT 3,(HL)
    (0xCB, 0x5F) : (0, [ BIT(3, "A") ],         []),                                                      # BIT 3,A
    (0xCB, 0x60) : (0, [ BIT(4, "B") ],         []),                                                      # BIT 4,B
    (0xCB, 0x61) : (0, [ BIT(4, "C") ],         []),                                                      # BIT 4,C
    (0xCB, 0x62) : (0, [ BIT(4, "D") ],         []),                                                      # BIT 4,D
    (0xCB, 0x63) : (0, [ BIT(4, "E") ],         []),                                                      # BIT 4,E
    (0xCB, 0x64) : (0, [ BIT(4, "H") ],         []),                                                      # BIT 4,H
    (0xCB, 0x65) : (0, [ BIT(4, "L") ],         []),                                                      # BIT 4,L
    (0xCB, 0x66) : (0, [],                      [ MR(indirect="HL", action=BIT(4)) ]),                    # BIT 4,(HL)
    (0xCB, 0x67) : (0, [ BIT(4, "A") ],         []),                                                      # BIT 4,A
    (0xCB, 0x68) : (0, [ BIT(5, "B") ],         []),                                                      # BIT 5,B
    (0xCB, 0x69) : (0, [ BIT(5, "C") ],         []),                                                      # BIT 5,C
    (0xCB, 0x6A) : (0, [ BIT(5, "D") ],         []),                                                      # BIT 5,D
    (0xCB, 0x6B) : (0, [ BIT(5, "E") ],         []),                                                      # BIT 5,E
    (0xCB, 0x6C) : (0, [ BIT(5, "H") ],         []),                                                      # BIT 5,H
    (0xCB, 0x6D) : (0, [ BIT(5, "L") ],         []),                                                      # BIT 5,L
    (0xCB, 0x6E) : (0, [],                      [ MR(indirect="HL", action=BIT(5)) ]),                    # BIT 5,(HL)
    (0xCB, 0x6F) : (0, [ BIT(5, "A") ],         []),                                                      # BIT 5,A
    (0xCB, 0x70) : (0, [ BIT(6, "B") ],         []),                                                      # BIT 6,B
    (0xCB, 0x71) : (0, [ BIT(6, "C") ],         []),                                                      # BIT 6,C
    (0xCB, 0x72) : (0, [ BIT(6, "D") ],         []),                                                      # BIT 6,D
    (0xCB, 0x73) : (0, [ BIT(6, "E") ],         []),                                                      # BIT 6,E
    (0xCB, 0x74) : (0, [ BIT(6, "H") ],         []),                                                      # BIT 6,H
    (0xCB, 0x75) : (0, [ BIT(6, "L") ],         []),                                                      # BIT 6,L
    (0xCB, 0x76) : (0, [],                      [ MR(indirect="HL", action=BIT(6)) ]),                    # BIT 6,(HL)
    (0xCB, 0x77) : (0, [ BIT(6, "A") ],         []),                                                      # BIT 6,A
    (0xCB, 0x78) : (0, [ BIT(7, "B") ],         []),                                                      # BIT 7,B
    (0xCB, 0x79) : (0, [ BIT(7, "C") ],         []),                                                      # BIT 7,C
    (0xCB, 0x7A) : (0, [ BIT(7, "D") ],         []),                                                      # BIT 7,D
    (0xCB, 0x7B) : (0, [ BIT(7, "E") ],         []),                                                      # BIT 7,E
    (0xCB, 0x7C) : (0, [ BIT(7, "H") ],         []),                                                      # BIT 7,H
    (0xCB, 0x7D) : (0, [ BIT(7, "L") ],         []),                                                      # BIT 7,L
    (0xCB, 0x7E) : (0, [],                      [ MR(indirect="HL", action=BIT(7)) ]),                    # BIT 7,(HL)
    (0xCB, 0x7F) : (0, [ BIT(7, "A") ],         []),                                                      # BIT 7,A
    (0xCB, 0x80) : (0, [ RES(0, "B") ],         []),                                                      # RES 0,B
    (0xCB, 0x81) : (0, [ RES(0, "C") ],         []),                                                      # RES 0,C
    (0xCB, 0x82) : (0, [ RES(0, "D") ],         []),                                                      # RES 0,D
    (0xCB, 0x83) : (0, [ RES(0, "E") ],         []),                                                      # RES 0,E
    (0xCB, 0x84) : (0, [ RES(0, "H") ],         []),                                                      # RES 0,H
    (0xCB, 0x85) : (0, [ RES(0, "L") ],         []),                                                      # RES 0,L
    (0xCB, 0x86) : (0, [],                      [ MR(indirect="HL", action=RES(0)), MW(indirect="HL") ]), # RES 0,(HL)
    (0xCB, 0x87) : (0, [ RES(0, "A") ],         []),                                                      # RES 0,A
    (0xCB, 0x88) : (0, [ RES(1, "B") ],         []),                                                      # RES 1,B
    (0xCB, 0x89) : (0, [ RES(1, "C") ],         []),                                                      # RES 1,C
    (0xCB, 0x8A) : (0, [ RES(1, "D") ],         []),                                                      # RES 1,D
    (0xCB, 0x8B) : (0, [ RES(1, "E") ],         []),                                                      # RES 1,E
    (0xCB, 0x8C) : (0, [ RES(1, "H") ],         []),                                                      # RES 1,H
    (0xCB, 0x8D) : (0, [ RES(1, "L") ],         []),                                                      # RES 1,L
    (0xCB, 0x8E) : (0, [],                      [ MR(indirect="HL", action=RES(1)), MW(indirect="HL") ]), # RES 1,(HL)
    (0xCB, 0x8F) : (0, [ RES(1, "A") ],         []),                                                      # RES 1,A
    (0xCB, 0x90) : (0, [ RES(2, "B") ],         []),                                                      # RES 2,B
    (0xCB, 0x91) : (0, [ RES(2, "C") ],         []),                                                      # RES 2,C
    (0xCB, 0x92) : (0, [ RES(2, "D") ],         []),                                                      # RES 2,D
    (0xCB, 0x93) : (0, [ RES(2, "E") ],         []),                                                      # RES 2,E
    (0xCB, 0x94) : (0, [ RES(2, "H") ],         []),                                                      # RES 2,H
    (0xCB, 0x95) : (0, [ RES(2, "L") ],         []),                                                      # RES 2,L
    (0xCB, 0x96) : (0, [],                      [ MR(indirect="HL", action=RES(2)), MW(indirect="HL") ]), # RES 2,(HL)
    (0xCB, 0x97) : (0, [ RES(2, "A") ],         []),                                                      # RES 2,A
    (0xCB, 0x98) : (0, [ RES(3, "B") ],         []),                                                      # RES 3,B
    (0xCB, 0x99) : (0, [ RES(3, "C") ],         []),                                                      # RES 3,C
    (0xCB, 0x9A) : (0, [ RES(3, "D") ],         []),                                                      # RES 3,D
    (0xCB, 0x9B) : (0, [ RES(3, "E") ],         []),                                                      # RES 3,E
    (0xCB, 0x9C) : (0, [ RES(3, "H") ],         []),                                                      # RES 3,H
    (0xCB, 0x9D) : (0, [ RES(3, "L") ],         []),                                                      # RES 3,L
    (0xCB, 0x9E) : (0, [],                      [ MR(indirect="HL", action=RES(3)), MW(indirect="HL") ]), # RES 3,(HL)
    (0xCB, 0x9F) : (0, [ RES(3, "A") ],         []),                                                      # RES 3,A
    (0xCB, 0xA0) : (0, [ RES(4, "B") ],         []),                                                      # RES 4,B
    (0xCB, 0xA1) : (0, [ RES(4, "C") ],         []),                                                      # RES 4,C
    (0xCB, 0xA2) : (0, [ RES(4, "D") ],         []),                                                      # RES 4,D
    (0xCB, 0xA3) : (0, [ RES(4, "E") ],         []),                                                      # RES 4,E
    (0xCB, 0xA4) : (0, [ RES(4, "H") ],         []),                                                      # RES 4,H
    (0xCB, 0xA5) : (0, [ RES(4, "L") ],         []),                                                      # RES 4,L
    (0xCB, 0xA6) : (0, [],                      [ MR(indirect="HL", action=RES(4)), MW(indirect="HL") ]), # RES 4,(HL)
    (0xCB, 0xA7) : (0, [ RES(4, "A") ],         []),                                                      # RES 4,A
    (0xCB, 0xA8) : (0, [ RES(5, "B") ],         []),                                                      # RES 5,B
    (0xCB, 0xA9) : (0, [ RES(5, "C") ],         []),                                                      # RES 5,C
    (0xCB, 0xAA) : (0, [ RES(5, "D") ],         []),                                                      # RES 5,D
    (0xCB, 0xAB) : (0, [ RES(5, "E") ],         []),                                                      # RES 5,E
    (0xCB, 0xAC) : (0, [ RES(5, "H") ],         []),                                                      # RES 5,H
    (0xCB, 0xAD) : (0, [ RES(5, "L") ],         []),                                                      # RES 5,L
    (0xCB, 0xAE) : (0, [],                      [ MR(indirect="HL", action=RES(5)), MW(indirect="HL") ]), # RES 5,(HL)
    (0xCB, 0xAF) : (0, [ RES(5, "A") ],         []),                                                      # RES 5,A
    (0xCB, 0xB0) : (0, [ RES(6, "B") ],         []),                                                      # RES 6,B
    (0xCB, 0xB1) : (0, [ RES(6, "C") ],         []),                                                      # RES 6,C
    (0xCB, 0xB2) : (0, [ RES(6, "D") ],         []),                                                      # RES 6,D
    (0xCB, 0xB3) : (0, [ RES(6, "E") ],         []),                                                      # RES 6,E
    (0xCB, 0xB4) : (0, [ RES(6, "H") ],         []),                                                      # RES 6,H
    (0xCB, 0xB5) : (0, [ RES(6, "L") ],         []),                                                      # RES 6,L
    (0xCB, 0xB6) : (0, [],                      [ MR(indirect="HL", action=RES(6)), MW(indirect="HL") ]), # RES 6,(HL)
    (0xCB, 0xB7) : (0, [ RES(6, "A") ],         []),                                                      # RES 6,A
    (0xCB, 0xB8) : (0, [ RES(7, "B") ],         []),                                                      # RES 7,B
    (0xCB, 0xB9) : (0, [ RES(7, "C") ],         []),                                                      # RES 7,C
    (0xCB, 0xBA) : (0, [ RES(7, "D") ],         []),                                                      # RES 7,D
    (0xCB, 0xBB) : (0, [ RES(7, "E") ],         []),                                                      # RES 7,E
    (0xCB, 0xBC) : (0, [ RES(7, "H") ],         []),                                                      # RES 7,H
    (0xCB, 0xBD) : (0, [ RES(7, "L") ],         []),                                                      # RES 7,L
    (0xCB, 0xBE) : (0, [],                      [ MR(indirect="HL", action=RES(7)), MW(indirect="HL") ]), # RES 7,(HL)
    (0xCB, 0xBF) : (0, [ RES(7, "A") ],         []),                                                      # RES 7,A
    (0xCB, 0xC0) : (0, [ SET(0, "B") ],         []),                                                      # SET 0,B
    (0xCB, 0xC1) : (0, [ SET(0, "C") ],         []),                                                      # SET 0,C
    (0xCB, 0xC2) : (0, [ SET(0, "D") ],         []),                                                      # SET 0,D
    (0xCB, 0xC3) : (0, [ SET(0, "E") ],         []),                                                      # SET 0,E
    (0xCB, 0xC4) : (0, [ SET(0, "H") ],         []),                                                      # SET 0,H
    (0xCB, 0xC5) : (0, [ SET(0, "L") ],         []),                                                      # SET 0,L
    (0xCB, 0xC6) : (0, [],                      [ MR(indirect="HL", action=SET(0)), MW(indirect="HL") ]), # SET 0,(HL)
    (0xCB, 0xC7) : (0, [ SET(0, "A") ],         []),                                                      # SET 0,A
    (0xCB, 0xC8) : (0, [ SET(1, "B") ],         []),                                                      # SET 1,B
    (0xCB, 0xC9) : (0, [ SET(1, "C") ],         []),                                                      # SET 1,C
    (0xCB, 0xCA) : (0, [ SET(1, "D") ],         []),                                                      # SET 1,D
    (0xCB, 0xCB) : (0, [ SET(1, "E") ],         []),                                                      # SET 1,E
    (0xCB, 0xCC) : (0, [ SET(1, "H") ],         []),                                                      # SET 1,H
    (0xCB, 0xCD) : (0, [ SET(1, "L") ],         []),                                                      # SET 1,L
    (0xCB, 0xCE) : (0, [],                      [ MR(indirect="HL", action=SET(1)), MW(indirect="HL") ]), # SET 1,(HL)
    (0xCB, 0xCF) : (0, [ SET(1, "A") ],         []),                                                      # SET 1,A
    (0xCB, 0xD0) : (0, [ SET(2, "B") ],         []),                                                      # SET 2,B
    (0xCB, 0xD1) : (0, [ SET(2, "C") ],         []),                                                      # SET 2,C
    (0xCB, 0xD2) : (0, [ SET(2, "D") ],         []),                                                      # SET 2,D
    (0xCB, 0xD3) : (0, [ SET(2, "E") ],         []),                                                      # SET 2,E
    (0xCB, 0xD4) : (0, [ SET(2, "H") ],         []),                                                      # SET 2,H
    (0xCB, 0xD5) : (0, [ SET(2, "L") ],         []),                                                      # SET 2,L
    (0xCB, 0xD6) : (0, [],                      [ MR(indirect="HL", action=SET(2)), MW(indirect="HL") ]), # SET 2,(HL)
    (0xCB, 0xD7) : (0, [ SET(2, "A") ],         []),                                                      # SET 2,A
    (0xCB, 0xD8) : (0, [ SET(3, "B") ],         []),                                                      # SET 3,B
    (0xCB, 0xD9) : (0, [ SET(3, "C") ],         []),                                                      # SET 3,C
    (0xCB, 0xDA) : (0, [ SET(3, "D") ],         []),                                                      # SET 3,D
    (0xCB, 0xDB) : (0, [ SET(3, "E") ],         []),                                                      # SET 3,E
    (0xCB, 0xDC) : (0, [ SET(3, "H") ],         []),                                                      # SET 3,H
    (0xCB, 0xDD) : (0, [ SET(3, "L") ],         []),                                                      # SET 3,L
    (0xCB, 0xDE) : (0, [],                      [ MR(indirect="HL", action=SET(3)), MW(indirect="HL") ]), # SET 3,(HL)
    (0xCB, 0xDF) : (0, [ SET(3, "A") ],         []),                                                      # SET 3,A
    (0xCB, 0xE0) : (0, [ SET(4, "B") ],         []),                                                      # SET 4,B
    (0xCB, 0xE1) : (0, [ SET(4, "C") ],         []),                                                      # SET 4,C
    (0xCB, 0xE2) : (0, [ SET(4, "D") ],         []),                                                      # SET 4,D
    (0xCB, 0xE3) : (0, [ SET(4, "E") ],         []),                                                      # SET 4,E
    (0xCB, 0xE4) : (0, [ SET(4, "H") ],         []),                                                      # SET 4,H
    (0xCB, 0xE5) : (0, [ SET(4, "L") ],         []),                                                      # SET 4,L
    (0xCB, 0xE6) : (0, [],                      [ MR(indirect="HL", action=SET(4)), MW(indirect="HL") ]), # SET 4,(HL)
    (0xCB, 0xE7) : (0, [ SET(4, "A") ],         []),                                                      # SET 4,A
    (0xCB, 0xE8) : (0, [ SET(5, "B") ],         []),                                                      # SET 5,B
    (0xCB, 0xE9) : (0, [ SET(5, "C") ],         []),                                                      # SET 5,C
    (0xCB, 0xEA) : (0, [ SET(5, "D") ],         []),                                                      # SET 5,D
    (0xCB, 0xEB) : (0, [ SET(5, "E") ],         []),                                                      # SET 5,E
    (0xCB, 0xEC) : (0, [ SET(5, "H") ],         []),                                                      # SET 5,H
    (0xCB, 0xED) : (0, [ SET(5, "L") ],         []),                                                      # SET 5,L
    (0xCB, 0xEE) : (0, [],                      [ MR(indirect="HL", action=SET(5)), MW(indirect="HL") ]), # SET 5,(HL)
    (0xCB, 0xEF) : (0, [ SET(5, "A") ],         []),                                                      # SET 5,A
    (0xCB, 0xF0) : (0, [ SET(6, "B") ],         []),                                                      # SET 6,B
    (0xCB, 0xF1) : (0, [ SET(6, "C") ],         []),                                                      # SET 6,C
    (0xCB, 0xF2) : (0, [ SET(6, "D") ],         []),                                                      # SET 6,D
    (0xCB, 0xF3) : (0, [ SET(6, "E") ],         []),                                                      # SET 6,E
    (0xCB, 0xF4) : (0, [ SET(6, "H") ],         []),                                                      # SET 6,H
    (0xCB, 0xF5) : (0, [ SET(6, "L") ],         []),                                                      # SET 6,L
    (0xCB, 0xF6) : (0, [],                      [ MR(indirect="HL", action=SET(6)), MW(indirect="HL") ]), # SET 6,(HL)
    (0xCB, 0xF7) : (0, [ SET(6, "A") ],         []),                                                      # SET 6,A
    (0xCB, 0xF8) : (0, [ SET(7, "B") ],         []),                                                      # SET 7,B
    (0xCB, 0xF9) : (0, [ SET(7, "C") ],         []),                                                      # SET 7,C
    (0xCB, 0xFA) : (0, [ SET(7, "D") ],         []),                                                      # SET 7,D
    (0xCB, 0xFB) : (0, [ SET(7, "E") ],         []),                                                      # SET 7,E
    (0xCB, 0xFC) : (0, [ SET(7, "H") ],         []),                                                      # SET 7,H
    (0xCB, 0xFD) : (0, [ SET(7, "L") ],         []),                                                      # SET 7,L
    (0xCB, 0xFE) : (0, [],                      [ MR(indirect="HL", action=SET(7)), MW(indirect="HL") ]), # SET 7,(HL)
    (0xCB, 0xFF) : (0, [ SET(7, "A") ],         []),                                                      # SET 7,A
    (0xDD, 0x09) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.B)&0xF)+((state.cpu.reg.IXH)&0xF)+((state.cpu.reg.C+state.cpu.reg.IXL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.B + state.cpu.reg.IXH + ((state.cpu.reg.C+state.cpu.reg.IXL)>>8)),
                 LDr('IX', value=lambda state : (state.cpu.reg.IX + state.cpu.reg.BC)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IX,BC
    (0xDD, 0x19) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.D)&0xF)+((state.cpu.reg.IXH)&0xF)+((state.cpu.reg.E+state.cpu.reg.IXL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.D + state.cpu.reg.IXH + ((state.cpu.reg.E+state.cpu.reg.IXL)>>8)),
                 LDr('IX', value=lambda state : (state.cpu.reg.IX + state.cpu.reg.DE)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IX,DE
    (0xDD, 0x29) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.IXH)&0xF)+((state.cpu.reg.IXH)&0xF)+((state.cpu.reg.IXL+state.cpu.reg.IXL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.IXH + state.cpu.reg.IXH + ((state.cpu.reg.IXL+state.cpu.reg.IXL)>>8)),
                 LDr('IX', value=lambda state : (state.cpu.reg.IX + state.cpu.reg.IX)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IX,IX
    (0xDD, 0x39) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.SPH)&0xF)+((state.cpu.reg.IXH)&0xF)+((state.cpu.reg.SPL+state.cpu.reg.IXL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.SPH + state.cpu.reg.IXH + ((state.cpu.reg.SPL+state.cpu.reg.IXL)>>8)),
                 LDr('IX', value=lambda state : (state.cpu.reg.IX + state.cpu.reg.SP)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IX,SP
    (0xDD, 0x21) : (0, [],                [ OD(), OD(action=LDr('IX')) ]),                            # LD IX,nn
    (0xDD, 0x22) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="IXL"),
                                            MW(source="IXH")]),                                       # LD (nn),IX
    (0xDD, 0x23) : (0, [ LDr('IX', value=lambda state : (state.cpu.reg.IX + 1)&0xFFFF) ],
                                    [] ),                                                             # INC IX
    (0xDD, 0x2A) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('IXL')), MR(action=LDr('IXH')) ]),          # LD IX,(nn)
    (0xDD, 0x2B) : (0, [ LDr('IX', value=lambda state : (state.cpu.reg.IX - 1)&0xFFFF) ],
                                    [] ),                                                             # DEC IX
    (0xDD, 0x34) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if ((v&0xF)+1 > 0xF) else 0),
                                                set_flags("SZ5-3V0-", value=lambda state, v : v + 1, key="value")),
                                               incaddr=False),
                                            MW() ] ),                                                 # INC (IX+d)
    (0xDD, 0x35) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if ((v&0xF)-1 < 0x0) else 0),
                                                set_flags("SZ5H3V1-", value=lambda state, v : v - 1, key="value")),
                                               incaddr=False),
                                            MW() ] ),                                                 # DEC (IX+d)
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
    (0xDD, 0x86) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF) > 0xF) else 0),
                                                set_flags("SZ5H3V0C",
                                                value=lambda state, v : state.cpu.reg.A + v,
                                                dest="A"))) ] ),                                      # ADD (IX+d)
    (0xDD, 0x8E) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                                                set_flags("SZ5H3V0C",
                                                value=lambda state, v : state.cpu.reg.A + v + state.cpu.reg.getflag('C'),
                                                dest="A"))) ] ),                                      # ADC (IX+d)
    (0xDD, 0x96) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) < 0x0) else 0),
                                                set_flags("SZ5H3V1C",
                                               value=lambda state, v : state.cpu.reg.A - v,
                                               dest="A"))) ] ),                                        # SUB (IX+d)
    (0xDD, 0x9E) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                                            set_flags("SZ5H3V1C",
                                               value=lambda state, v : state.cpu.reg.A - v - state.cpu.reg.getflag('C'),
                                               dest="A"))) ] ),                                        # SBC (IX+d)
    (0xDD, 0xA6) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=set_flags("SZ513P00",
                                               value=lambda state, v : state.cpu.reg.A & v,
                                               dest="A")) ] ),                                        # AND (IX+d)
    (0xDD, 0xAE) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=set_flags("SZ503P00",
                                               value=lambda state, v : state.cpu.reg.A ^ v,
                                               dest="A")) ] ),                                        # XOR (IX+d)
    (0xDD, 0xB6) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=set_flags("SZ503P00",
                                               value=lambda state, v : state.cpu.reg.A | v,
                                               dest="A")) ] ),                                        # OR (IX+d)
    (0xDD, 0xBE) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IX') }),
                                            MR(action=set_flags("SZ5H3V1C",
                                               value=lambda state, v : state.cpu.reg.A - v,)) ] ),    # CP (IX+d)
    (0xDD, 0xCB) : (0, [],                [ OD(key='address', signed=True),
                                            IO(1, True, transform={'address' : add_register('IX') }),
                                            OCF(prefix=(0xDD, 0xCB)) ]),                              # -- second and third bytes of 4 byte op-code
    (0xDD, 0xE1) : (0, [],                [ SR(), SR(action=LDr("IX")) ]),                            # POP IX
    (0xDD, 0xE3) : (0, [ RRr('H','IXH'), RRr('L','IXL') ],
                        [ SR(), SR(action=LDr("IX"), extra=1), SW(key="H"), SW(key="L", extra=2) ]),  # EX (SP),IX
    (0xDD, 0xE5) : (1, [],                [ SW(source="IXH"), SW(source="IXL") ]),                    # PUSH IX
    (0xDD, 0xE9) : (0, [ JP(source="IX") ], []),                                                      # JP (IX)
    (0xDD, 0xF9) : (0, [LDrs('SP','IX'),],[]),                                                        # LD SP,IX
    (0xED, 0x42) : (0, SBC16('BC'),      [ IO(4, True), IO(3, True) ] ),                              # SBC HL,BC
    (0xED, 0x43) : (0, [],                [ OD(key="address"),
                                            OD(key="address",
                                            compound=high_after_low),
                                            MW(source="C"), MW(source="B") ]),                        # LD (nn),BC
    (0xED, 0x44) : (0, [ set_flags("SZ513V11", value=lambda state : (-state.cpu.reg.A)&0xFF, dest='A') ],
                                         []),                                                         # NEG
    (0xED, 0x45) : (0, [],               [ SR(), SR(action=JP()) ] ),                                 # RETN
    (0xED, 0x47) : (0, [LDrs('I', 'A')], []),                                                         # LD I,A
    (0xED, 0x4B) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('C')), MR(action=LDr('B')) ]),              # LD BC,(nn)
    (0xED, 0x4A) : (0, ADC16('BC'),      [ IO(4, True), IO(3, True) ] ),                              # ADC HL,BC
    (0xED, 0x4D) : (0, [],               [ SR(), SR(action=JP()) ] ),                                 # RETI
    (0xED, 0x4F) : (0, [LDrs('R', 'A'),], []),                                                        # LD R,A
    (0xED, 0x52) : (0, SBC16('DE'),      [ IO(4, True), IO(3, True) ] ),                              # SBC HL,DE
    (0xED, 0x53) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="E"),
                                            MW(source="D") ]),                                        # LD (nn),DE
    (0xED, 0x57) : (0, [LDrs('A', 'I'), set_flags("SZ503*0-", source='I') ], []),                     # LD A,I
    (0xED, 0x5A) : (0, ADC16('DE'),      [ IO(4, True), IO(3, True) ] ),                              # ADC HL,DE
    (0xED, 0x5B) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('E')), MR(action=LDr('D')) ]),              # LD DE,(nn)
    (0xED, 0x5F) : (0, [LDrs('A', 'R'), set_flags("SZ503*0-", source='R') ], []),                     # LD A,R
    (0xED, 0x62) : (0, SBC16('HL'),      [ IO(4, True), IO(3, True) ] ),                              # SBC HL,HL
    (0xED, 0x67) : (0, [],               [ MR(indirect="HL",
                                              action=do_each(
                                                  RRr("value", value=lambda state,v : (v >> 4) | (state.cpu.reg.A << 4)),
                                                  set_flags("SZ503P0-", value=lambda state,v : (v&0x0F), dest="A", key=None))),
                                            IO(4, True),
                                            MW(indirect="HL") ] ),                                    # RRD
    (0xED, 0x6A) : (0, ADC16('HL'),      [ IO(4, True), IO(3, True) ] ),                              # ADC HL,HL
    (0xED, 0x6F) : (0, [],               [ MR(indirect="HL",
                                              action=do_each(
                                                  RRr("value", value=lambda state,v : (v << 4) | (state.cpu.reg.A&0x0F)),
                                                  set_flags("SZ503P0-", value=lambda state,v : (v >> 4), dest="A", key=None))),
                                            IO(4, True),
                                            MW(indirect="HL") ] ),                                    # RLD
    (0xED, 0x72) : (0, SBC16('SP'),      [ IO(4, True), IO(3, True) ] ),                              # SBC HL,SP
    (0xED, 0x73) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MW(source="SPL"),
                                            MW(source="SPH") ]),                                      # LD (nn),SP
    (0xED, 0x7A) : (0, ADC16('SP'),      [ IO(4, True), IO(3, True) ] ),                              # ADC HL,SP
    (0xED, 0x7B) : (0, [],                [ OD(key="address"),
                                            OD(key="address", compound=high_after_low),
                                            MR(action=LDr('SPL')), MR(action=LDr('SPH')) ]),          # LD SP,(nn)
    (0xED, 0xA0) : (0, [],                [ MR(indirect="HL"),
                                            MW(indirect="DE",
                                                extra=2,
                                                action=do_each(set_flags("--50310-", value=lambda state,_ : state.kwargs['value'] + state.cpu.reg.A),
                                                                inc("HL"),
                                                                inc("DE"),
                                                                dec("BC"),
                                                                on_zero("BC", clear_flag("V")))) ]), # LDI
    (0xED, 0xA1) : (0, [],                [ MR(indirect="HL"),
                                            IO(5, True, transform={'value' : subfrom() },
                                                   action=do_each(set_flags("-Z50311-"),
                                                                  inc("HL"),
                                                                  dec("BC"),
                                                                  on_zero("BC", clear_flag("V")))) ]), # CPI
    (0xED, 0xA8) : (0, [],                [ MR(indirect="HL"),
                                            MW(indirect="DE",
                                                extra=2,
                                                action=do_each(set_flags("--50310-", value=lambda state,_ : state.kwargs['value'] + state.cpu.reg.A),
                                                                dec("HL"),
                                                                dec("DE"),
                                                                dec("BC"),
                                                                on_zero("BC", clear_flag("V")))) ]), # LDD
    (0xED, 0xA9) : (0, [],                [ MR(indirect="HL"),
                                            IO(5, True, transform={'value' : subfrom() },
                                                   action=do_each(set_flags("-Z50311-"),
                                                                  dec("HL"),
                                                                  dec("BC"),
                                                                  on_zero("BC", clear_flag("V")))) ]), # CPD
    (0xED, 0xB0) : (0, [],                [ MR(indirect="HL"),
                                            MW(indirect="DE",
                                                extra=2,
                                                action=do_each(set_flags("--50310-", value=lambda state,_ : state.kwargs['value'] + state.cpu.reg.A),
                                                                inc("HL"),
                                                                inc("DE"),
                                                                dec("BC"),
                                                                on_zero("BC", clear_flag("V")),
                                                                on_zero("BC", early_abort()))),
                                            IO(5, True, action=do_each(dec("PC"), dec("PC"))) ]), # LDIR
    (0xED, 0xB1) : (0, [],                [ MR(indirect="HL"),
                                            IO(5, True, transform={'value' : subfrom() },
                                                   action=do_each(set_flags("-Z50311-"),
                                                                  inc("HL"),
                                                                  dec("BC"),
                                                                  on_zero("BC", clear_flag("V")),
                                                                  on_zero("BC", early_abort()),
                                                                  on_flag('Z', early_abort()))),
                                            IO(5, True, action=do_each(dec("PC"), dec("PC"))) ]), # CPIR
    (0xED, 0xB8) : (0, [],                [ MR(indirect="HL"),
                                            MW(indirect="DE",
                                                extra=2,
                                                action=do_each(set_flags("--50310-", value=lambda state,_ : state.kwargs['value'] + state.cpu.reg.A),
                                                                dec("HL"),
                                                                dec("DE"),
                                                                dec("BC"),
                                                                on_zero("BC", clear_flag("V")),
                                                                on_zero("BC", early_abort()))),
                                            IO(5, True, action=do_each(dec("PC"), dec("PC"))) ]), # LDDR
    (0xED, 0xB9) : (0, [],                [ MR(indirect="HL"),
                                            IO(5, True, transform={'value' : subfrom() },
                                                   action=do_each(set_flags("-Z50311-"),
                                                                  dec("HL"),
                                                                  dec("BC"),
                                                                  on_zero("BC", clear_flag("V")),
                                                                  on_zero("BC", early_abort()),
                                                                  on_flag('Z', early_abort()))),
                                                IO(5, True, action=do_each(dec("PC"), dec("PC"))) ]), # CPDR
    (0xFD, 0x09) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.B)&0xF)+((state.cpu.reg.IYH)&0xF)+((state.cpu.reg.C+state.cpu.reg.IYL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.B + state.cpu.reg.IYH + ((state.cpu.reg.C+state.cpu.reg.IYL)>>8)),
                 LDr('IY', value=lambda state : (state.cpu.reg.IY + state.cpu.reg.BC)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IY,BC
    (0xFD, 0x19) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.D)&0xF)+((state.cpu.reg.IYH)&0xF)+((state.cpu.reg.E+state.cpu.reg.IYL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.D + state.cpu.reg.IYH + ((state.cpu.reg.E+state.cpu.reg.IYL)>>8)),
                 LDr('IY', value=lambda state : (state.cpu.reg.IY + state.cpu.reg.DE)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IY,DE
    (0xFD, 0x23) : (0, [ LDr('IY', value=lambda state : (state.cpu.reg.IY + 1)&0xFFFF) ],
                                    [] ),                                                             # INC IY
    (0xFD, 0x29) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.IYH)&0xF)+((state.cpu.reg.IYH)&0xF)+((state.cpu.reg.IYL+state.cpu.reg.IYL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.IYH + state.cpu.reg.IYH + ((state.cpu.reg.IYL+state.cpu.reg.IYL)>>8)),
                 LDr('IY', value=lambda state : (state.cpu.reg.IY + state.cpu.reg.IY)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IY,IY
    (0xFD, 0x2B) : (0, [ LDr('IY', value=lambda state : (state.cpu.reg.IY - 1)&0xFFFF) ],
                                    [] ),                                                             # DEC IY
    (0xFD, 0x39) : (0, [ force_flag('H', lambda  state : 1 if (((state.cpu.reg.SPH)&0xF)+((state.cpu.reg.IYH)&0xF)+((state.cpu.reg.SPL+state.cpu.reg.IYL)>>8) > 0xF) else 0),
                 set_flags("--5-3-0C", value=lambda state : state.cpu.reg.SPH + state.cpu.reg.IYH + ((state.cpu.reg.SPL+state.cpu.reg.IYL)>>8)),
                 LDr('IY', value=lambda state : (state.cpu.reg.IY + state.cpu.reg.SP)&0xFFFF) ],
                                    [ IO(4, True), IO(3, True) ] ),                                   # ADD IY,SP
    (0xFD, 0x21) : (0, [],                [ OD(), OD(action=LDr('IY')) ]),   # LD IY,nn
    (0xFD, 0x22) : (0, [],                [ OD(key="address"),
                                            OD(key="address"),
                                            MW(source="IYL"),
                                            MW(source="IYH") ]),                                      # LD (nn),IY
    (0xFD, 0x2A) : (0, [],                [ OD(key="address"),
                                            OD(key="address"),
                                            MR(action=LDr('IYL')), MR(action=LDr('IYH')) ]),          # LD IY,(nn)
    (0xFD, 0x34) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if ((v&0xF)+1 > 0xF) else 0),
                                                set_flags("SZ5-3V0-", value=lambda state, v : v + 1, key="value")),
                                               incaddr=False),
                                            MW() ] ),                                                 # INC (IY+d)
    (0xFD, 0x35) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if ((v&0xF)-1 < 0x0) else 0),
                                                set_flags("SZ5H3V1-", value=lambda state, v : v - 1, key="value")),
                                               incaddr=False),
                                            MW() ] ),                                                 # DEC (IY+d)
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
    (0xFD, 0x86) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF) > 0xF) else 0),
                                                set_flags("SZ5H3V0C",
                                                value=lambda state, v : state.cpu.reg.A + v,
                                                dest="A"))) ] ),                                      # ADD (IY+d)
    (0xFD, 0x8E) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)+(v&0xF)+state.cpu.reg.getflag('C') > 0xF) else 0),
                                                set_flags("SZ5H3V0C",
                                                value=lambda state, v : state.cpu.reg.A + v + state.cpu.reg.getflag('C'),
                                                dest="A"))) ] ),                                      # ADC (IY+d)
    (0xFD, 0x96) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=do_each(
                                                force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) < 0x0) else 0),
                                                set_flags("SZ5H3V1C",
                                               value=lambda state, v : state.cpu.reg.A - v,
                                               dest="A"))) ] ),                                        # SUB (IY+d)
    (0xFD, 0x9E) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=do_each(
                                            force_flag('H', lambda  state,v : 1 if (((state.cpu.reg.A)&0xF)-(v&0xF) - state.cpu.reg.getflag('C') < 0x0) else 0),
                                            set_flags("SZ5H3V1C",
                                               value=lambda state, v : state.cpu.reg.A - v - state.cpu.reg.getflag('C'),
                                               dest="A"))) ] ),                                        # SBC (IY+d)
    (0xFD, 0xA6) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=set_flags("SZ513P00",
                                               value=lambda state, v : state.cpu.reg.A & v,
                                               dest="A")) ] ),                                        # AND (IY+d)
    (0xFD, 0xAE) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=set_flags("SZ503P00",
                                               value=lambda state, v : state.cpu.reg.A ^ v,
                                               dest="A")) ] ),                                        # XOR (IY+d)
    (0xFD, 0xB6) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=set_flags("SZ503P00",
                                               value=lambda state, v : state.cpu.reg.A | v,
                                               dest="A")) ] ),                                        # OR (IY+d)
    (0xFD, 0xBE) : (0, [],                [ OD(key='address', signed=True),
                                            IO(5, True, transform={'address' : add_register('IY') }),
                                            MR(action=set_flags("SZ5H3V1C",
                                               value=lambda state, v : state.cpu.reg.A - v,)) ] ),    # CP (IY+d)
    (0xFD, 0xCB) : (0, [],                [ OD(key='address', signed=True),
                                            IO(1, True, transform={'address' : add_register('IY') }),
                                            OCF(prefix=(0xFD, 0xCB)) ]),                              # -- second and third bytes of 4 byte op-code
    (0xFD, 0xE1) : (0, [],                [ SR(), SR(action=LDr("IY")) ]),                            # POP IY
    (0xFD, 0xE3) : (0, [ RRr('H','IYH'), RRr('L','IYL') ],
                        [ SR(), SR(action=LDr("IY"), extra=1), SW(key="H"), SW(key="L", extra=2) ]),  # EX (SP),IY
    (0xFD, 0xE5) : (1, [],                [ SW(source="IYH"), SW(source="IYL") ]),                    # PUSH IY
    (0xFD, 0xE9) : (0, [ JP(source="IY") ], []),                                                      # JP (IY)
    (0xFD, 0xF9) : (0, [LDrs('SP','IY'),],[]),                                                        # LD SP,IY

    (0xDD, 0xCB, 0x06) : (0, [], [ MR(action=RLC(), incaddr=False), MW() ]),                          # RLC (IX+d)
    (0xDD, 0xCB, 0x0E) : (0, [], [ MR(action=RRC(), incaddr=False), MW() ]),                          # RRC (IX+d)
    (0xDD, 0xCB, 0x16) : (0, [], [ MR(action=RL(), incaddr=False), MW() ]),                           # RL (IX+d)
    (0xDD, 0xCB, 0x1E) : (0, [], [ MR(action=RR(), incaddr=False), MW() ]),                           # RR (IX+d)
    (0xDD, 0xCB, 0x26) : (0, [], [ MR(action=SLA(), incaddr=False), MW() ]),                          # SLA (IX+d)
    (0xDD, 0xCB, 0x2E) : (0, [], [ MR(action=SRA(), incaddr=False), MW() ]),                          # SRA (IX+d)
    (0xDD, 0xCB, 0x36) : (0, [], [ MR(action=SL1(), incaddr=False), MW() ]),                          # SL1 (IX+d) (undocumemnted)
    (0xDD, 0xCB, 0x3E) : (0, [], [ MR(action=SRL(), incaddr=False), MW() ]),                          # SRA (IX+d)
    (0xDD, 0xCB, 0x46) : (0, [], [ MR(action=BIT(0)) ]),                                              # BIT 0,(IX+d)
    (0xDD, 0xCB, 0x4E) : (0, [], [ MR(action=BIT(1)) ]),                                              # BIT 1,(IX+d)
    (0xDD, 0xCB, 0x56) : (0, [], [ MR(action=BIT(2)) ]),                                              # BIT 2,(IX+d)
    (0xDD, 0xCB, 0x5E) : (0, [], [ MR(action=BIT(3)) ]),                                              # BIT 3,(IX+d)
    (0xDD, 0xCB, 0x66) : (0, [], [ MR(action=BIT(4)) ]),                                              # BIT 4,(IX+d)
    (0xDD, 0xCB, 0x6E) : (0, [], [ MR(action=BIT(5)) ]),                                              # BIT 5,(IX+d)
    (0xDD, 0xCB, 0x76) : (0, [], [ MR(action=BIT(6)) ]),                                              # BIT 6,(IX+d)
    (0xDD, 0xCB, 0x7E) : (0, [], [ MR(action=BIT(7)) ]),                                              # BIT 7,(IX+d)
    (0xDD, 0xCB, 0x86) : (0, [], [ MR(action=RES(0), incaddr=False), MW() ]),                         # RES 0,(IX+d)
    (0xDD, 0xCB, 0x8E) : (0, [], [ MR(action=RES(1), incaddr=False), MW() ]),                         # RES 1,(IX+d)
    (0xDD, 0xCB, 0x96) : (0, [], [ MR(action=RES(2), incaddr=False), MW() ]),                         # RES 2,(IX+d)
    (0xDD, 0xCB, 0x9E) : (0, [], [ MR(action=RES(3), incaddr=False), MW() ]),                         # RES 3,(IX+d)
    (0xDD, 0xCB, 0xA6) : (0, [], [ MR(action=RES(4), incaddr=False), MW() ]),                         # RES 4,(IX+d)
    (0xDD, 0xCB, 0xAE) : (0, [], [ MR(action=RES(5), incaddr=False), MW() ]),                         # RES 5,(IX+d)
    (0xDD, 0xCB, 0xB6) : (0, [], [ MR(action=RES(6), incaddr=False), MW() ]),                         # RES 6,(IX+d)
    (0xDD, 0xCB, 0xBE) : (0, [], [ MR(action=RES(7), incaddr=False), MW() ]),                         # RES 7,(IX+d)
    (0xDD, 0xCB, 0xC6) : (0, [], [ MR(action=SET(0), incaddr=False), MW() ]),                         # SET 0,(IX+d)
    (0xDD, 0xCB, 0xCE) : (0, [], [ MR(action=SET(1), incaddr=False), MW() ]),                         # SET 1,(IX+d)
    (0xDD, 0xCB, 0xD6) : (0, [], [ MR(action=SET(2), incaddr=False), MW() ]),                         # SET 2,(IX+d)
    (0xDD, 0xCB, 0xDE) : (0, [], [ MR(action=SET(3), incaddr=False), MW() ]),                         # SET 3,(IX+d)
    (0xDD, 0xCB, 0xE6) : (0, [], [ MR(action=SET(4), incaddr=False), MW() ]),                         # SET 4,(IX+d)
    (0xDD, 0xCB, 0xEE) : (0, [], [ MR(action=SET(5), incaddr=False), MW() ]),                         # SET 5,(IX+d)
    (0xDD, 0xCB, 0xF6) : (0, [], [ MR(action=SET(6), incaddr=False), MW() ]),                         # SET 6,(IX+d)
    (0xDD, 0xCB, 0xFE) : (0, [], [ MR(action=SET(7), incaddr=False), MW() ]),                         # SET 7,(IX+d)

    (0xFD, 0xCB, 0x06) : (0, [], [ MR(action=RLC(), incaddr=False), MW() ]),                          # RLC (IY+d)
    (0xFD, 0xCB, 0x0E) : (0, [], [ MR(action=RRC(), incaddr=False), MW() ]),                          # RRC (IY+d)
    (0xFD, 0xCB, 0x16) : (0, [], [ MR(action=RL(), incaddr=False), MW() ]),                           # RL (IY+d)
    (0xFD, 0xCB, 0x1E) : (0, [], [ MR(action=RR(), incaddr=False), MW() ]),                           # RR (IY+d)
    (0xFD, 0xCB, 0x26) : (0, [], [ MR(action=SLA(), incaddr=False), MW() ]),                          # SLA (IY+d)
    (0xFD, 0xCB, 0x2E) : (0, [], [ MR(action=SRA(), incaddr=False), MW() ]),                          # SRA (IY+d)
    (0xFD, 0xCB, 0x36) : (0, [], [ MR(action=SL1(), incaddr=False), MW() ]),                          # SL1 (IY+d) (undocumemnted)
    (0xFD, 0xCB, 0x3E) : (0, [], [ MR(action=SRL(), incaddr=False), MW() ]),                          # SRA (IY+d)
    (0xFD, 0xCB, 0x46) : (0, [], [ MR(action=BIT(0)) ]),                                              # BIT 0,(IY+d)
    (0xFD, 0xCB, 0x4E) : (0, [], [ MR(action=BIT(1)) ]),                                              # BIT 1,(IY+d)
    (0xFD, 0xCB, 0x56) : (0, [], [ MR(action=BIT(2)) ]),                                              # BIT 2,(IY+d)
    (0xFD, 0xCB, 0x5E) : (0, [], [ MR(action=BIT(3)) ]),                                              # BIT 3,(IY+d)
    (0xFD, 0xCB, 0x66) : (0, [], [ MR(action=BIT(4)) ]),                                              # BIT 4,(IY+d)
    (0xFD, 0xCB, 0x6E) : (0, [], [ MR(action=BIT(5)) ]),                                              # BIT 5,(IY+d)
    (0xFD, 0xCB, 0x76) : (0, [], [ MR(action=BIT(6)) ]),                                              # BIT 6,(IY+d)
    (0xFD, 0xCB, 0x7E) : (0, [], [ MR(action=BIT(7)) ]),                                              # BIT 7,(IY+d)
    (0xFD, 0xCB, 0x86) : (0, [], [ MR(action=RES(0), incaddr=False), MW() ]),                         # RES 0,(IY+d)
    (0xFD, 0xCB, 0x8E) : (0, [], [ MR(action=RES(1), incaddr=False), MW() ]),                         # RES 1,(IY+d)
    (0xFD, 0xCB, 0x96) : (0, [], [ MR(action=RES(2), incaddr=False), MW() ]),                         # RES 2,(IY+d)
    (0xFD, 0xCB, 0x9E) : (0, [], [ MR(action=RES(3), incaddr=False), MW() ]),                         # RES 3,(IY+d)
    (0xFD, 0xCB, 0xA6) : (0, [], [ MR(action=RES(4), incaddr=False), MW() ]),                         # RES 4,(IY+d)
    (0xFD, 0xCB, 0xAE) : (0, [], [ MR(action=RES(5), incaddr=False), MW() ]),                         # RES 5,(IY+d)
    (0xFD, 0xCB, 0xB6) : (0, [], [ MR(action=RES(6), incaddr=False), MW() ]),                         # RES 6,(IY+d)
    (0xFD, 0xCB, 0xBE) : (0, [], [ MR(action=RES(7), incaddr=False), MW() ]),                         # RES 7,(IY+d)
    (0xFD, 0xCB, 0xC6) : (0, [], [ MR(action=SET(0), incaddr=False), MW() ]),                         # SET 0,(IY+d)
    (0xFD, 0xCB, 0xCE) : (0, [], [ MR(action=SET(1), incaddr=False), MW() ]),                         # SET 1,(IY+d)
    (0xFD, 0xCB, 0xD6) : (0, [], [ MR(action=SET(2), incaddr=False), MW() ]),                         # SET 2,(IY+d)
    (0xFD, 0xCB, 0xDE) : (0, [], [ MR(action=SET(3), incaddr=False), MW() ]),                         # SET 3,(IY+d)
    (0xFD, 0xCB, 0xE6) : (0, [], [ MR(action=SET(4), incaddr=False), MW() ]),                         # SET 4,(IY+d)
    (0xFD, 0xCB, 0xEE) : (0, [], [ MR(action=SET(5), incaddr=False), MW() ]),                         # SET 5,(IY+d)
    (0xFD, 0xCB, 0xF6) : (0, [], [ MR(action=SET(6), incaddr=False), MW() ]),                         # SET 6,(IY+d)
    (0xFD, 0xCB, 0xFE) : (0, [], [ MR(action=SET(7), incaddr=False), MW() ]),                         # SET 7,(IY+d)
    }

def decode_instruction(instruction):
    """Decode an instruction code and return a tuple of:
    (extra_time_for_OCF, [list of callables as side-effects of OCF], [ list of new machine states to add to pipeline ])"""
    if instruction in INSTRUCTION_STATES:
        return INSTRUCTION_STATES[instruction]
    raise UnrecognisedInstructionError(instruction)
