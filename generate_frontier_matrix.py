import os

opcodes = {
    "node_filter": {
        "op": "OP_NODE_FILTER",
        "fmt": "{op} R4, R3, R0, 0", # R4=dest, R3=frontier, R0=data
        "setup": """
.array_float MOCK_PRICES = [1.5, 0.0, 3.14, 0.0]
0x00: OP_LOAD_INLINE_ARRAY     R0, MOCK_PRICES
0x01: OP_INIT_MOCK_NODE_ATTR   0, R0, R255
"""
    }
}

representations = {
    "id_list": {
        "data": ".array_node FRONTIER = [0, 2]",
        "load": "0x02: OP_LOAD_INLINE_NODE_ARRAY  R3, FRONTIER"
    },
    "roaring": {
        "data": ".set_roaring FRONTIER = [0, 2]",
        "load": "0x02: OP_LOAD_INLINE_SET_ROARING R3, FRONTIER"
    },
    "dense": {
        "data": ".set_dense FRONTIER = [0, 2]",
        "load": "0x02: OP_LOAD_INLINE_SET_DENSE   R3, FRONTIER"
    }
}

template = """
; ====================================================================
; Test: {test_name}
; ====================================================================
; {{EXPECT: STATUS = IMPULSE_VM_OK}}
; {{EXPECT: FLAG = !ZF}}

.data
{data_decl}
{op_setup}

.text
{load_inst}
0x03: {exec_inst}
0x04: OP_HALT
"""

for op_name, op_info in opcodes.items():
    for rep_name, rep_info in representations.items():
        test_name = f"tc_poly_{op_name}_{rep_name}_pos"
        filename = f"test-vectors/vm-impas/05_extended/{test_name}.impas"
        
        content = template.format(
            test_name=test_name.upper(),
            data_decl=rep_info["data"],
            op_setup=op_info["setup"],
            load_inst=rep_info["load"],
            exec_inst=op_info["fmt"].format(op=op_info["op"])
        )
        
        with open(filename, "w") as f:
            f.write(content.strip() + "\n")
        print(f"Generated {filename}")
