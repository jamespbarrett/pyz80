from .registers import RegisterFile
from .machinestates import *

class CPUStalled(Exception):
    pass

STD_OCF = OCF()

class Z80CPU(object):
    def __init__(self, iobus, membus):
        self.iobus  = iobus
        self.membus = membus
        self.iff1 = 0
        self.iff2 = 0
        self.int = False
        self.nmi = False
        self.pending_nmi = None
        self.pending_interrupt = None
        self.interrupt_mode = 0

        self.reg = RegisterFile()

        self.most_recent_instruction = None
        self.tick_count = 0

        # This member holds all of the active instruction pipelines currently being worked on by the cpu
        # It starts off with a single pipeline containing a single OCF (Op Code Fetch) machine state
        self.pipeline = [ OCF()().setcpu(self), ]

    def clock(self):
        """This method executes a single clock cycle on the CPU's state machine."""
        self.pipeline[0].clock(self.pipeline)
        self.tick_count += 1
        if len(self.pipeline) == 0:
            self.most_recent_instruction = None
            self.tick_count = 0

            if self.int:
                if self.nmi:
                    self.iff1 = 0
                    self.pipeline = interrupt_response(self, True, ack=self.pending_nmi)
                else:
                    self.iff1 = 0
                    self.iff2 = 0
                    self.pipeline = interrupt_response(self, False, ack=self.pending_interrupt)
                self.pending_nmi       = None
                self.pending_interrupt = None
                self.int               = False
                self.nmi               = False
            else:
                self.pipeline = [ STD_OCF().setcpu(self), ]

        if len(self.pipeline) == 0:
            raise CPUStalled("No instructions in pipeline")

        return self.tick_count

    def interrupt(self, ack=None, nmi=False):
        """Call to initiate an interrupt. Set ack to a generator taking the cpu as an argument, which will be called in response 
        to the interrupt if it is accepted, any values it yields will be used as the data on the data bus from the external interrupting device,
        otherwise 0x00 will be used. If nmi is set to True then the interrupt will be non-maskable, and will have higher priority."""
        if nmi:
            self.pending_nmi = ack
            self.int = True
            self.nmi = True
        elif self.iff1 != 0:
            self.pending_interrupt = ack
            self.int = True

    def CPU_STATE(self):
        rval = []
        rval += [ '[ ' + (', '.join(repr(state) for state in self.pipeline)) + ' ],' ]
        rval += [ """Interrupt Mode: {}, iff ({},{}), Pending Interrupts: {!r}""".format(self.interrupt_mode, self.iff1, self.iff2, self.int) ]
        return '\n\n'.join(rval)

if __name__ == "__main__": #pragma: no cover
    from .ULA import SpectrumULA
    from .memorybus import MemoryBus, ROM
    from .iobus import IOBus
    from traceback import format_exc
    from time import sleep

    program = [
        0x06, 0x55,       # LD B,55H
        0xDD, 0x7E, 0xFF, # LD A,(IX-01H)
        0xC3, 0x00, 0x00, # JP 0000H
        ]

    ula    = SpectrumULA(scale=2)
    membus = MemoryBus(mappings=[
        (0x0000, len(program), ROM(program)),
        (0x4000, 0x1B00, ula.display)
        ])
    iobus  = IOBus([ ula.io ])

    cpu    = Z80CPU(iobus, membus)
    cpu.reg.IX = 0x0001

    n = 0
    while True:
        try:
            print("Tick: %d" % n)
            cpu.clock()
            ula.update()
            print(cpu.CPU_STATE())
            print(cpu.reg.registermap())
            if (input("Press Enter to continue (or type 'q<Enter>' to quit)... ") == 'q'):
                break
        except CPUStalled as e:
            print(format_exc())
            break
        n+=1
