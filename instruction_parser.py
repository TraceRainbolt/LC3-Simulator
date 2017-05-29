#
# This file takes an instruction and returns
# a list of the separated parts
#

def parse_any(inst):
    opcode = inst >> 12

    str_op = parse_op(opcode)

    if str_op == 'ADD':
        return parse_add(inst)
    elif str_op == 'NOT':
        return parse_not(inst)
    elif str_op == 'AND':
        return parse_and(inst)
    elif str_op == 'LD':
        return parse_ld(inst)
    elif str_op == 'LDI':
        return parse_ldi(inst)
    elif str_op == 'LDR':
        return parse_ldr(inst)
    elif str_op == 'LEA':
        return parse_lea(inst)
    elif str_op == 'ST':
        return parse_st(inst)
    elif str_op == 'STI':
        return parse_sti(inst)
    elif str_op == 'STR':
        return parse_str(inst)
    elif str_op == 'BR':
        ret = parse_br(inst)
        if ret[1] == 0 and ret[2] == 0:
            return 'NOP'
        return ret
    elif str_op == 'JSR':
        return parse_jsr(inst)
    elif str_op == 'RET':
        return parse_ret(inst)
    elif str_op == 'RTI':
        return parse_rti(inst)
    elif str_op == 'TRAP':
        return parse_trap(inst)

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
    return ['RET']


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