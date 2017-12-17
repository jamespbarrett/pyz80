"""An implementation of an emulation of the memory bus expected by a Z80 
processor.

The Z80 has a 16-bit address bus and 8-bit data bus, which allows the addressing
of up to 64KB of memory as individual octets. 

This module includes a class which emulates such a data bus in a relatively
simple fashion, as well as some options to map portions of this memory space to
peripherals such as ROM chips and IO."""

__all__ = [ "MemoryBus", "Peripheral", "FileROM", "RAM", "ROM" ]

class MemoryBus (object):
    """This class represents a memory bus."""

    def __init__(self, size=0x10000, mappings=[]):
        """Size is the number of bytes the bus can address (default is 64KB),
        mappings should be a list of 3-tuples of the form:
          (start, size, peripheral)
        where start and size are integers indicating the starting address and
        size of the mapped region, and peripheral is an object which is an
        instance of class Peripheral."""
        self.size = size
        pages = []
        mappings = sorted(mappings, key=lambda m : m[0])
        ramcount = 0
        ramstart = 0
        for n in range(0, (size + 255)/256):
            if len(mappings) > 0 and n*256 >= mappings[0][0] and n*256 < mappings[0][0] + mappings[0][1]:
                if ramcount > 0:
                    ram = RAM(ramcount*256)
                    while ramcount > 0:
                        pages.append((ramstart, ram))
                        ramcount -= 1
                pages.append((mappings[0][0], mappings[0][2]))
                if (n+1)*256 == mappings[0][0] + mappings[0][1]:
                    mappings.pop(0)
            else:
                if ramcount == 0:
                    ramstart = n
                ramcount += 1
        if ramcount > 0:
            ram = RAM(ramcount*256)
            while ramcount > 0:
                pages.append((ramstart, ram))
                ramcount -= 1
        self.pages = list(pages)

    def read(self, address):
        """Read from the specified address."""
        return self.pages[(address >> 8)][1].read(address - self.pages[(address >> 8)][0])

    def write(self, address, data):
        """Write to the specified address."""
        self.pages[(address >> 8)][1].write(address - self.pages[(address >> 8)][0], data)

    def memory_map(self, granularity=0x100):
        """Print a nice representation of the memory map."""
        mmap = []
        periph = None
        for n in range(0, (len(self.pages) << 8)/granularity):
            page = self.pages[(n*granularity) >> 8]
            if periph != page[1]:
                periph = page[1]
                mmap.append(("0x%04x +" + ('-'*71) + "+") % (n*granularity, ))
                mmap.append(("       | %s" + (' '*(70 - len(page[1].description()))) + "|") % (page[1].description(), ))
            else:
                mmap.append("       |" + (' '*71) + "|")
        mmap.append("       +" + ('-'*71) + "+")
        return "\n".join(mmap)

class Peripheral (object):
    def __init__(self):
        pass

    def read(self, address):
        """Read from the specified address."""
        return 0xFF

    def write(self, address, data):
        """Write to the specified address."""
        pass

    def description(self):
        """Return a single line description of this peripheral."""
        return "Generic Peripheral"

class RAM (Peripheral):
    def __init__(self, size):
        self.size = size
        self.data = bytearray(size)

    def read (self, address):
        return self.data[address % self.size]

    def write (self, address, data):
        self.data[address % self.size] = data&0xFF

    def description(self):
        return "RAM"

class ROM (Peripheral):
    def __init__(self, data, name="Custom ROM"):
        if isinstance(data, list) or isinstance(data, tuple):
            data = ''.join("%c" % x for x in data)
        self.data = bytes(data)
        self.size = len(self.data)
        self.name = name

    def read(self, address):
        return ord(self.data[address % self.size])

    def write(self, address, data):
        pass

    def description(self):
        return "ROM ( %s )" % (self.name,)

class FileROM (ROM):
    def __init__(self, filename):
        with open(filename, "r") as f:
            data = bytes(f.read())
        super(FileROM, self).__init__(data, name=filename)

if __name__ == "__main__": # pragma: no cover
    bus = MemoryBus(mappings=[(0x00, 0x4000, FileROM("tmp.rom"))])

    print bus.memory_map(granularity=0x1000)
