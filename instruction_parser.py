#
# This file takes an instruction and returns
# a list of the separated parts
#

def parse_any(inst):
    opcode = inst >> 12
    str_op = parse_op(opcode)
    ret = []
    if str_op == 'ADD':
        ret = parse_add(inst)
        ret[1] = 'R' + str(ret[1])
        ret[2] = 'R' + str(ret[2])
        if ret.pop(3) == 1:  # Immediate value
            ret[3] = '#' + str(ret[3])
        else:
            ret[3]= 'R' + str(ret[3])
    elif str_op == 'NOT':
        ret = parse_not(inst)
        ret[1] = 'R' + str(ret[1])
        ret[2] = 'R' + str(ret[2])
    elif str_op == 'AND':
        ret = parse_and(inst)
        ret[1] = 'R' + str(ret[1])
        ret[2] = 'R' + str(ret[2])
        if ret.pop(3) == 1:  # Immediate value
            ret[3] = '#' + str(ret[3])
        else:
            ret[3]= 'R' + str(ret[3])
    elif str_op == 'LD':
        ret = parse_ld(inst)
        ret[1] = 'R' + str(ret[1])
    elif str_op == 'LDI':
        ret = parse_ldi(inst)
        ret[1] = 'R' + str(ret[1])
    elif str_op == 'LDR':
        ret = parse_ldr(inst)
        ret[1] = 'R' + str(ret[1])
        ret[2] = 'R' + str(ret[2])
        ret[3] = '#' + str(ret[3])
    elif str_op == 'LEA':
        ret = parse_lea(inst)
        ret[1] = 'R' + str(ret[1])
    elif str_op == 'ST':
        ret = parse_st(inst)
        ret[1] = 'R' + str(ret[1])
    elif str_op == 'STI':
        ret = parse_sti(inst)
        ret[1] = 'R' + str(ret[1])
    elif str_op == 'STR':
        ret = parse_str(inst)
        ret[1] = 'R' + str(ret[1])
        ret[2] = 'R' + str(ret[2])
        ret[3] = '#' + str(ret[3])
    elif str_op == 'BR':
        ret = parse_br(inst)
        if ret[1] == 0 and ret[2] == 0:
            return ['NOP']
        val = ret.pop(1)
        cc = '{:03b}'.format(val)
        if val == 0 and inst in range(256):
            ret = ['    ' + chr(inst) + '       #' + str(inst)]
            return ret
        for i, n in enumerate(cc):
            if n == '1':
                if i == 0:
                    ret[0] += 'n'
                elif i == 1:
                    ret[0] += 'z'
                elif i == 2:
                    ret[0] += 'p'
    elif str_op == 'JSR':
        ret = parse_jsr(inst)
        val = ret.pop(1)
        if val == 0:
            ret[1] = 'R' + str(ret[1])
    elif str_op == 'RET':
        ret = parse_ret(inst)
        if ret[1] == 7:
            return ['RET']
        ret[1] = 'R' + str(ret[1])
    elif str_op == 'RTI':
        ret = parse_rti(inst)
    elif str_op == 'TRAP':
        ret = parse_trap(inst)
        ret[1] = hex(ret[1])[1:]
    return ret

def parse_add(inst):
    DR = get_DR(inst)
    SR1 = get_SR(inst)
    if is_imm(inst):
        imm_val = get_imm(inst)
        return ['ADD', DR, SR1, 1, imm_val]
    else:
        SR2 = get_SR2(inst)
        return ['ADD', DR, SR1, 0, SR2]


def parse_not(inst):
    DR = get_DR(inst)
    SR = get_SR(inst)
    return ['NOT', DR, SR]


def parse_and(inst):
    DR = get_DR(inst)
    SR1 = get_SR(inst)
    if is_imm(inst):
        imm_val = get_imm(inst)
        return ['AND', DR, SR1, 1, imm_val]
    else:
        SR2 = get_SR2(inst)
        return ['AND', DR, SR1, 0, SR2]


def parse_ld(inst):
    DR = get_DR(inst)
    offset = get_9offset(inst)
    return ['LD', DR, offset]


def parse_ldi(inst):
    DR = get_DR(inst)
    offset = get_9offset(inst)
    return ['LDI', DR, offset]


def parse_ldr(inst):
    DR = get_DR(inst)
    BaseR = get_SR(inst)
    offset = get_6offset(inst)
    return ['LDR', DR, BaseR, offset]


def parse_lea(inst):
    DR = get_DR(inst)
    offset = get_9offset(inst)
    return ['LEA', DR, offset]


def parse_st(inst):
    DR = get_DR(inst)
    offset = get_9offset(inst)
    return ['ST', DR, offset]


def parse_sti(inst):
    DR = get_DR(inst)
    offset = get_9offset(inst)
    return ['STI', DR, offset]


def parse_str(inst):
    DR = get_DR(inst)
    BaseR = get_SR(inst)
    offset = get_6offset(inst)
    return ['STR', DR, BaseR, offset]


def parse_br(inst):
    condition = get_DR(inst)
    offset = get_9offset(inst)
    return ['BR', condition, offset]


def parse_jump(inst):
    return ['JMP', get_SR(inst)]


def parse_jsr(inst):
    if get_bit_11(inst) == 1:
        return ['JSR', 1, get_11offset(inst)]
    else:
        return ['JSRR', 0, get_SR(inst)]


def parse_ret(inst):
    DR = get_SR(inst)
    return ['RET', DR]


def parse_rti(inst):
    return ['RTI']


def parse_trap(inst):
    trap_vec = get_trap_vec(inst)
    return ['TRAP', trap_vec]

#
# Helper functions for parsing instructions
#

def get_DR(inst):
    return (inst >> 9) & 0b111


def get_SR(inst):
    return (inst >> 6) & 0b111


def get_imm(inst):
    return inst & 0b11111


def get_SR2(inst):
    return inst & 0b111


def get_trap_vec(inst):
    return inst & 0b11111111


def get_6offset(inst):
    return inst & 0b111111


def get_9offset(inst):
    return inst & 0b111111111


def get_11offset(inst):
    return inst & 0b11111111111


def get_bit_11(inst):
    return (inst >> 11) & 1


def is_imm(inst):
    return (inst >> 5) & 0b1 == 1


def parse_op(opcode):
    return ['BR', 'ADD', 'LD', 'ST',
            'JSR', 'AND', 'LDR', 'STR',
            'RTI', 'NOT', 'LDI', 'STI',
            'RET', 'NOP', 'LEA', 'TRAP'][opcode]