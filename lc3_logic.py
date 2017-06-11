import sys

import time
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

import alu
import instruction_parser as parser
from storage import *
import lc3_gui
import lc3_gui

# Turn ON machine
ON = True

# Useful memory locations
KBSR = -512  # 0xFE00
KBDR = -510  # 0xFE02
DSR = -508  # 0xFE04
DDR = -506  # 0xFE06
MCR = -2  # 0xFFFE

bit_mask = 0xFFFF

# Location of OS file
os_file_name = "LC3_OS.bin"


# Main function, initializes memory and starts running instructions
def main():
    memory.load_os()
    memory.reset_modified()
    memory[MCR] = 0x7FFF
    memory[KBSR] = 0x4000
    create_UI()


def create_UI():
    app = QtGui.QApplication(sys.argv)
    app.setStyle("plastique")
    GUI = lc3_gui.Window()
    GUI.show()
    sys.exit(app.exec_())


# Updates the register table to display to the UI
def update_gui_registers(console):
    QtCore.QMetaObject.invokeMethod(console, 'send_update_gui_tables', Qt.DirectConnection)


# Handles basics for running instructions
def run_instructions(console):
    while (memory[MCR] >> 15) & 0b1 == 1:
        registers.PC += 1
        inst = memory[registers.PC - 1]
        registers.IR = inst
        handle_instruction(inst, console)
        if not ON and registers.PC == sign_extend(0xFD79, 16):
            memory[MCR] = 0x7FFF
            break
        if (registers.PC & 0xFFFF) in memory.breakpoints:
            memory.breakpoints.remove((registers.PC & 0xFFFF))
            break
        if memory.paused:
            break
    memory.paused = False
    update_gui_registers(console)
    QtCore.QMetaObject.invokeMethod(console, 'emit_done', Qt.DirectConnection)


# Same as run instruction, but once
def step_instruction(console):
    if (memory[MCR] >> 15) & 0b1 == 1:
        registers.PC += 1
        inst = memory[registers.PC - 1]
        registers.IR = inst
        handle_instruction(inst, console)
        if not ON and registers.PC == sign_extend(0xFD79, 16):
            memory[MCR] = 0x7FFF
        update_gui_registers(console)


# Finds instruction and tells handle to execute it
def handle_instruction(inst, console):
    opcode = inst >> 12
    str_op = parser.parse_op(opcode)
    if str_op == 'ADD':
        handle_add(inst)
    elif str_op == 'NOT':
        handle_not(inst)
    elif str_op == 'AND':
        handle_and(inst)
    elif str_op == 'LD':
        handle_ld(inst, console)
    elif str_op == 'LDI':
        handle_ldi(inst, console)
    elif str_op == 'LDR':
        handle_ldr(inst, console)
    elif str_op == 'LEA':
        handle_lea(inst)
    elif str_op == 'ST':
        handle_st(inst, console)
    elif str_op == 'STI':
        handle_sti(inst, console)
    elif str_op == 'STR':
        handle_str(inst, console)
    elif str_op == 'BR':
        handle_br(inst)
    elif str_op == 'JSR':
        handle_jsr(inst)
    elif str_op == 'RET':
        handle_ret(inst)
    elif str_op == 'RTI':
        handle_rti(inst)
    elif str_op == 'TRAP':
        handle_trap(inst)


# Handle the Display Data Register, called when updated
def handle_DDR(console):
    if (memory[DSR] >> 15) & 0b1 == 1:
        if memory[DDR] in range(256):
            QtCore.QMetaObject.invokeMethod(console, 'send_append_text', Qt.DirectConnection,
                                            QtCore.Q_ARG(str, str(chr(memory[DDR]))))


# Handle the Keyboard Status Register, called when updated
def handle_KBSR(console):
    if (memory[KBSR] >> 15) & 1 == 1:
        memory[KBSR] = memory[KBSR] & 0x4000  # Reset KBSR
        handle_update_gui_memory(console, KBSR)


def handle_update_gui_memory(console, changed):
    QtCore.QMetaObject.invokeMethod(console, 'send_update_gui_memory', Qt.DirectConnection,
                                    QtCore.Q_ARG(int, changed))

#
# HANDLERS: THe following functions handle
# their respective instructions
#
def handle_add(inst):
    inst_list = parser.parse_add(inst)
    V2 = 0
    # Check for imm
    if inst_list[3] == 0:
        V2 = registers[inst_list[4]]
    else:
        V2 = sign_extend(inst_list[4], 5)
    DR = inst_list[1]
    SR1 = registers[inst_list[2]]
    # Let fsm execute add
    inst_list_eval = [SR1, V2]
    value = alu.execute_add(inst_list_eval)
    registers.registers[DR] = value
    registers.set_CC(value)


def handle_not(inst):
    inst_list = parser.parse_not(inst)
    DR = inst_list[1]
    SR = registers[inst_list[2]]
    value = alu.execute_not(SR)
    registers.registers[DR] = value
    registers.set_CC(value)


def handle_and(inst):
    inst_list = parser.parse_add(inst)
    V2 = 0
    # Check for imm
    if inst_list[3] == 0:
        V2 = registers[inst_list[4]]
    else:
        V2 = sign_extend(inst_list[4], 5)
    DR = inst_list[1]
    SR1 = registers[inst_list[2]]
    # Let alu execute add
    inst_list_eval = [SR1, V2]
    value = alu.execute_and(inst_list_eval)
    registers.registers[DR] = value
    registers.set_CC(value)


def handle_ld(inst, console):
    inst_list = parser.parse_ld(inst)
    DR = inst_list[1]
    address = registers.PC + sign_extend(inst_list[2], 9)
    value = memory[address]
    registers.set_CC(value)
    if address == KBSR:
        handle_KBSR(console)
    registers.registers[DR] = value


def handle_ldi(inst, console):
    inst_list = parser.parse_ldi(inst)
    DR = inst_list[1]
    address = registers.PC + sign_extend(inst_list[2], 9)
    value = memory[memory[address]]
    registers.set_CC(value)
    if memory[address] == KBSR:
        handle_KBSR(console)
    registers.registers[DR] = value


def handle_ldr(inst, console):
    inst_list = parser.parse_ldr(inst)
    DR = inst_list[1]
    BaseR = inst_list[2]
    address = registers.registers[BaseR] + sign_extend(inst_list[3], 6)
    value = memory[address]
    if address == KBSR:
        handle_KBSR(console)
    registers.registers[DR] = value
    registers.set_CC(value)


def handle_lea(inst):
    inst_list = parser.parse_lea(inst)
    DR = inst_list[1]
    address = registers.PC + sign_extend(inst_list[2], 9)
    registers.registers[DR] = address


def handle_st(inst, console):
    inst_list = parser.parse_st(inst)
    SR = inst_list[1]
    val = registers.registers[SR]
    address = registers.PC + sign_extend(inst_list[2], 9)
    memory[address] = val
    if val == DDR:
        handle_DDR(console)
    changed = address
    handle_update_gui_memory(console, changed)


def handle_sti(inst, console):
    inst_list = parser.parse_st(inst)
    SR = inst_list[1]
    address = registers.PC + sign_extend(inst_list[2], 9)
    sti_addr = memory[address]
    val = registers.registers[SR]
    memory[sti_addr] = val
    if memory[address] == DDR:
        handle_DDR(console)
    changed = sti_addr & bit_mask
    handle_update_gui_memory(console, changed)


def handle_str(inst, console):
    inst_list = parser.parse_str(inst)
    SR = inst_list[1]
    BaseR = inst_list[2]
    address = registers.registers[BaseR] + sign_extend(inst_list[3], 6)
    val = registers.registers[SR]
    memory[address] = val
    if registers.registers[SR] == DDR:
        handle_DDR(console)
    changed = address
    handle_update_gui_memory(console, changed)


def handle_br(inst):
    inst_list = parser.parse_br(inst)
    condition = '{:03b}'.format(inst_list[1])
    cc = '{:03b}'.format(registers.CC)
    address = registers.PC + sign_extend(inst_list[2], 9)
    for i, bit in enumerate(condition):
        if bit == "1" and bit == cc[i]:
            registers.PC = address


def handle_jsr(inst):
    inst_list = parser.parse_jsr(inst)
    if inst_list[1] == 1:  # JSR
        address = registers.PC + sign_extend(inst_list[2], 11)
    else:  # JSRR
        BaseR = inst_list[2]
        address = registers.registers[BaseR]
    registers.registers[7] = registers.PC
    registers.PC = address


def handle_ret(inst):
    inst_list = parser.parse_ret(inst)
    BaseR = inst_list[1]
    registers.PC = registers.registers[BaseR]


def handle_rti(inst):
    if registers.PSR >> 15 == 0:
        registers.PC = memory[registers.registers[6]]
        registers.registers[6] += 1
        temp = memory[registers.registers[6]]
        registers.registers[6] += 1
        registers.PSR = temp
        registers.CC = registers.PSR & 0b111
    else:
        print "Privilege mode exception."


def handle_trap(inst):
    global ON
    registers.registers[7] = registers.PC
    trap = parser.parse_trap(inst)[1]
    registers.PC = memory[trap]
    if trap == 0x25:
        ON = False


# Sign extend, used for SEXTing offsets
def sign_extend(val, bits):
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set
        val = val - (1 << bits)  # compute negative value
    return val  # return positive value as is


# Used to print hex values in proper format
def to_hex_string(val):
    return 'x' + '{:04x}'.format((val + (1 << 16)) % (1 << 16)).upper()


# Used to print bin values in proper format
def to_bin_string(val):
    return '{:016b}'.format((val + (1 << 16)) % (1 << 16))


if __name__ == '__main__':
    main()
