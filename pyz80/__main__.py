from ULA import SpectrumULA
from cpu import Z80CPU, CPUStalled
from memorybus import MemoryBus, FileROM
from iobus import IOBus
from time import time,sleep
from traceback import format_exc
import pkg_resources

DATA_PATH = pkg_resources.resource_filename('pyz80', 'roms/')
ROM_FILE = pkg_resources.resource_filename('pyz80', 'roms/48.rom')

def main(args=None):
    ula    = SpectrumULA(scale=2)
    membus = MemoryBus(mappings=[
        (0x0000, 0x4000, FileROM(ROM_FILE)),
        (0x4000, 0x1B00, ula.display)
        ])
    iobus  = IOBus([ ula.io ])

    cpu    = Z80CPU(iobus, membus)
    ula.setup_interrupts(69888, cpu.interrupt)

    n = 0
    while True:
        print cpu.reg.PC
        try:
            cpu.clock()
            ula.update()
        except CPUStalled as e:
            print format_exc()
            break
        except:
            raise
        n+=1

if __name__ == "__main__":
    main()
