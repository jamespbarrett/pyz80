import unittest
from pyz80.memorybus import MemoryBus
from pyz80.videoadapter import *
import mock

class TestSpectrumVideoAdapter(unittest.TestCase):
    def setUp(self):
        self.pixels = {}

        with mock.patch('Tkinter.Tk') as tk:
            with mock.patch('Tkinter.Canvas') as Canvas:
                Canvas.return_value.create_rectangle = lambda *args, **kwargs : (args[0], args[1])
                self.UUT = SpectrumDisplayAdapter()

                Canvas.assert_called_once_with(tk.return_value,
                                                   width=256*self.UUT.scale,
                                                   height=192*self.UUT.scale,
                                                   bg="#000000")
                self.canvas = Canvas.return_value
        self.canvas.pack.assert_called_once_with()

        self.bus = MemoryBus(mappings=[(0x4000, 0x1B00, self.UUT)])

    def test_init(self):
        pass

    def assert_write_pixel(self, x, y, bg=0, fg=7):
        self.canvas.itemconfigure.reset_mock()
        self.UUT.data[0x1800 + (y/8)*32 + (x/8)] = fg + (bg << 3)
        bitval = 1 << (x%8)
        addr = 0x4000 + (x/8) + ((y&0x7) << 8) + ((y&0x38) << 2) + ((y&0xC0) << 5)
        self.bus.write(addr, bitval)

        expected_calls = []
        for i in range(0,8):
            if (1 << i) != bitval:
                expected_calls.append(mock.call((((x/8)*8 + i)*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.pallette[bg][0]))
            else:
                expected_calls.append(mock.call((((x/8)*8 + i)*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.pallette[fg][0]))               
        self.assertItemsEqual(self.canvas.itemconfigure.mock_calls, expected_calls)

    def test_write_pixels(self):
        for y in range(0,192):
            for x in range(0,256):
                self.assert_write_pixel(x,y)

    def assert_write_attributes(self, x, y, fg=7, bg=0):
        self.canvas.itemconfigure.reset_mock()
        addr = x + ((y&0x7) << 5) + ((y&0x18) << 8)
        for i in range(0,8):
            self.UUT.data[addr] = 0x55
            addr += 0x100

        addr = 0x5800 + (y*32) + x
        self.bus.write(addr, (fg) + (bg << 3))

        expected_calls = []
        for j in range(0,8):
            for i in range(0,4):
                expected_calls.append(mock.call(( (x*8 + 2*i + 1)*self.UUT.scale, (y*8 + j)*self.UUT.scale ), fill=self.UUT.pallette[bg][0]))
                expected_calls.append(mock.call(((x*8 + 2*i + 0)*self.UUT.scale, (y*8 + j)*self.UUT.scale ), fill=self.UUT.pallette[fg][0]))
        self.assertItemsEqual(self.canvas.itemconfigure.mock_calls, expected_calls)

    def test_write_attributes(self):
        for y in range(0,24):
            for x in range(0,32):
                self.assert_write_attributes(x,y)

    def test_update(self):
        with mock.patch('pyz80.videoadapter.time', return_value=self.UUT.last_flash + 1):
            self.UUT.update()
        self.UUT.window.update_idletasks.assert_called_once_with()
        self.UUT.window.update.assert_called_once_with()


