import unittest
from pyz80.iobus import *
import mock

class TestIOBus(unittest.TestCase):
    def test_read(self):
        devices = [ mock.MagicMock(Device, name="device" + str(n)) for n in range(0,4) ]
        def matches(n):
            def __inner(p):
                return p == n
            return __inner
        for n in range(0,4):
            devices[n].responds_to_port.side_effect = matches(n)
            devices[n].read.side_effect = lambda a : a + n

        UUT = IOBus(devices)

        for n in range(0,4):
            for a in range(0,256):
                for device in devices:
                    device.reset_mock()
                self.assertEqual(a+n, UUT.read(n, a))
                devices[n].read.assert_called_once_with(a)
                for device in devices:
                    if device != devices[n]:
                        device.read.assert_not_called()

    def test_write(self):
        devices = [ mock.MagicMock(Device, name="device" + str(n)) for n in range(0,4) ]
        def matches(n):
            def __inner(p):
                return p == n
            return __inner
        for n in range(0,4):
            devices[n].responds_to_port.side_effect = matches(n)

        UUT = IOBus(devices)

        for n in range(0,4):
            for a in range(0,256):
                for device in devices:
                    device.reset_mock()
                UUT.write(n, a, mock.sentinel.data)
                devices[n].write.assert_called_once_with(a, mock.sentinel.data)
                for device in devices:
                    if device != devices[n]:
                        device.write.assert_not_called()

class TestDevice(unittest.TestCase):
    def test_responds_to_port(self):
        UUT = Device()
        for n in range(0,256):
            self.assertFalse(UUT.responds_to_port(n))

    def test_read(self):
        UUT = Device()
        for a in range(0,256):
            self.assertEqual(0x00, UUT.read(a))

    def test_write(self):
        UUT = Device()
        for a in range(0,256):
            UUT.write(a, mock.sentinel.data)
