from registers import RegisterFile
from machinestates import *

class CPUStalled(Exception):
    pass

class Z80CPU(object):
    def __init__(self, iobus, membus):
        self.iobus  = iobus
        self.membus = membus

        self.reg = RegisterFile()

        # This member holds all of the active instruction pipelines currently being worked on by the cpu
        # It starts off with a single pipeline containing a single OCF (Op Code Fetch) machine state
        self.pipelines = [
            [ OCF().setcpu(self), ],
            ]

    def clock(self):
        """This method executes a single clock cycle on the CPU's state machine."""
        for pipeline in self.pipelines:
            pipeline[0].clock(pipeline)
        while len(self.pipelines) > 0 and len(self.pipelines[0]) == 0:
            self.pipelines.pop(0)
        if all(all(not state.fetchlocked() for state in pipeline) for pipeline in self.pipelines):
            self.pipelines.append([ OCF().setcpu(self), ])

        if len(self.pipelines) == 0:
            raise CPUStalled("No instructions in pipeline")

    def CPU_STATE(self):
        return '\n'.join('[ ' + (', '.join(repr(state) for state in pipeline)) + ' ],' for pipeline in self.pipelines)

if __name__ == "__main__": #pragma: no cover
    from ULA import SpectrumULA
    from memorybus import MemoryBus, ROM
    from iobus import IOBus
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
            print "Tick: %d" % n
            cpu.clock()
            ula.update()
            print cpu.CPU_STATE()
            print cpu.reg.registermap()
            if (raw_input("Press Enter to continue (or type 'q<Enter>' to quit)... ") == 'q'):
                break
        except CPUStalled as e:
            print format_exc()
            break
        n+=1
