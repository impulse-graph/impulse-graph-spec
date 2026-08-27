import os

opcodes = {
    "node_filter": {
        "op": "OP_NODE_FILTER",
        "fmt": "{op} R4, R3, R0, 0, 0",
        "setup": """
0x00: OP_LOAD_INLINE_INT_ARRAY R1, MOCK_VALUES
0x01: OP_INIT_MOCK_NODE_ATTR   0, R1, R255
0x02: OP_LOAD_CONST_INT        R0, 30
"""
    }
}

representations = {
    "id_list": {
        "data": ".array_node FRONTIER = [0, 2]",
        "load": "0x03: OP_LOAD_INLINE_NODE_ARRAY  R3, FRONTIER"
    },
    "roaring": {
        "data": ".set_roaring FRONTIER = [0, 2]",
        "load": "0x03: OP_LOAD_INLINE_SET_ROARING R3, FRONTIER"
    },
    "dense": {
        "data": ".set_dense FRONTIER = [0, 2]",
        "load": "0x03: OP_LOAD_INLINE_SET_DENSE   R3, FRONTIER"
    }
}

template = """
; ====================================================================
; Test: {test_name}
; ====================================================================
; {{EXPECT: STATUS = IMPULSE_VM_OK}}
; {{EXPECT: FLAG = !ZF}}
; {{EXPECT: R5 = 1}}

.data
.array_int MOCK_VALUES = [10, 0, 30, 0]
{data_decl}

.text
{op_setup}
{load_inst}
0x04: {exec_inst}
0x05: OP_SET_CARDINALITY R5, R4
0x06: OP_HALT
"""

for op_name, op_info in opcodes.items():
    for rep_name, rep_info in representations.items():
        test_name = f"tc_poly_{op_name}_{rep_name}_pos"
        filename = f"test-vectors/vm-impas/05_extended/{test_name}.impas"
        
        content = template.format(
            test_name=test_name.upper(),
            data_decl=rep_info["data"],
            op_setup=op_info["setup"].strip(),
            load_inst=rep_info["load"],
            exec_inst=op_info["fmt"].format(op=op_info["op"])
        )
        
        with open(filename, "w") as f:
            f.write(content.strip() + "\n")
        print(f"Generated {filename}")
