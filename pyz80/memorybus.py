"""An implementation of an emulation of the memory bus expected by a Z80 
processor.

The Z80 has a 16-bit address bus and 8-bit data bus, which allows the addressing
of up to 64KB of memory as individual octets. 

This module includes a class which emulates such a data bus in a relatively
simple fashion, as well as some options to map portions of this memory space to
peripherals such as ROM chips and IO."""

__all__ = [ "MemoryBus", "Peripheral", "FileROM" ]

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
        self.mappings = mappings
        self.data = bytearray(size)

    def read(self, address):
        """Read from the specified address."""
        address %= self.size
        for mapping in self.mappings:
            if address >= mapping[0] and address < mapping[0] + mapping[1]:
                return mapping[2].read(address - mapping[0])
        return self.data[address]

    def write(self, address, data):
        """Write to the specified address."""
        address %= self.size
        for mapping in self.mappings:
            if address >= mapping[0] and address < mapping[0] + mapping[1]:
                return mapping[2].write(address - mapping[0], data)
        self.data[address] = data

    def memory_map(self, granularity=0x100):
        """Print a nice representation of the memory map."""
        mmap = []
        segments = []
        for mapping in self.mappings:
            segments.append((mapping[0], mapping[1], mapping[2].description()))
        segments = sorted(segments, key=lambda x : x[0])
        n = 0
        l = 0
        while n*granularity < self.size:
            if len(segments) == 0 or n*granularity < segments[0][0]:
                if l == 0:
                    mmap.append(("0x%04x +" + ('-'*71) + "+") % (n*granularity, ))
                    mmap.append("       | RAM" + (' '*67) + "|")
                else:
                    mmap.append("       |" + (' '*71) + "|")
                l += 1
            else:
                if n*granularity == segments[0][0]:
                    l = 0
                    mmap.append(("0x%04x +" + ('-'*71) + "+") % (n*granularity, ))
                    mmap.append(("       | %s" + (' '*(70 - len(segments[0][2]))) + "|") % (segments[0][2], ))
                else:
                    mmap.append("       |" + (' '*71) + "|")

                if l*granularity < segments[0][1] and (l+1)*granularity >= segments[0][1]:
                    l = 0
                    segments.pop(0)
                else:
                    l += 1
            n += 1
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

class FileROM (Peripheral):
    def __init__(self, filename):
        with open(filename, "r") as f:
            self.data = bytes(f.read())
        self.size = len(self.data)
        self.filename = filename

    def read(self, address):
        return ord(self.data[address % self.size])

    def write(self, address, data):
        pass

    def description(self):
        return "ROM ( %s )" % (self.filename,)

if __name__ == "__main__": # pragma: no cover
    bus = MemoryBus(mappings=[(0x00, 0x4000, FileROM("tmp.rom"))])

    print bus.memory_map(granularity=0x1000)
