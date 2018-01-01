from .registers import RegisterFile
from .machinestates import *

class CPUStalled(Exception):
    pass

class Z80CPU(object):
    def __init__(self, iobus, membus):
        self.iobus  = iobus
        self.membus = membus
        self.iff1 = 0
        self.iff2 = 0
        self.int = False
        self.pending_interrupts = []
        self.interrupt_mode = 0

        self.reg = RegisterFile()

        self.most_recent_instruction = None
        self.tick_count = 0

        # This member holds all of the active instruction pipelines currently being worked on by the cpu
        # It starts off with a single pipeline containing a single OCF (Op Code Fetch) machine state
        self.pipelines = [
            [ OCF()().setcpu(self), ],
            ]

    def clock(self):
        """This method executes a single clock cycle on the CPU's state machine."""
        for pipeline in self.pipelines:
            pipeline[0].clock(pipeline)
            self.tick_count += 1
        while len(self.pipelines) > 0 and len(self.pipelines[0]) == 0:
            self.pipelines.pop(0)
        if all(all(not state.fetchlocked() for state in pipeline) for pipeline in self.pipelines):
            self.most_recent_instruction = None
            self.tick_count = 0
            interrupt = None

            if len([ ack for (nmi, ack) in self.pending_interrupts if nmi ]) > 0:
                interrupt = [ (nmi, ack) for (nmi, ack) in self.pending_interrupts if nmi ][-1]
            elif (len(self.pending_interrupts) > 0):
                interrupt = self.pending_interrupts[-1]
            self.pending_interrupts = []
            if interrupt is not None:
                self.iff1 = 0
                if not interrupt[0]:
                    self.iff2 = 0
                self.pipelines.append(interrupt_response(self, interrupt[0], ack=interrupt[1]))
            elif self.int == True:
                raise Exception("Should be a processable interrupt here, but there isn't")

            self.int = False
        if all(all(not state.fetchlocked() for state in pipeline) for pipeline in self.pipelines):
            self.pipelines.append([ OCF()().setcpu(self), ])

        if len(self.pipelines) == 0:
            raise CPUStalled("No instructions in pipeline")

        return self.tick_count

    def interrupt(self, ack=None, nmi=False):
        """Call to initiate an interrupt. Set ack to a generator taking the cpu as an argument, which will be called in response 
        to the interrupt if it is accepted, any values it yields will be used as the data on the data bus from the external interrupting device,
        otherwise 0x00 will be used. If nmi is set to True then the interrupt will be non-maskable, and will have higher priority."""
        self.int = self.int or nmi or (self.iff1 != 0)
        if nmi or (self.iff1 != 0):
            self.pending_interrupts.append((nmi, ack))

    def CPU_STATE(self):
        rval = []
        rval += [ ('\n'.join('[ ' + (', '.join(repr(state) for state in pipeline)) + ' ],' for pipeline in self.pipelines)) ]
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
