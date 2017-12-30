
class Debugger(object):
    def __init__(self, cpu, *args):
        self.cpu = cpu
        self.components = args
        self.commandhistory = []
        self.breakpoints = []

        self.commands = {
            "quit" : [ self.quit, "exit the debugger"],
            "help" : [ self.help, "print this message"],
            "list" : [ self.printstate, "print the state of the cpu and memory" ],
            "print" : [ self._print, "print a register value or location in memory" ],
            "next"  : [ self.next, "advance to next instruction (or more if argument provided)" ],
            "breakpoint" : [ self._break, "Set a breakpoint at given address" ],
            "deletebreakpoint" : [ self.deletebreakpoint, "Remove a breakpoint" ],
            "showbreakpoints" : [ self.showbreakpoints, "Show all breakpoints" ],
            "continue"        : [ self._continue, "Run until a breakpoint is hit or an exception thrown" ],
            "" : [self.dolastthing, None],
        }

    def decode_address(self, a):
        if a in ["AF", "BC", "DE", "HL", "SP", "PC", "IX", "IY"]:
            return getattr(self.cpu.reg, a)
        elif a.isdigit():
            return int(a,10)
        elif a[:2] == "0x":
            return int(a[2:],16)
        elif a[:2] == "IX" and a[2] == "+":
            if a[3:].isdigit():
                return self.cpu.reg.IX + int(a[3:],10)
            elif a[3:5] == "0x":
                return self.cpu.reg.IX + int(a[5:],16)
            else:
                raise Exception
        elif a[:2] == "IX" and a[2] == "-":
            if a[3:].isdigit():
                return self.cpu.reg.IX - int(a[3:],10)
            elif a[3:5] == "0x":
                return self.cpu.reg.IX - int(a[5:],16)
            else:
                raise Exception
        elif a[:2] == "IY" and a[2] == "+":
            if a[3:].isdigit():
                return self.cpu.reg.IY + int(a[3:],10)
            elif a[3:5] == "0x":
                return self.cpu.reg.IY + int(a[5:],16)
            else:
                raise Exception
        elif a[:2] == "IY" and a[2] == "-":
            if a[3:].isdigit():
                return self.cpu.reg.IY - int(a[3:],10)
            elif a[3:5] == "0x":
                return self.cpu.reg.IY - int(a[5:],16)
            else:
                raise Exception
        else:
            raise Exception

    def _break(self, *args):
        if len(args) == 0:
            print "Need an address to set break point at"
            return

        try:
            addr = self.decode_address(args[0])
        except:
            print "Bad argument: <{}>".format(args[0])

        self.breakpoints.append(addr)
        print "Set breakpoint <{}> at 0x{:04X}".format(len(self.breakpoints)-1, addr)

    def deletebreakpoint(self, *args):
        if len(args) == 0:
            n = len(self.breakpoints) - 1
        else:
            try:
                n = int(args[0])
            except:
                print "Bad argument: <{}>".format(args[0])

        if n >= 0:
            self.breakpoints[n] = None

    def help(self, *args):
        print "Commands:"
        for cmd in self.commands:
            if self.commands[cmd][1] is not None:
                print "{} -- {}".format(cmd, self.commands[cmd][1])
        print

    def quit(self, *args):
        return "quit"

    def dolastthing(self, *args):
        if len(self.commandhistory) > 0:
            if not self.executecommand(self.commandhistory[-1]):
                return "quit"

    def next(self, *args):
        if len(args) > 0:
            try:
                n = int(args[0])
            except:
                print "Invalid argument: <{}>".format(arg[0])
                return
        else:
            n = 1

        for _ in range(0,n):
            while self.cpu.clock() != 0:
                for comp in self.components:
                    comp.clock()
            self.printstate()

    def _continue(self, *args):
        while True:
            try:
                while self.cpu.clock() != 0:
                    for comp in self.components:
                        comp.clock()
            except:
                traceback.print_exc()
                print
                self.printstate()
                return

            n = 0
            for bp in self.breakpoints:
                if self.cpu.reg.PC == bp:
                    print "Hit breakpoint <{:02d}>".format(n)
                    print
                    self.printstate()
                    return
                n += 1

    def _print(self, *args):
        for arg in args:
            try:
                if arg in ["AF", "BC", "DE", "HL", "SP", "PC", "IX", "IY"]:
                    print " {} = 0x{:04x}".format(arg, getattr(self.cpu.reg, arg))
                elif arg in [ "A", "F", "B", "C", "D", "E", "H", "L", "SPH", "SPL", "PCH", "PCL", "IXH", "IXL", "IYH", "IYL", "I", "R" ]:
                    print " {} = 0x{:04x}".format(arg, getattr(self.cpu.reg, arg))
                elif arg[0] == "(" and arg[-1] == ")":
                    a = self.decode_address(arg[1:len(arg)-1])
                    print " {} = 0x{:02x}".format(arg, self.cpu.membus.read(a))
            except:
                print "Bad argument: <{}>".format(arg)

    def showbreakpoints(self, *args):
        n = 0
        for PC in self.breakpoints:
            if PC is not None:
                start = max(0, PC - 8)
                end   = min(0x10000, start + 16)
                print "  ".join("0x{:04X}".format(addr) for addr in range(start, end))
                print "-"*126
                print "  ".join(" 0x{:02X} ".format(self.cpu.membus.read(addr)) for addr in range(start, end))
                print "  ".join([ "      " for _ in range(start, PC) ] + [ "^<{:02d}>^".format(n) ] + [ "      " for _ in range(PC+1, end) ])
                print
            n += 1

    def printstate(self, *args):
        print
        print self.cpu.CPU_STATE()
        print
        print self.cpu.reg.registermap()
        print
        PC = self.cpu.reg.PC
        start = max(0, PC - 8)
        end   = min(0x10000, start + 16)
        print "  ".join("0x{:04X}".format(addr) for addr in range(start, end))
        print "-"*126
        print "  ".join(" 0x{:02X} ".format(self.cpu.membus.read(addr)) for addr in range(start, end))
        print "  ".join([ "      " for _ in range(start, PC) ] + [ "^^PC^^" ] + [ "      " for _ in range(PC+1, end) ])
        print
        HL = self.cpu.reg.HL
        start = max(0, HL - 8)
        end   = min(0x10000, start + 16)
        print "  ".join("0x{:04X}".format(addr) for addr in range(start, end))
        print "-"*126
        print "  ".join(" 0x{:02X} ".format(self.cpu.membus.read(addr)) for addr in range(start, end))
        print "  ".join([ "      " for _ in range(start, HL) ] + [ "^^HL^^" ] + [ "      " for _ in range(HL+1, end) ])
        print

    def executecommand(self, cmd):
        cmds = cmd.split(' ')
        cmd = cmds[0]
        C = None
        if cmd != "":
            for c in self.commands:
                if cmd == c[:len(cmd)]:
                    C = c
                    break
        else:
            C = ""

        if C in self.commands:
            return (self.commands[C][0](*cmds[1:]) is None)

        print "Unknown Command: {}".format(cmd)
        return True

    def mainloop(self):
        self.printstate()

        while True:
            try:
                cmd = raw_input("> ")
            except EOFError:
                cmd = 'quit'
            if not self.executecommand(cmd):
                break
            if cmd != "":
                self.commandhistory.append(cmd)
                print "command history: {!r}".format(self.commandhistory)

if __name__ == "__main__":
    from ULA import SpectrumULA
    from cpu import Z80CPU, CPUStalled
    from memorybus import MemoryBus, FileROM
    from iobus import IOBus
    import traceback
    import pkg_resources

    DATA_PATH = pkg_resources.resource_filename('pyz80', 'roms/')
    ROM_FILE = pkg_resources.resource_filename('pyz80', 'roms/48.rom')

    ula    = SpectrumULA(scale=2)
    membus = MemoryBus(mappings=[
        (0x0000, 0x4000, FileROM(ROM_FILE)),
        (0x4000, 0x1B00, ula.display)
        ])
    iobus  = IOBus([ ula.io ])

    cpu    = Z80CPU(iobus, membus)
    ula.setup_interrupts(69888, cpu.interrupt)

    debugger = Debugger(cpu, ula)

    try:
        debugger.mainloop()
    except:
        traceback.print_exc()