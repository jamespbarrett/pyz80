A simple emulator for the Zilog Z80 CPU writtern in pure python, with some ability to mimic the ZX Spectrum 48K.

There are two methods of invoking:

> python3 -m pyz80

will launch a graphical window containing the spectrum display and load up the 48K spectrum OS ROM then start running.

Currently it progresses as far as the copyright screen and then appears to hang not accepting keyboard input.



> python3 -m pyz80.debugger

will launch a graphical windows containing the spectrum display and load up the 48K spectrum OS ROM and then present an interactive
debugger on the terminal from which it is invoked. The commands on this debugger are fairly standard (and listable with "help") and it
supports break-points, watch-points (for registers), printing of arbitrary registers and memory locations, and stepping through instruction
by instruction with disassembled code annotated next to the instructions. 

NB. Whilst the disassembly of the current PC location and future locations shown will be correct it is possible sometimes for the 
debugger to incorrectly disassemble the preceeding instructions if there is some ambiguity in them. Use with caution.



In writing this emulator I have made extensive use of the documentation in the Z80 CPU manual, and at the sites:

<http://www.z80.info/>

and 

<http://z80-heaven.wikidot.com/>

as well as the Complete Spectrum ROM Disassembly by Dr Ian Logan & Dr Frank O’Hara
