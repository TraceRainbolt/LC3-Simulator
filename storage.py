import numpy as np

#Register class for registers, PC, IR, and CC
class registers:
  def __init__(self, registers, PC, IR, CC):
      self.registers = registers
      self.PC = PC
      self.IR = IR
      self.CC = CC
      self.PSR = 0x8000 + self.CC

  def __getitem__(self, position):
      return self.registers[position]

  #Handles .ORIG line
  def set_origin(self, origin):
      self.PC = origin


  def print_registers(self):
      for i, register in enumerate(self.registers):
          print "R" + str(i) + ": " + to_hex_string(register)

  def print_spec_regs(self):
      print "PC: " + to_hex_string(self.PC)
      print "IR: " + to_hex_string(self.IR)
      print "CC: " + '{:03b}'.format(self.CC)

#Memory class: xFFFF memory locations, containing a singed 16 bit number
class memory:
    def __init__(self, memory=None):
        self.memory = memory

    def __getitem__(self, position):
        return self.memory[position]

    def __setitem__(self, position, item):
        self.memory[position] = item

    def load_instructions(self, fname, regs):
        first = True
        orig = 0x0000
        with open(fname) as f:
            orig = int("".join(f.readline()), 2)
            for i, line in enumerate(f):
                self.memory[i + orig] = int(line, 2)
                i += 1
        regs.set_origin(orig)

    #Loads LC3 Operating System from text file
    def load_os(self, fname, nrow):
        x = np.empty(nrow, dtype='int16')
        with open(fname) as f:
            for irow, line in enumerate(f):
                x[irow] = int(line, 2)
        return x

#Used for properly formatting/printing hex numbers
def to_hex_string(val):
    return 'x' + '{:04x}'.format((val + (1 << 16)) % (1 << 16)).upper()