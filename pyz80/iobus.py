"""An implementation of an emulation of the io bus expected by a Z80 
processor.

The Z80 has a 16-bit address bus and 8-bit data bus, shared with the memory bus, 
however when used by the IO bus the LSB of the address bus is used to identify the 
device which will respond, whilst the MSB of the address bus is passed to the device 
as additional input.

This module includes a class which emulates such a bus in a relatively
simple fashion, as well as some options to map portions of this io space to
peripherals."""

__all__ = [ "IOBus", "Device" ]

class IOBus (object):
    """This class represents an io bus."""

    def __init__(self, devices=[]):
        """Devices should be a list of devices to connect to the bus."""
        self.devices = devices

    def read(self, port, high_address):
        """Read from the specified address on the specified port."""
        for device in self.devices:
            if device.responds_to_port(port):
                return device.read(high_address)

    def write(self, port, high_address, data):
        """Write to the specified address on the specified port."""
        for device in self.devices:
            if device.responds_to_port(port):
                device.write(high_address, data)
                return

class Device (object):
    def responds_to_port(self, port):
        """Override this in derived classes to return true for the correct ports."""
        return False

    def read(self, address):
        """Default implementation just returns 0."""
        return 0x00

    def write(self, address, data):
        """Default implementation does nothing."""
        pass
