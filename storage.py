import numpy as np
import binascii as ba

# Register class for registers, PC, IR, and CC
class registers:
    def __init__(self, registers, PC, IR, CC):
        self.registers = registers
        self.PC = PC
        self.IR = IR
        self.CC = CC
        self.PSR = 0x8000 + self.CC

    def __getitem__(self, position):
        return self.registers[position]

    # Handles .ORIG line
    def set_origin(self, origin):
        self.PC = origin

    def set_CC(self, value):
        self.PSR = 0x8000 + self.CC
        if value < 0:
            self.CC = 0b100
        elif value == 0:
            self.CC = 0b010
        elif value > 0:
            self.CC = 0b001
        else:
            print "Invalid CC state entered."

    def print_registers(self):
        for i, register in enumerate(self.registers):
            print "R" + str(i) + ": " + to_hex_string(register)

    def print_spec_regs(self):
        print "PC: " + to_hex_string(self.PC)
        print "IR: " + to_hex_string(self.IR)
        print "PSR:" + to_hex_string(self.PSR)
        print "CC: " + '{:03b}'.format(self.CC)


# Memory class: xFFFF memory locations, containing a singed 16 bit number
class memory:
    def __init__(self, memory=None):
        self.memory = memory

    def __getitem__(self, position):
        return self.memory[position]

    def __setitem__(self, position, item):
        self.memory[position] = item

    def load_instructions(self, fname, regs):
        inst_list = parse_obj(fname)
        orig = int(inst_list.pop(0), 2)
        for i, inst in enumerate(inst_list):
            self.memory[sign_extend(orig, 16) + i] = int(inst, 2)
            i += 1
        regs.set_origin(orig)

    # Loads LC3 Operating System from text file
    def load_os(self, fname, nrow):
        x = np.empty(nrow, dtype='int16')
        with open(fname) as f:
            for irow, line in enumerate(f):
                x[irow] = int(line, 2)
        return x


def parse_obj(fname):
    chars = []
    with open(fname) as f:
        for line in f:
            for char in line:
                chars.append('{:08b}'.format(int(ba.hexlify(char), 16)))
    combined_chars = []
    j = 0
    for i in range(len(chars)):
        if j + 1 < len(chars):
            char1 = chars[j]
            char2 = chars[j + 1]
            combined_chars.append(char1 + char2)
        j += 2
    return combined_chars


# Used for properly formatting/printing hex numbers
def to_hex_string(val):
    return 'x' + '{:04x}'.format((val + (1 << 16)) % (1 << 16)).upper()


# Sign extend, used for SEXTing offsets
def sign_extend(val, bits):
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set
        val = val - (1 << bits)  # compute negative value
    return val  # return positive value as is
