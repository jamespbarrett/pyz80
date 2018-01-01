from .ULA import SpectrumULA
from .cpu import Z80CPU, CPUStalled
from .memorybus import MemoryBus, FileROM
from .iobus import IOBus
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
        try:
            cpu.clock()
            ula.clock()
        except CPUStalled as e:
            print(format_exc())
            break
        except:
            print(format_exc())
            print()
            inst = cpu.most_recent_instruction
            if isinstance(inst, tuple):
                inst = "(" + ', '.join( "0x{:02X}".format(i) for i in inst ) + ")"
            elif isinstance(inst, int):
                inst = "0x{:02X}".format(inst)
            print("Most recent instruction processed: {!r}".format(inst))
            print("On t-state number: {}".format(cpu.tick_count))
            print()
            print(cpu.CPU_STATE())
            print()
            print(cpu.reg.registermap())
            print()
            print("Memory around PC:")
            PC = cpu.reg.PC
            start = max(0, PC - 8)
            for n in range(start, start + 16):
                if n != PC:
                    print("0x{:04X} : 0x{:02X}".format(n,cpu.membus.read(n)))
                else:
                    print("0x{:04X} : 0x{:02X} <-- (PC)".format(n,cpu.membus.read(n)))
            print()
            break
        n+=1

if __name__ == "__main__":
    main()
