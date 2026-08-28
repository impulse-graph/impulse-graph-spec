import os

OUTPUT_DIR = "test-vectors/vm-impas/05_extended"

def create_pathological_tests():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. 40k Relation ID
    with open(os.path.join(OUTPUT_DIR, "pathological_rel_id_40k.impas"), "w") as f:
        f.write("""; ====================================================================
; Pathological Test: 40,000 Relation ID (Exceeds 8-bit limit of 255)
; ====================================================================
; Because of the 8-bit packing limit in the 64-bit instruction format, 
; 40000 (0x9C40) gets truncated to 64 (0x40). This test highlights the 
; need for the 128-bit EXTENDED instruction format!
; {EXPECT: STATUS = IMPULSE_VM_ERR_OUT_OF_BOUNDS}

.text
0x00: OP_LOAD_CONST_INT      R0, 1
0x01: OP_LOAD_CONST_INT      R1, 2
0x02: OP_CSR_WALK_PREDICATE  R2, R0, R1, 40000
0x03: OP_HALT
""")

    # 2. 38k Attribute ID
    with open(os.path.join(OUTPUT_DIR, "pathological_attr_id_38k.impas"), "w") as f:
        f.write("""; ====================================================================
; Pathological Test: 38,000 Attribute ID (Exceeds 8-bit limit of 255)
; ====================================================================
; Similar to rel_id, 38000 (0x9470) gets truncated to 112 (0x70) by the
; 8-bit packing limits.
; {EXPECT: STATUS = IMPULSE_VM_ERR_OUT_OF_BOUNDS}

.text
0x00: OP_LOAD_CONST_INT      R0, 1
0x01: OP_LOAD_CONST_INT      R1, 2
0x02: OP_NODE_FILTER         R2, R0, R1, 38000
0x03: OP_HALT
""")

    # 3. 35k Domain ID mapping
    with open(os.path.join(OUTPUT_DIR, "pathological_domain_id_35k.impas"), "w") as f:
        f.write("""; ====================================================================
; Pathological Test: 35,000 Domain ID
; ====================================================================
; The OP_MAP_KEYS_TO_DENSE opcode puts the domain_id in the payload. 
; Here, 35000 (0x88B8) fits in a 16-bit payload, but stresses the 
; architectural upper bounds of the struct.
; {EXPECT: STATUS = IMPULSE_VM_ERR_OUT_OF_BOUNDS}

.text
0x00: OP_MAP_KEYS_TO_DENSE   R0, 35000
0x01: OP_HALT
""")

    print("Pathological test vectors generated successfully in", OUTPUT_DIR)

if __name__ == "__main__":
    create_pathological_tests()
