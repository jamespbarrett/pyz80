import unittest
from pyz80.memorybus import MemoryBus
from pyz80.ULA import *
import mock

class TestSpectrumULA(unittest.TestCase):
    def setUp(self):
        self.pixels = {}

        with mock.patch('Tkinter.Tk') as tk:
            with mock.patch('Tkinter.Canvas') as Canvas:
                Canvas.return_value.create_rectangle = lambda *args, **kwargs : (args[0], args[1])
                self.UUT = SpectrumULA()

                Canvas.assert_called_once_with(tk.return_value,
                                                   width=256*self.UUT.scale,
                                                   height=192*self.UUT.scale,
                                                   bg="#000000")
                self.canvas = Canvas.return_value
        self.canvas.pack.assert_called_once_with()

        self.bus = MemoryBus(mappings=[(0x4000, 0x1B00, self.UUT.display)])

    def test_init(self):
        pass

    def test_read(self):
        for addr in range(0,0x1B00):
            self.bus.write(0x4000 + addr, addr&0xFF)
            self.assertEqual(addr&0xFF, self.bus.read(0x4000 + addr))

    def test_running(self):
        self.assertTrue(self.UUT.running())
        self.UUT.kill()
        self.assertFalse(self.UUT.running())
        self.UUT.window.destroy.assert_called_once_with()

    def assert_write_pixel(self, x, y, bg=0, fg=7, flash=False):
        self.canvas.itemconfigure.reset_mock()
        self.UUT.display.data[0x1800 + (y/8)*32 + (x/8)] = (0x80 if flash else 0x00) + fg + (bg << 3)
        bitval = 1 << (x%8)
        addr = 0x4000 + (x/8) + ((y&0x7) << 8) + ((y&0x38) << 2) + ((y&0xC0) << 5)
        self.bus.write(addr, bitval)

        expected_calls = []
        flip = (flash and (self.UUT.display.flash != 0x00))
        for i in range(0,8):
            if (not flip and ((1 << i) != bitval)) or (flip and ((1 << i) == bitval)):
                expected_calls.append(mock.call((((x/8)*8 + i)*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.display.pallette[bg][0]))
            else:
                expected_calls.append(mock.call((((x/8)*8 + i)*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.display.pallette[fg][0]))
        self.assertItemsEqual(self.canvas.itemconfigure.mock_calls, expected_calls)


    def test_write_pixels(self):
        for y in range(0,192):
            self.assert_write_pixel(255 - y,y)
        for y in range(0,192):
             self.assert_write_pixel(y,y, flash=True)
        self.UUT.display.flash = 0xFF
        for y in range(0,192):
            self.assert_write_pixel((2*y)%256 + int((2*y)/256),y, flash=True)

    def assert_write_attributes(self, x, y, fg=7, bg=0, flash=False):
        self.maxDiff = None
        self.canvas.itemconfigure.reset_mock()
        addr = x + ((y&0x7) << 5) + ((y&0x18) << 8)
        for i in range(0,8):
            self.UUT.display.data[addr] = 0x55
            addr += 0x100

        addr = 0x5800 + (y*32) + x
        self.bus.write(addr, (0x80 if flash else 0x00) + (fg) + (bg << 3))

        expected_calls = []
        for j in range(0,8):
            for i in range(0,4):
                if flash and (self.UUT.display.flash != 0x00):
                    expected_calls.append(mock.call(( (x*8 + 2*i + 1)*self.UUT.scale, (y*8 + j)*self.UUT.scale ), fill=self.UUT.display.pallette[fg][0]))
                    expected_calls.append(mock.call(((x*8 + 2*i + 0)*self.UUT.scale, (y*8 + j)*self.UUT.scale ), fill=self.UUT.display.pallette[bg][0]))
                else:
                    expected_calls.append(mock.call(( (x*8 + 2*i + 1)*self.UUT.scale, (y*8 + j)*self.UUT.scale ), fill=self.UUT.display.pallette[bg][0]))
                    expected_calls.append(mock.call(((x*8 + 2*i + 0)*self.UUT.scale, (y*8 + j)*self.UUT.scale ), fill=self.UUT.display.pallette[fg][0]))
        self.assertItemsEqual(self.canvas.itemconfigure.mock_calls, expected_calls)

    def test_write_attributes(self):
        for y in range(0,24):
            self.assert_write_attributes(y,y)
        for y in range(0,24):
            self.assert_write_attributes(31-y,y, flash=True)
        self.UUT.display.flash = 0xFF
        for y in range(0,24):
            self.assert_write_attributes((2*y)%32 + int((2*y)/32),y, flash=True)

    def test_update(self):
        with mock.patch('pyz80.ULA.time', return_value=self.UUT.display.last_flash + 1):
            self.UUT.update()
        self.UUT.window.update_idletasks.assert_called_once_with()
        self.UUT.window.update.assert_called_once_with()

    def test_flash(self):
        self.UUT.display.data[0x1800] = 0x87
        for j in range(0,8):
            self.UUT.display.data[j*0x100] = 0x55

        with mock.patch('pyz80.ULA.time', side_effect=lambda : self.UUT.display.last_flash + 1):
            self.UUT.update()

        expected_calls = []
        for y in range(0,8):
            for x in range(0,4):
                expected_calls.append(mock.call(( 2*x*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.display.pallette[0][0]))
                expected_calls.append(mock.call(( (2*x + 1)*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.display.pallette[7][0]))
        self.assertItemsEqual(expected_calls, self.canvas.itemconfigure.mock_calls)

        self.canvas.itemconfigure.reset_mock()
        with mock.patch('pyz80.ULA.time', side_effect=lambda : self.UUT.display.last_flash):
            self.UUT.update()

        self.canvas.itemconfigure.assert_not_called()

        self.canvas.itemconfigure.reset_mock()
        with mock.patch('pyz80.ULA.time', side_effect=lambda : self.UUT.display.last_flash + 1):
            self.UUT.update()

        expected_calls = []
        for y in range(0,8):
            for x in range(0,4):
                expected_calls.append(mock.call(( 2*x*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.display.pallette[7][0]))
                expected_calls.append(mock.call(( (2*x + 1)*self.UUT.scale, y*self.UUT.scale), fill=self.UUT.display.pallette[0][0]))
        self.assertItemsEqual(expected_calls, self.canvas.itemconfigure.mock_calls)

    def test_description(self):
        self.assertIsInstance(self.UUT.display.description(), basestring)
