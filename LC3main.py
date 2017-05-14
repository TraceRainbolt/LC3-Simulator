import sys
import os
import copy
import errno
import msvcrt
import numpy as np
from storage import *
import control_unit as ctu
import instruction_parser as parser

#Initialize registers
regs = registers(np.array([0,0,0,0,0,0,0,0], dtype='int16'), 0, 0, 0)

#Initialize Memory, turn ON machine
memory = memory()
ON = True

#Useful memory locations
KBSR = 0xFE00
KBDR = 0xFE02
DSR = 0xFE04
DDR = 0xFE06
MCR = 0xFFFE

#Location of OS file
os_file_name = "operating_sys_lc3.txt"

#Main function, intializes memory and starts running isntructions
def main():
  memory.memory = memory.load_os(os_file_name, 65537)
  memory.load_instructions('instructs/test3.txt', regs)
  memory[MCR] = 0xFFFF
  run_instructions()
  regs.print_registers()
  print ''
  regs.print_spec_regs()
  #print bin(memory[KBSR])

#Handles basics for running instructions
def run_instructions():
    while ON:
        regs.PC += 1
        inst = memory[regs.PC - 1]
        regs.IR = inst
        #print to_hex_string(regs.PC - 1) + " " + to_hex_string(regs.IR) + " " + to_hex_string(regs.CC) + " " + str(regs.registers[0]) + " " + to_hex_string(regs.registers[1])
        handle_instruction(inst)
        poll_status_registers()
        #print to_hex_string(regs.PC)

#Finds instruction and tells handle to execute it
def handle_instruction(inst):
    opcode = inst >> 12
    inst_list = []
    str_op = parse_op(opcode)
    reg_state = copy.deepcopy(regs.registers)
    temp = None
    if str_op == 'ADD':
        handle_add(inst)
    elif str_op == 'NOT':
        handle_not(inst)
    elif str_op == 'AND':
        handle_and(inst)
    elif str_op == 'LD':
        handle_ld(inst)
    elif str_op == 'LDI':
        handle_ldi(inst)
    elif str_op == 'LDR':
        handle_ldr(inst)
    elif str_op == 'LEA':
        handle_lea(inst)
    elif str_op == 'ST':
        handle_st(inst)
    elif str_op == 'STI':
        handle_sti(inst)
    elif str_op == 'STR':
        handle_str(inst)
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

#Detect that a key has been pressed:
def kbfunc(): 
   x = msvcrt.kbhit()
   if x: 
      ret = ord(msvcrt.getch()) 
   else: 
      ret = None 
   return ret

#See if status registers have been updated
def poll_status_registers():
    char = kbfunc()
    if  char:
        memory[KBSR] = memory[KBSR] ^ 0x4000
        memory[KBDR] = char

def handle_DDR():
    if (DSR >> 15) & 0b1 == 1:
        print memory[DDR]

#
# HANDLERS: THe following functions handle
# their respective instructions
#
def handle_add(inst):
    inst_list = parser.parse_add(inst)
    V2 = 0
    #Check for imm
    if inst_list[3] == 0: 
        V2 = regs[inst_list[4]]
    else:
        V2 = inst_list[4]
    DR = inst_list[1]
    SR1 = regs[inst_list[2]]
    #Let fsm execute add
    inst_list_eval = [SR1, V2]
    value = ctu.execute_add(inst_list_eval)
    regs.registers[DR] = value
    regs.set_CC(value)


def handle_not(inst):
    inst_list = parser.parse_not(inst)
    DR = inst_list[1]
    SR = regs[inst_list[2]]
    value = ctu.execute_not(SR)
    regs.registers[DR] = value
    regs.set_CC(value)

def handle_and(inst):
    inst_list = parser.parse_add(inst)
    V2 = 0
    #Check for imm
    if inst_list[3] == 0: 
        V2 = regs[inst_list[4]]
    else:
        V2 = inst_list[4]
    DR = inst_list[1]
    SR1 = regs[inst_list[2]]
    #Let fsm execute add
    inst_list_eval = [SR1, V2]
    value = ctu.execute_and(inst_list_eval)
    regs.registers[DR]  = value
    regs.set_CC(value)

def handle_ld(inst):
    inst_list = parser.parse_ld(inst)
    DR = inst_list[1]
    address = regs.PC + sign_extend(inst_list[2], 16)
    value = memory[address]
    regs.registers[DR] = value
    regs.set_CC(value)
    if address == DDR:
        handle_DDR()

def handle_ldi(inst):
    inst_list = parser.parse_ldi(inst)
    DR = inst_list[1]
    address = regs.PC + sign_extend(inst_list[2], 9)
    value = memory[memory[address]]
    regs.registers[DR] = value
    regs.set_CC(value)
    if memory[address] == DDR:
        handle_DDR()

def handle_ldr(inst):
    inst_list = parser.parse_ldr(inst)
    DR = inst_list[1]
    BaseR = inst_list[2]
    address = regs.registers[BaseR] + sign_extend(inst_list[3], 6)
    value = memory[address]
    regs.registers[DR] = value
    regs.set_CC(value)
    if address == DDR:
        handle_DDR()

def handle_lea(inst):
    inst_list = parser.parse_lea(inst)
    DR = inst_list[1]
    address = regs.PC + sign_extend(inst_list[2], 9)
    regs.registers[DR] = address

def handle_st(inst):
    inst_list = parser.parse_st(inst)
    SR = inst_list[1]
    val = regs.registers[SR]
    address = regs.PC + sign_extend(inst_list[2], 9)
    memory[address] = val

def handle_sti(inst):
    inst_list = parser.parse_st(inst)
    SR = inst_list[1]
    address = regs.PC + sign_extend(inst_list[2], 9)
    memory[address] = SR

def handle_str(inst):
    inst_list = parser.parse_str(inst)
    SR = inst_list[1]
    BaseR = inst_list[2]
    address = regs.registers[BaseR] + sign_extend(inst_list[3], 6)
    memory[address] = regs.registers[SR]

def handle_br(inst):
    inst_list = parser.parse_br(inst)
    condition = '{:03b}'.format(inst_list[1])
    cc = '{:03b}'.format(regs.CC)
    address = regs.PC + sign_extend(inst_list[2], 9)
    for i, bit in enumerate(condition):
        if bit == "1" and bit == cc[i]:
            regs.PC = address

def handle_jsr(inst):
    inst_list = parser.parse_jsr(inst)
    address = 0x0000
    if inst_list[1] == 1:
        address = regs.PC + sign_extend(inst_list[2], 11)
    else:
        BaseR = inst_list[2]
        address = regs.registers[BaseR]
    regs.registers[7] = regs.PC
    regs.PC = address

def handle_ret(inst):
    inst_list = parser.parse_ret(inst)
    regs.PC = regs.registers[7]

def handle_rti(inst):
    inst_list = parser.parse_ret(inst)
    if regs.PSR >> 15 == 0:
        regs.PC = memory[regs.registers[6]]
        regs.registers[6] += 1
        temp = memory[regs.registers[6]]
        regs.registers[6] += 1
        regs.PSR = temp
        regs.CC = PSR & 0b111
    else:
        print "Priviledge mode exception."
        ON = False


def handle_trap(inst):
    global ON
    trap = parser.parse_trap(inst)[1]
    regs.PC = memory[trap]
    if trap == 0:
        ON = False
    if trap == 0x25:
        ON = False


#Sign extend, used for SEXTing offsets
def sign_extend(val, bits):
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set
        val = val - (1 << bits)        # compute negative value
    return val                         # return positive value as is

#Return opcode as string
def parse_op(opcode):
    return ['BR','ADD','LD', 'ST', 
           'JSR','AND','LDR','STR', 
           'RTI','NOT', 'LDI', 'STI',
           'RET','NOP','LEA','TRAP'][opcode]

#Used to print hex values in proper format
def to_hex_string(val):
    return 'x' + '{:04x}'.format((val + (1 << 16)) % (1 << 16)).upper()
 
if __name__ == '__main__':
    main()
 
