"""This module contains classes implementing a simple video adapter and keyboard device 
for our Z80 emulator. Specifically one modeled on the Spectrum.

To use any of these classes the program must run a tkinter main loop."""

__all__ = [ "SpectrumULA" ]

import Tkinter
from memorybus import Peripheral
from iobus import Device
from time import time

class SpectrumULA (object):
    """This is the class that defines the spectrum ULA."""

    class DisplayAdapter(Peripheral):
        """This inner class represents the display adapter."""

        pallette = [ ('#000000', '#000000'),
                 ('#0000D7', '#0000FF'),
                 ('#D70000', '#FF0000'),
                 ('#D700D7', '#FF00FF'),
                 ('#00D700', '#00FF00'),
                 ('#00D7D7', '#00FFFF'),
                 ('#D7D700', '#FFFF00'),
                 ('#D7D7D7', '#FFFFFF'), ]

        def __init__(self, parent):
            self.parent = parent
            self.canvas = Tkinter.Canvas(parent.window,
                                         width=256*parent.scale,
                                         height=192*parent.scale,
                                         bg='#000000')
            self.data = bytearray(0x1B00)
            self.canvas.pack()
            self.last_flash = int(time())
            self.flash = 0x00
            self.pixels = []
            for addr in range(0,0x1800):
                y = ((addr >> 8)&0x7) + ((addr >> 2)&0x38) + ((addr >> 5)&0xC0)
                x = ((addr >> 0)&0x1F)
                pixels = []
                for i in range(0,8):
                    pixel = self.canvas.create_rectangle((x*8 + i)*parent.scale,
                                                        y*parent.scale,
                                                        (x*8 + i + 1)*parent.scale,
                                                        (y + 1)*parent.scale,
                                                        fill="#000000",
                                                        width=0)
                    pixels.append(pixel)
                self.pixels.append(pixels)

        def read(self, addr):
            """Read from video memory."""
            return self.data[addr]

        def write(self, addr, data):
            """Write to video memory, and update the display."""
            self.data[addr] = data

            if addr < 0x1800:
                # This is a write to the bitmap region, only update the relevent part
                y = ((addr >> 5)&0x7) + ((addr >> 8)&0x18)
                x = ((addr >> 0)&0x1F)
                attributes = self.data[0x1800 + y*32 + x]
                fg = self.pallette[(attributes & 0x7)][(attributes >> 6)&0x1]
                bg = self.pallette[((attributes >> 3) & 0x7)][(attributes >> 6)&0x1]
                if (attributes >> 7) == 1:
                        data = data ^ self.flash
                for i in range(0,8):
                    if (data&0x1) == 0:
                        c = bg
                    else:
                        c = fg
                    pixel = self.pixels[addr][i]
                    self.canvas.itemconfigure(pixel, fill=c)
                    data >>= 1
            else:
                # This is a change to attributes, so whole 8x8 block needs updating
                y = (addr - 0x1800)/32
                x = (addr - 0x1800)%32
                fg = self.pallette[(data & 0x7)][(data >> 6)&0x1]
                bg = self.pallette[((data >> 3) & 0x7)][(data >> 6)&0x1]
                pixaddr = ((y << 5)&0x00E0) + ((y << 8)&0x1800) + x
                for j in range(0,8):
                    pixdata = self.data[pixaddr]
                    if (data >> 7) == 1:
                        pixdata = pixdata ^ self.flash
                    for i in range(0,8):
                        if (pixdata&0x1) == 0:
                            c = bg
                        else:
                            c = fg
                        pixel = self.pixels[pixaddr][i]
                        self.canvas.itemconfigure(pixel, fill=c)
                        pixdata >>= 1
                    pixaddr += 0x100

        def description(self):
            return "Spectrum Video Adapter"

        def update(self):
            t = int(time())
            if t != self.last_flash:
                self.last_flash = t
                self.flash = ~self.flash
                for y in range(0,24):
                    for x in range(0,32):
                        attributes = self.data[0x1800 + y*32 + x]
                        if (attributes >> 7) == 1:
                            fg = self.pallette[(attributes & 0x7)][(attributes >> 6)&0x1]
                            bg = self.pallette[((attributes >> 3) & 0x7)][(attributes >> 6)&0x1]
                            pixaddr = ((y << 5)&0x00E0) + ((y << 8)&0x1800) + x
                            for j in range(0,8):
                                pixdata = self.data[pixaddr]
                                pixdata = pixdata ^ self.flash
                                for i in range(0,8):
                                    if (pixdata&0x1) == 0:
                                        c = bg
                                    else:
                                        c = fg
                                    pixel = self.pixels[pixaddr][i]
                                    self.canvas.itemconfigure(pixel, fill=c)
                                    pixdata >>= 1
                                pixaddr += 0x100

    def __init__(self, scale=4):
        self._running = True
        self.window = Tkinter.Tk()
        self.window.protocol("WM_DELETE_WINDOW", self.kill)
        self.scale = scale
        self.display = self.DisplayAdapter(self)

    def running(self):
        """Returns true if the main window is still open."""
        return self._running

    def update(self):
        """Call repeatedly in the main program loop to keep GUI updated."""
        self.display.update()
        self.window.update_idletasks()
        self.window.update()

    def kill(self):
        """Destroys the main window."""
        self._running = False
        self.window.destroy()

if __name__ == "__main__": # pragma: no cover
    from memorybus import MemoryBus

    ula = SpectrumULA(scale=2)
    vid = ula.display
    bus = MemoryBus(mappings=[(0x4000, 0x1B00, vid)])
    for i in range(0,8):
        for j in range(0,32):
            bus.write(0x5800 + i*32 + j, (j&0x7) + ((i&0x7) << 3))
    for i in range(0,8):
        for j in range(0,32):
            bus.write(0x5900 + i*32 + j, 0x80 + (j&0x7) + ((i&0x7) << 3))
    for i in range(0,8):
        for j in range(0,32):
            bus.write(0x5A00 + i*32 + j, 0x40 + (j&0x7) + ((i&0x7) << 3))

    addr = 0x4000
    mode = "pixels"
    while ula.running():
        if mode == "pixels":
            d = bus.read(addr)
            bus.write(addr, 0x55)
#            if d == 0x7F:
            addr += 1
            if addr == 0x5800:
                mode = "attributes"
        elif mode == "attributes":
            d = bus.read(addr)
            bus.write(addr, (d + 1)&0xFF)
            addr += 1
            if addr == 0x5B00:
                addr = 0x5800
        ula.update()
