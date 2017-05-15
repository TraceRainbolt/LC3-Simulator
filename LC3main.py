import sys
import os
import copy
from threading import Thread
from time import sleep
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
KBSR = -512 #xFE00
KBDR = -510 #xFE02
DSR = -508  #xFE04
DDR = -506  #xFE06
MCR = -2  #xFFFE

#Location of OS file
os_file_name = "operating_sys_lc3.txt"

#Main function, intializes memory and starts running isntructions
def main():
  memory.memory = memory.load_os(os_file_name, 65536)
  memory.load_instructions('instructs/test3.txt', regs)
  memory[MCR] = 0xFFFF
  run_instructions()
  print ''
  regs.print_registers()
  print ''
  regs.print_spec_regs()
  #print bin(memory[KBSR])

#Handles basics for running instructions
def run_instructions():
    cycle = 0
    while (memory[MCR] >> 15) & 0b1 == 1:
        regs.PC += 1
        inst = memory[regs.PC - 1]
        regs.IR = inst
        #print to_hex_string(regs.PC - 1) + " " + to_hex_string(regs.IR) + " " + to_hex_string(regs.CC) + " " + to_hex_string(regs.registers[1])
        handle_instruction(inst)
        if ON == False:
            if regs.PC == sign_extend(0xFD79, 16):
                memory[MCR] = 0x7FFF

        #poll_status_registers()
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
    if char:
        memory[KBSR] = memory[KBSR] + 0x8000
        if char == 0x0D:
            char = 0x0A
        memory[KBDR] = char
        return True
    return False

#For future use (when threads are added)
def update_keyboard():
    while ON:
        poll_status_registers()

#Handle the Dispaly Data Register, called when updated
def handle_DDR():
    if (memory[DSR] >> 15) & 0b1 == 1:
        if memory[DDR] in range(256):
            sys.stdout.write(chr(memory[DDR]))

#Handle the Keyboard Status Register, called when updated
def handle_KBSR():
    if (memory[KBSR] >> 15) & 1 == 1:
        memory[KBSR] = memory[KBSR] & 0x4000  #Reset KBSR
    poll_status_registers()
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
        V2 = sign_extend(inst_list[4], 5)
    DR = inst_list[1]
    SR1 = regs[inst_list[2]]
    #Let fsm execute add
    inst_list_eval = [SR1, V2]
    value = ctu.execute_add(inst_list_eval)
    n = regs.registers[3]
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
        V2 = sign_extend(inst_list[4], 5)
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
    regs.set_CC(value)
    if address == KBSR:
        handle_KBSR()
    regs.registers[DR] = value

def handle_ldi(inst):
    inst_list = parser.parse_ldi(inst)
    DR = inst_list[1]
    address = regs.PC + sign_extend(inst_list[2], 9)
    value = memory[memory[address]]
    regs.set_CC(value)
    if memory[address] == KBSR:
        handle_KBSR()
    regs.registers[DR] = value

def handle_ldr(inst):
    inst_list = parser.parse_ldr(inst)
    DR = inst_list[1]
    BaseR = inst_list[2]
    address = regs.registers[BaseR] + sign_extend(inst_list[3], 6)
    value = memory[address]
    if address == KBSR:
        handle_KBSR()
    regs.registers[DR] = value
    regs.set_CC(value)

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
    if val == DDR:
        handle_DDR()

def handle_sti(inst):
    inst_list = parser.parse_st(inst)
    SR = inst_list[1]
    address = regs.PC + sign_extend(inst_list[2], 9)
    memory[memory[address]] = regs.registers[SR]
    if memory[address] == DDR:
        handle_DDR()

def handle_str(inst):
    inst_list = parser.parse_str(inst)
    SR = inst_list[1]
    BaseR = inst_list[2]
    address = regs.registers[BaseR] + sign_extend(inst_list[3], 6)
    memory[address] = regs.registers[SR]
    if regs.registers[SR] == DDR:
        handle_DDR()

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
        ON = False1


def handle_trap(inst):
    global ON
    regs.registers[7] = regs.PC
    trap = parser.parse_trap(inst)[1]
    regs.PC = memory[trap]
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
    #thread_main = Thread(target = main)
    # thread_keyb = Thread(target = update_keyboard)
    '''thread_main.daemon = True
    thread_keyb.daemon = True
    thread_main.start()
    thread_keyb.start()
    thread_main.join()
    thread_keyb.join()'''
 
