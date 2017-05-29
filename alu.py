def execute_add(inst_list):
    return inst_list[0] + inst_list[1]

def execute_not(inst_list):
    return ~inst_list

def execute_and(inst_list):
    return inst_list[0] & inst_list[1]