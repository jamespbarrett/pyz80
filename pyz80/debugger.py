from .machinestates import *

class Debugger(object):
    def __init__(self, cpu, *args):
        self.cpu = cpu
        self.components = args
        self.commandhistory = []
        self.breakpoints = []
        self.watchpoints = []

        self.commands = {
            "quit" : [ self.quit, "exit the debugger"],
            "help" : [ self.help, "print this message"],
            "list" : [ self.printstate, "print the state of the cpu and memory" ],
            "print" : [ self._print, "print a register value or location in memory" ],
            "next"  : [ self.__next__, "advance to next instruction (or more if argument provided)" ],
            "breakpoint" : [ self._break, "Set a breakpoint at given address" ],
            "deletebreakpoint" : [ self.deletebreakpoint, "Remove a breakpoint" ],
            "showbreakpoints" : [ self.showbreakpoints, "Show all breakpoints" ],
            "continue"        : [ self._continue, "Run until a breakpoint is hit or an exception thrown" ],
            "" : [self.dolastthing, None],
            "stack" : [ self.printstack, "Print the stack" ],
            "watchpoint" : [ self.watch, "Watch the value in a register for changes" ],
            "deletewatchpoint" : [ self.deletewatchpoint, "Remove a watchpoint" ],
            "showwatchpoints" : [ self.showatchpoints, "Show all watchpoints" ],
            "disassemble" : [ self.disassemble, "disassemble instructions near the current PC" ],
        }

    def disassemble(self, *args):
        PC = self.cpu.reg.PC
        found = False
        for baddr in range(PC-8, PC+1):
            start = max(0, baddr)
            end   = min(0x10000, start + 16)
            instructions = [ self.cpu.membus.read(addr) for addr in range(start, end) ]
            disassembly = disassemble_instructions(instructions)

            pc = start
            for (c,l) in disassembly:
                if pc == PC:
                    found = True
                    break
                pc += l
            if found:
                break

        i = 0
        for d in range(0, len(disassembly)):
            print((">> " if start + i == PC else "   ") + "0x{:04X}:  0x{:02X}  -- {}".format(start + i, instructions[i], disassembly[d][0]))
            i += 1
            for n in range(1,disassembly[d][1]):
                if i < len(instructions):
                    print("   0x{:04X}:  0x{:02X}".format(start + i, instructions[i]))
                    i += 1

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
            print("Need an address to set break point at")
            return

        try:
            addr = self.decode_address(args[0])
        except:
            print("Bad argument: <{}>".format(args[0]))

        self.breakpoints.append(addr)
        print("Set breakpoint <{}> at 0x{:04X}".format(len(self.breakpoints)-1, addr))

    def deletebreakpoint(self, *args):
        if len(args) == 0:
            n = len(self.breakpoints) - 1
        else:
            try:
                n = int(args[0])
            except:
                print("Bad argument: <{}>".format(args[0]))

        if n >= 0 and n < len(self.breakpoints):
            self.breakpoints[n] = None

    def watch(self, *args):
        if len(args) == 0:
            print("Need a register to watch")
            return

        if args[0] not in [ "AF", "BC", "DE", "HL", "SP", "PC", "IX", "IY",  "A", "F", "B", "C", "D", "E", "H", "L", "SPH", "SPL", "PCH", "PCL", "IXH", "IXL", "IYH", "IYL", "I", "R" ]:
            print("Bad register: <{}>".format(args[0]))
            return

        self.watchpoints.append(args[0])

    def deletewatchpoint(self, *args):
        if len(args) == 0:
            print("Need a register to stop watching")
            return

        if len(args) == 0 and len(self.watchpoints) > 0:
            del self.watchpoints[-1]
        else:
            try:
                self.watchpoints.remove(args[0])
            except:
                print("{} is not a register being watched".format(args[0]))
                return

    def help(self, *args):
        print("Commands:")
        for cmd in self.commands:
            if self.commands[cmd][1] is not None:
                print("{} -- {}".format(cmd, self.commands[cmd][1]))
        print()

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
                print("Invalid argument: <{}>".format(arg[0]))
                return
        else:
            n = 1

        watchvals = {}
        for reg in self.watchpoints:
            watchvals[reg] = getattr(self.cpu.reg, reg)

        for _ in range(0,n):
            while self.cpu.clock() != 0:
                for comp in self.components:
                    comp.clock()

            stop = False
            x = 0
            for bp in self.breakpoints:
                if self.cpu.reg.PC == bp:
                    print("Hit breakpoint <{:02d}>".format(x))
                    stop = True
                x += 1

            for reg in watchvals:
                if watchvals[reg] != getattr(self.cpu.reg, reg):
                    print("Watched value changed: {} from 0x{:02X} to 0x{:02X}".format(reg, watchvals[reg], getattr(self.cpu.reg, reg)))
                    stop = True

            if stop:
                print()
                self.printstate()
                return

        self.printstate()

    def _continue(self, *args):
        watchvals = {}
        for reg in self.watchpoints:
            watchvals[reg] = getattr(self.cpu.reg, reg)

        while True:
            try:
                while self.cpu.clock() != 0:
                    for comp in self.components:
                        comp.clock()
            except:
                traceback.print_exc()
                print()
                self.printstate()
                return

            stop = False
            n = 0
            for bp in self.breakpoints:
                if self.cpu.reg.PC == bp:
                    print("Hit breakpoint <{:02d}>".format(n))
                    stop = True
                n += 1

            for reg in watchvals:
                if watchvals[reg] != getattr(self.cpu.reg, reg):
                    print("Watched value changed: {} from 0x{:02X} to 0x{:02X}".format(reg, watchvals[reg], getattr(self.cpu.reg, reg)))
                    stop = True

            if stop:
                print()
                self.printstate()
                return

    def _print(self, *args):
        for arg in args:
            try:
                if arg in ["AF", "BC", "DE", "HL", "SP", "PC", "IX", "IY"]:
                    print(" {} = 0x{:04x}".format(arg, getattr(self.cpu.reg, arg)))
                elif arg in [ "A", "F", "B", "C", "D", "E", "H", "L", "SPH", "SPL", "PCH", "PCL", "IXH", "IXL", "IYH", "IYL", "I", "R" ]:
                    print(" {} = 0x{:04x}".format(arg, getattr(self.cpu.reg, arg)))
                elif arg[0] == "(" and arg[-1] == ")":
                    a = self.decode_address(arg[1:len(arg)-1])
                    print(" {} = 0x{:02x}".format(arg, self.cpu.membus.read(a)))
            except:
                print("Bad argument: <{}>".format(arg))

    def showbreakpoints(self, *args):
        n = 0
        for PC in self.breakpoints:
            if PC is not None:
                start = max(0, PC - 8)
                end   = min(0x10000, start + 16)
                print("  ".join("0x{:04X}".format(addr) for addr in range(start, end)))
                print("-"*126)
                print("  ".join(" 0x{:02X} ".format(self.cpu.membus.read(addr)) for addr in range(start, end)))
                print("  ".join([ "      " for _ in range(start, PC) ] + [ "^<{:02d}>^".format(n) ] + [ "      " for _ in range(PC+1, end) ]))
                print()
            n += 1

    def showatchpoints(self, *args):
        print(", ".join(self.watchpoints))

    def printstate(self, *args):
        print()
        print(self.cpu.CPU_STATE())
        print()
        print(self.cpu.reg.registermap())
        print()
        HL = self.cpu.reg.HL
        start = max(0, HL - 8)
        end   = min(0x10000, start + 16)
        print("  ".join("0x{:04X}".format(addr) for addr in range(start, end)))
        print("-"*126)
        print("  ".join(" 0x{:02X} ".format(self.cpu.membus.read(addr)) for addr in range(start, end)))
        print("  ".join([ "      " for _ in range(start, HL) ] + [ "^^HL^^" ] + [ "      " for _ in range(HL+1, end) ]))
        print()
        self.printstack(*args)
        print()
        self.disassemble(*args)

    def printstack(self, *args):
        print("Stack")
        print("-----")
        for n in range(0,8):
            addr = self.cpu.reg.SP + 2*n
            if addr <= 0xFFFE:
                print("0x{:04x}".format(self.cpu.membus.read(addr) + (self.cpu.membus.read(addr + 1) << 8)))
        print()

    def executecommand(self, cmd):
        cmds = cmd.split(' ')
        cmd = cmds[0]
        C = []
        if cmd != "":
            for c in self.commands:
                if cmd == c[:len(cmd)]:
                    C.append(c)
            if len(C) == 0:
                print("Unknown Command: {}".format(cmd))
                return True
            elif len(C) == 1:
                C = C[0]
            else:
                print("Ambiguous Command, could be any of: {}".format(', '.join(C)))
                return True
        
        else:
            C = ""

        if C in self.commands:
            return (self.commands[C][0](*cmds[1:]) is None)

        print("Unknown Command: {}".format(cmd))
        return True

    def mainloop(self):
        self.printstate()

        while True:
            try:
                cmd = input("> ")
            except EOFError:
                cmd = 'quit'
            if not self.executecommand(cmd):
                break
            if cmd != "":
                self.commandhistory.append(cmd)

if __name__ == "__main__":
    from .ULA import SpectrumULA
    from .cpu import Z80CPU, CPUStalled
    from .memorybus import MemoryBus, FileROM
    from .iobus import IOBus
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
