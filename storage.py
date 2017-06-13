import numpy as np
import binascii as ba
from queue import *

nrow = 65536


# Register class for registers, PC, IR, and CC
class Registers(object):
    def __init__(self, registers, PC, IR, CC):
        self.registers = registers
        self.PC = PC
        self.IR = IR
        self.CC = CC
        self.PSR = 0x8000 + self.CC

    def __getitem__(self, position):
        return self.registers[position]

    def __setitem__(self, position, item):
        self.registers[position] = item

    # Handles .ORIG line
    def set_origin(self, origin):
        self.PC = origin

    def set_CC(self, value):
        if value < 0:
            self.CC = 0b100
        elif value == 0:
            self.CC = 0b010
        elif value > 0:
            self.CC = 0b001
        else:
            print "Invalid CC state entered."
        self.PSR = (self.PSR & 0xFFF8) + self.CC

    def print_registers(self):
        for i, register in enumerate(self.registers):
            print "R" + str(i) + ": " + to_hex_string(register)

    def print_spec_regs(self):
        print "PC: " + to_hex_string(self.PC)
        print "IR: " + to_hex_string(self.IR)
        print "PSR:" + to_hex_string(self.PSR)
        print "CC: " + '{:03b}'.format(self.CC)


# Memory class: 0xFFFF memory locations, containing a singed 16 bit number
class Memory(object):
    def __init__(self, mem=np.empty(nrow, dtype='int16')):
        self.memory = mem
        self.paused = False
        self.modified_data = []
        self.breakpoints = []
        self.instructions_ran = 0
        self.key_queue = Queue(maxsize=100)
        self.stepping_over = False

    def __getitem__(self, position):
        return self.memory[position]

    def __setitem__(self, position, item):
        self.memory[position] = item

    def load_instructions(self, fname):
        inst_list = parse_obj(fname)
        orig = int(inst_list.pop(0), 2)
        total = 0
        for i, inst in enumerate(inst_list):
            self.memory[sign_extend(orig, 16) + i] = int(inst, 2)
            total += 1
        registers.set_origin(orig)
        return orig, orig + total  # Return interval that was modified

    # Loads LC3 Operating System from text file
    def load_os(self):
        self.breakpoints = []
        fname = "LC3_OS.bin"
        with open(fname) as f:
            for irow, line in enumerate(f):
                inst = int(line, 2)
                if self.memory[irow] & 0xFFFF != inst:
                    self.modified_data.append(irow)
                    self[irow] = inst

    def reset_modified(self):
        self.modified_data = []


# Parse .obj files
def parse_obj(fname):
    chars = []
    with open(fname, "rb") as f:
        for line in f:
            for char in line:
                chars.append('{:08b}'.format(int(ba.hexlify(char), 16)))
    combined_chars = []
    j = 0
    while j + 1 < len(chars):
        char1 = chars[j]
        char2 = chars[j + 1]
        combined_chars.append(char1 + char2)
        j += 2
    return combined_chars

# Create an instance (singleton) of the memory and the registers
memory = Memory()
registers = Registers(np.array([0, 0, 0, 0, 0, 0, 0, 0], dtype='int16'), 0, 0, 0)

# Used for properly formatting/printing hex numbers
def to_hex_string(val):
    return 'x' + '{:04x}'.format((val + (1 << 16)) % (1 << 16)).upper()

# Sign extend, used for SEXTing offsets
def sign_extend(val, bits):
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set
        val = val - (1 << bits)  # compute negative value
    return val  # return positive value as is
