#!/usr/bin/env python3
"""
ImpulseVM Convention-Driven Assembly Test Runner & Opcode Coverage Verifier
Spec v0.9.0 / Spec v2.4

Scans test-vectors/vm-impas/ for annotated .impas files, executes them against
the ImpulseVM C-ABI engine via ctypes FFI, verifies register and status expectations,
and enforces 100% Opcode Coverage with a minimum multi-file appearance threshold.
"""

import os
import re
import sys
import ctypes
from pathlib import Path

# --- Color Formatting ---
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# --- Opcode Mapping Table ---
OPCODES = {
    "OP_HALT": 0x00,
    "OP_NOP": 0x01,
    "OP_INIT_INPUT_NODE": 0x02,
    "OP_INIT_INPUT_SET": 0x03,
    "OP_LOAD_CONST_INT": 0x04,
    "OP_MAP_KEYS_TO_DENSE": 0x05,
    "OP_LOAD_CONST_FLOAT": 0x06,
    "OP_LOAD_CONST_STR_PREFIX": 0x07,
    "OP_LOAD_INLINE_ARRAY": 0x08,
    "OP_INIT_MOCK_GRAPH": 0x09,

    "OP_CSR_WALK": 0x10,
    "OP_CSR_WALK_FILTERED": 0x11,
    "OP_CSR_DEGREE": 0x12,
    "OP_CSR_WALK_PREDICATE": 0x13,
    "OP_NODE_FILTER": 0x14,
    "OP_NODE_FILTER_STR_PREFIX": 0x15,
    "OP_CSR_WALK_REDUCE_SUM": 0x16,
    "OP_CSR_WALK_REDUCE": 0x17,
    "OP_CSC_WALK": 0x18,
    "OP_HAS_CSR": 0x19,
    "OP_HAS_CSC": 0x1A,
    "OP_HAS_COO": 0x1B,
    "OP_HAS_KEY_CATALOG": 0x1C,
    "OP_ASSERT_FINITE": 0x2A,

    "OP_SET_UNION": 0x30,
    "OP_SET_INTERSECT": 0x31,
    "OP_SET_DIFFERENCE": 0x32,
    "OP_SET_CARDINALITY": 0x33,
    "OP_VECTOR_MUL_ATTR": 0x34,
    "OP_VECTOR_REDUCE_SUM": 0x35,
    "OP_VECTOR_DIV": 0x36,
    "OP_VECTOR_STR_CONCAT": 0x37,
    "OP_FLOAT_VECTOR_SCALE": 0x38,
    "OP_L1_NORM_DIFF": 0x39,

    "OP_CC_AFFOREST": 0x40,
    "OP_MXV": 0x41,
    "OP_VXM": 0x42,
    "OP_EWISE_ADD": 0x43,
    "OP_EWISE_MULT": 0x44,
    "OP_REDUCE": 0x45,
    "OP_CC_HOOK_COMPRESS": 0x46,
    "OP_TC_SWEEP_BATCH": 0x47,
    "OP_BRANDES_FORWARD": 0x48,
    "OP_BRANDES_BACKWARD": 0x49,
    "OP_DELTA_STEP_RELAX": 0x4A,
    "OP_READ_EDGE_WEIGHT": 0x4B,

    "OP_JMP": 0x50,
    "OP_JZ": 0x51,
    "OP_JNZ": 0x52,
    "OP_LOOP_DECR": 0x53,
    "OP_STABLE_CHECK": 0x54,
    "OP_CALL": 0x55,
    "OP_RET": 0x56,
    "OP_ENTER_FRAME": 0x57,
    "OP_LEAVE_FRAME": 0x58,
    "OP_THROW": 0x5A,
    "OP_ASSERT": 0x5B,
    "OP_TRAP": 0x5C,

    "OP_SAMPLE_NEIGHBORS": 0x60,
    "OP_RANDOM_WALK": 0x61,
    "OP_SCATTER_GATHER": 0x62,
    "OP_REBAC_CHECK": 0x63,
    "OP_ROARING_BITMAP_AND": 0x64,
    "OP_ISLAND_DETECT": 0x65,
    "OP_SPARSE_MATVEC": 0x66,
    "OP_LOUVAIN_MODULARITY": 0x67,
    "OP_KCORE_DECOMPOSITION": 0x68,
    "OP_MOTIF_MATCH_3": 0x69,
    "OP_GRAPH_ISOMORPHISM": 0x6A,
    "OP_ROARING_BITMAP_OR": 0x6B,
    "OP_ROARING_BITMAP_AND_NOT": 0x6C,

    "OP_MOV": 0x70,
    "OP_CLEAR_REG": 0x71,
    "OP_LOAD_INDIRECT": 0x72,
    "OP_ALLOC_SCRATCH": 0x73,
    "OP_ASSERT_SCRATCH_BYTES": 0x74,
    "OP_SET_MAX_DOP": 0x75,

    "OP_COLLECT_BITSET": 0x90,
    "OP_COLLECT_ARRAY": 0x91,
    "OP_MAP_DENSE_TO_KEYS": 0x92,
    "OP_COLLECT_VALUE_MAP": 0x93,
}

STATUS_NAMES = {
    0: "IMPULSE_VM_OK",
    1: "IMPULSE_VM_ERR_INVALID_OPCODE",
    2: "IMPULSE_VM_ERR_OUT_OF_BOUNDS",
    3: "IMPULSE_VM_ERR_NULL_SNAPSHOT",
    4: "IMPULSE_VM_ERR_STACK_OVERFLOW",
    5: "IMPULSE_VM_ERR_STACK_UNDERFLOW",
    6: "IMPULSE_VM_ERR_INVALID_REGISTER",
    7: "IMPULSE_VM_ERR_USER_THROW",
    8: "IMPULSE_VM_ERR_ASSERTION_FAILED",
    9: "IMPULSE_VM_ERR_TRAP",
    10: "IMPULSE_VM_ERR_RESERVED_OPCODE",
    11: "IMPULSE_VM_ERR_BUFFER_OVERFLOW",
    12: "IMPULSE_VM_ERR_FLOATING_POINT",
    13: "IMPULSE_VM_ERR_GAS_EXHAUSTED",
}

# --- C-ABI Types ---
class Instruction(ctypes.Structure):
    _fields_ = [
        ("opcode", ctypes.c_uint8),
        ("flags", ctypes.c_uint8),
        ("dst_reg", ctypes.c_uint16),
        ("payload", ctypes.c_uint32),
    ]

class VmState(ctypes.Structure):
    _fields_ = [
        ("pc", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
        ("flags", ctypes.c_uint64),
        ("registers", ctypes.c_uint64 * 64),
        ("register_types", ctypes.c_uint8 * 64),
        ("query_context", ctypes.c_void_p),
        ("call_stack", ctypes.c_uint32 * 8),
        ("call_stack_depth", ctypes.c_uint32),
        ("reserved_padding2", ctypes.c_uint32),
    ]

# --- Find Library Path ---
def load_native_library():
    repo_root = Path(__file__).resolve().parent.parent.parent
    possible_paths = [
        repo_root / "impulse-graph-core" / "impulse-cpp" / "build" / "libimpulse_graph.dylib",
        repo_root / "impulse-graph-core" / "impulse-cpp" / "build" / "libimpulse_graph.so",
        repo_root / "impulse-graph-core" / "impulse-cpp" / "build" / "impulse_graph.dll",
    ]
    for p in possible_paths:
        if p.exists():
            return ctypes.CDLL(str(p))
    raise RuntimeError(f"Native library not found in {possible_paths}. Please run cmake build first.")

CONSTANTS = {
    "SEMIRING_PLUS_TIMES": 0,
    "SEMIRING_MIN_PLUS": 1,
    "SEMIRING_MAX_MIN": 2,
    "SEMIRING_BOOL": 3,
    "BINARY_OP_ADD": 0,
    "BINARY_OP_MUL": 1,
    "BINARY_OP_MIN": 2,
    "BINARY_OP_MAX": 3,
    "BINARY_OP_AND": 4,
    "BINARY_OP_OR": 5,
}

def parse_val(t):
    if t in CONSTANTS:
        return CONSTANTS[t]
    if t.startswith("0x"):
        return int(t, 16)
    if t.startswith("R"):
        return int(t[1:])
    try:
        return int(t)
    except:
        return 0

# --- Parse Assembly File ---
def parse_impas_file(file_path):
    expectations = {
        "status": "IMPULSE_VM_OK",
        "registers": {},
        "throw_code": None,
        "flag_zf": None,
    }
    instructions = []
    data_bytes = bytearray()
    opcodes_used = set()

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Build inline binary payload
    import struct
    full_text = "".join(lines)
    symbols = {}
    
    # Parse all .csr_inline blocks
    for csr_match in re.finditer(r"\.csr_inline\s+(\w+)\s*=\s*\{([^}]+)\}", full_text):
        sym_name = csr_match.group(1)
        csr_body = csr_match.group(2)

        offset_start = len(data_bytes)
        offsets = [0]
        targets = []
        node_count = 0

        for line in csr_body.splitlines():
            line_str = line.strip()
            if not line_str or ":" not in line_str:
                continue
            src_str, tgt_str = line_str.split(":", 1)
            tgt_str = tgt_str.strip().replace("[", "").replace("]", "").strip()
            if tgt_str:
                tgts = [int(x.strip()) for x in tgt_str.split(",") if x.strip()]
            else:
                tgts = []
            targets.extend(tgts)
            offsets.append(len(targets))
            node_count += 1

        for off in offsets:
            data_bytes.extend(struct.pack("<I", off))
        for tgt in targets:
            data_bytes.extend(struct.pack("<I", tgt))
        symbols[sym_name] = (offset_start, node_count)

    # Parse all .array_float blocks
    for arr_match in re.finditer(r"\.array_float\s+(\w+)\s*=\s*\[([^\]]+)\]", full_text):
        sym_name = arr_match.group(1)
        arr_body = arr_match.group(2)
        offset_start = len(data_bytes)
        floats = [float(x.strip()) for x in arr_body.split(",") if x.strip()]
        for flt in floats:
            data_bytes.extend(struct.pack("<f", flt))
        symbols[sym_name] = (offset_start, len(floats))

    # Parse all .rel directives: .rel <name> = <id> [, multiplicity = <m1|1m|11|mn>]
    for rel_match in re.finditer(r"\.rel\s+(\w+)\s*=\s*(\d+)(?:\s*,\s*multiplicity\s*=\s*(\w+))?", full_text):
        rel_name = rel_match.group(1)
        rel_id = int(rel_match.group(2))
        CONSTANTS[rel_name] = rel_id
        symbols[rel_name] = (rel_id, 0)

    # Parse all .vrel directives: .vrel <name> = \[(.*?)\]
    for vrel_match in re.finditer(r"\.vrel\s+(\w+)\s*=\s*\[([^\]]+)\]", full_text):
        vrel_name = vrel_match.group(1)
        comp_str = vrel_match.group(2)
        comp_ids = [parse_val(x.strip()) for x in comp_str.split(",") if x.strip()]
        # Assign virtual relation ID (e.g. 10 + len(symbols))
        vrel_id = 10 + len(symbols)
        CONSTANTS[vrel_name] = vrel_id
        symbols[vrel_name] = (vrel_id, comp_ids)

    for line in lines:
        line_str = line.strip()

        # Parse Token Expectations
        match_exp = re.search(r";\s*\{EXPECT:\s*([^}]+)\}", line_str)
        if match_exp:
            exp_body = match_exp.group(1).strip()
            if "=" in exp_body:
                key, val = [x.strip() for x in exp_body.split("=", 1)]
                if key == "STATUS":
                    expectations["status"] = val
                elif key.startswith("R"):
                    reg_idx = int(key[1:])
                    expectations["registers"][reg_idx] = int(val)
                elif key == "THROW_CODE":
                    expectations["throw_code"] = int(val)
                elif key == "PC":
                    expectations["pc"] = int(val)
                elif key == "CALL_STACK_DEPTH":
                    expectations["call_stack_depth"] = int(val)
                elif key == "SCRATCH_BYTES":
                    expectations["scratch_bytes"] = int(val)
                elif key == "MAX_DOP":
                    expectations["max_dop"] = int(val)
                elif key == "FLAG":
                    if val == "ZF":
                        expectations["flag_zf"] = True
                    elif val == "!ZF":
                        expectations["flag_zf"] = False
                    elif val == "ST":
                        expectations["flag_st"] = True
                    elif val == "!ST":
                        expectations["flag_st"] = False

        # Parse Code Instructions & Directives
        if line_str.startswith(".fuel"):
            parts = line_str.split()
            if len(parts) > 1:
                expectations["fuel"] = parse_val(parts[1])
            continue

        if line_str.startswith(";") or line_str.startswith(".") or not line_str:
            continue

        # Format: 0x00: OP_LOAD_CONST_INT R0, 42
        clean_line = re.sub(r";.*$", "", line_str).strip()
        if not clean_line:
            continue

        parts = clean_line.split(":", 1)
        code_part = parts[1].strip() if len(parts) > 1 else parts[0].strip()

        tokens = re.split(r"[\s,]+", code_part)
        op_name = tokens[0].upper()

        if op_name in OPCODES:
            op_code = OPCODES[op_name]
            opcodes_used.add(op_name)

            dst_reg = 0
            payload = 0
            flags = 0

            if op_name in ("OP_JMP", "OP_JZ", "OP_JNZ", "OP_CALL", "OP_TRAP", "OP_NOP", "OP_HALT", "OP_RET", "OP_STABLE_CHECK", "OP_LEAVE_FRAME"):
                if len(tokens) > 1:
                    payload = parse_val(tokens[1])
            elif op_name in ("OP_INIT_MOCK_GRAPH", "OP_LOAD_INLINE_ARRAY"):
                if len(tokens) > 1:
                    dst_reg = parse_val(tokens[1])
                if len(tokens) > 2:
                    sym_name = tokens[2].strip()
                    if sym_name in symbols:
                        off_b, cnt = symbols[sym_name]
                        payload = off_b | (cnt << 16)
            elif op_name == "OP_CSC_WALK":
                if len(tokens) > 1: dst_reg = parse_val(tokens[1])
                if len(tokens) > 2: payload |= (parse_val(tokens[2]) & 0xFFFF)
                if len(tokens) == 4:
                    payload |= ((parse_val(tokens[3]) & 0xFFFF) << 16)
                elif len(tokens) > 4:
                    payload |= ((parse_val(tokens[3]) & 0xFF) << 16)
                    payload |= ((parse_val(tokens[4]) & 0xFF) << 24)
            elif op_name in ("OP_MXV", "OP_VXM"):
                if len(tokens) > 1: dst_reg = parse_val(tokens[1])
                if len(tokens) > 2: payload |= (parse_val(tokens[2]) & 0xFF)
                if len(tokens) > 3: payload |= ((parse_val(tokens[3]) & 0xFF) << 8)
                if len(tokens) > 4: payload |= ((parse_val(tokens[4]) & 0xFFFF) << 16)
            elif op_name in ("OP_LOAD_INDIRECT", "OP_ASSERT", "OP_ENTER_FRAME"):
                if len(tokens) > 1: dst_reg = parse_val(tokens[1])
                if len(tokens) > 2: payload |= (parse_val(tokens[2]) & 0xFFFF)
                if len(tokens) > 3: payload |= ((parse_val(tokens[3]) & 0xFFFF) << 16)
                if len(tokens) > 4: flags = parse_val(tokens[4])
            elif op_name in ("OP_ALLOC_SCRATCH", "OP_ASSERT_SCRATCH_BYTES", "OP_SET_MAX_DOP"):
                if len(tokens) > 1: dst_reg = parse_val(tokens[1])
                if len(tokens) > 2: payload = parse_val(tokens[2])
            else:
                if len(tokens) > 1:
                    if tokens[1].startswith("R"):
                        dst_reg = parse_val(tokens[1])
                    else:
                        payload = parse_val(tokens[1])
                if len(tokens) > 2:
                    payload |= (parse_val(tokens[2]) & 0xFFFF)
                if len(tokens) > 3:
                    payload |= ((parse_val(tokens[3]) & 0xFFFF) << 16)
                if len(tokens) > 4:
                    flags = parse_val(tokens[4])

            instructions.append(Instruction(op_code, flags, dst_reg, payload & 0xFFFFFFFF))

    return instructions, bytes(data_bytes), expectations, opcodes_used

# --- Runner Main ---
def print_flush(*args, **kwargs):
    kwargs["flush"] = True
    print(*args, **kwargs)

# --- Runner Main ---
def main():
    print_flush(f"{BOLD}{BLUE}==============================================================={RESET}")
    print_flush(f"{BOLD}{BLUE} ImpulseVM Polyglot Assembly Test Suite & Coverage Verifier   {RESET}")
    print_flush(f"{BOLD}{BLUE} Spec v0.9.0 / Spec v2.4                                       {RESET}")
    print_flush(f"{BOLD}{BLUE}==============================================================={RESET}\n")

    try:
        lib = load_native_library()
    except Exception as e:
        print_flush(f"{RED}Error loading native C-ABI kernel: {e}{RESET}")
        sys.exit(1)

    # Set FFI signatures
    lib.impulse_vm_context_create.argtypes = [ctypes.c_void_p]
    lib.impulse_vm_context_create.restype = ctypes.c_void_p

    lib.impulse_vm_context_destroy.argtypes = [ctypes.c_void_p]
    lib.impulse_vm_context_destroy.restype = None

    lib.impulse_vm_context_bind_inline_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    lib.impulse_vm_context_bind_inline_data.restype = None

    lib.impulse_vm_context_set_fuel.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.impulse_vm_context_set_fuel.restype = None

    lib.impulse_vm_execute.argtypes = [
        ctypes.POINTER(Instruction),
        ctypes.c_size_t,
        ctypes.POINTER(VmState),
        ctypes.c_uint64,
    ]
    lib.impulse_vm_execute.restype = ctypes.c_int

    spec_dir = Path(__file__).resolve().parent.parent
    test_dir = spec_dir / "test-vectors" / "vm-impas"
    impas_files = list(test_dir.glob("**/*.impas"))

    if not impas_files:
        print_flush(f"{RED}No .impas test files found in {test_dir}{RESET}")
        sys.exit(1)

    passed_count = 0
    failed_count = 0

    opcode_file_counts = {op: set() for op in OPCODES.keys()}

    for test_file in sorted(impas_files):
        rel_path = test_file.relative_to(spec_dir)
        try:
            instrs, data_buf, expectations, opcodes_used = parse_impas_file(test_file)

            for op in opcodes_used:
                opcode_file_counts[op].add(test_file.name)

            if not instrs:
                print_flush(f"{YELLOW}[SKIP]{RESET} {rel_path} (Empty or no executable instructions)")
                continue

            print_flush(f"[RUN] {rel_path}")
            ctx = lib.impulse_vm_context_create(None)
            if "fuel" in expectations:
                lib.impulse_vm_context_set_fuel(ctx, expectations["fuel"])
            c_buf = None
            if data_buf:
                c_buf = (ctypes.c_char * len(data_buf)).from_buffer_copy(data_buf)
                lib.impulse_vm_context_bind_inline_data(ctx, ctypes.cast(c_buf, ctypes.c_void_p), len(data_buf))

            state = VmState()
            state.query_context = ctx

            c_instrs = (Instruction * len(instrs))(*instrs)
            status_code = lib.impulse_vm_execute(c_instrs, len(instrs), ctypes.byref(state), 0)
            status_name = STATUS_NAMES.get(status_code, f"UNKNOWN({status_code})")

            # Verify Expectations
            test_passed = True
            failure_reasons = []

            expected_status = expectations["status"]
            if status_name != expected_status:
                test_passed = False
                failure_reasons.append(f"Expected STATUS={expected_status}, got {status_name}")

            for reg_idx, exp_val in expectations["registers"].items():
                actual_val = state.registers[reg_idx]
                if actual_val != exp_val:
                    test_passed = False
                    failure_reasons.append(f"Expected R{reg_idx}={exp_val}, got {actual_val}")

            if expectations["throw_code"] is not None:
                actual_throw = state.registers[0]
                if actual_throw != expectations["throw_code"]:
                    test_passed = False
                    failure_reasons.append(f"Expected THROW_CODE={expectations['throw_code']}, got {actual_throw}")

            if expectations["flag_zf"] is not None:
                actual_zf = bool(state.flags & 1)
                if actual_zf != expectations["flag_zf"]:
                    test_passed = False
                    failure_reasons.append(f"Expected FLAG ZF={expectations['flag_zf']}, got {actual_zf}")

            if expectations.get("flag_st") is not None:
                actual_st = bool(state.flags & 2)
                if actual_st != expectations["flag_st"]:
                    test_passed = False
                    failure_reasons.append(f"Expected FLAG ST={expectations['flag_st']}, got {actual_st}")

            if expectations.get("pc") is not None:
                if state.pc != expectations["pc"]:
                    test_passed = False
                    failure_reasons.append(f"Expected PC={expectations['pc']}, got {state.pc}")

            if expectations.get("call_stack_depth") is not None:
                if state.call_stack_depth != expectations["call_stack_depth"]:
                    test_passed = False
                    failure_reasons.append(f"Expected CALL_STACK_DEPTH={expectations['call_stack_depth']}, got {state.call_stack_depth}")

            lib.impulse_vm_context_destroy(ctx)

            if test_passed:
                print_flush(f"{GREEN}[PASS]{RESET} {rel_path}")
                passed_count += 1
            else:
                print_flush(f"{RED}[FAIL]{RESET} {rel_path}")
                print_flush(f"       -> Fail location: PC={state.pc}")
                for reason in failure_reasons:
                    print_flush(f"       -> {RED}{reason}{RESET}")
                failed_count += 1
        except Exception as err:
            print_flush(f"{RED}[FAIL]{RESET} {rel_path} (Execution Exception: {err})")
            failed_count += 1

    # --- Opcode Coverage Report ---
    print_flush(f"\n{BOLD}{BLUE}==============================================================={RESET}")
    print_flush(f"{BOLD}{BLUE} Opcode Coverage & Multi-File Threshold Analysis               {RESET}")
    print_flush(f"{BOLD}{BLUE}==============================================================={RESET}\n")

    MIN_FILE_THRESHOLD = 2
    uncovered_opcodes = []
    under_threshold_opcodes = []

    print_flush(f"{'Opcode Name':<30} | {'Hex Code':<10} | {'File Count':<12} | {'Coverage Status':<15}")
    print_flush("-" * 75)

    for op_name, hex_code in sorted(OPCODES.items(), key=lambda x: x[1]):
        file_cnt = len(opcode_file_counts[op_name])
        hex_str = f"0x{hex_code:02X}"

        if file_cnt == 0:
            status_str = f"{RED}UNCOVERED{RESET}"
            uncovered_opcodes.append(op_name)
        elif file_cnt < MIN_FILE_THRESHOLD:
            status_str = f"{YELLOW}UNDER THRESHOLD{RESET}"
            under_threshold_opcodes.append(op_name)
        else:
            status_str = f"{GREEN}OK ({file_cnt} files){RESET}"

        print_flush(f"{op_name:<30} | {hex_str:<10} | {file_cnt:<12} | {status_str}")

    total_opcodes = len(OPCODES)
    covered_opcodes = total_opcodes - len(uncovered_opcodes)
    coverage_pct = (covered_opcodes / total_opcodes) * 100.0

    print_flush("-" * 75)
    print_flush(f"{BOLD}Total Opcodes Defined:{RESET} {total_opcodes}")
    print_flush(f"{BOLD}Covered Opcodes:{RESET} {covered_opcodes} ({coverage_pct:.1f}%)")
    print_flush(f"{BOLD}Multi-File Threshold Requirement:{RESET} >= {MIN_FILE_THRESHOLD} files per opcode\n")

    # --- Final Conclusion ---
    if failed_count > 0 or uncovered_opcodes or under_threshold_opcodes:
        print_flush(f"{BOLD}{RED}FAILED:{RESET} Suite failed verification.")
        if failed_count > 0:
            print_flush(f" - {failed_count} test file(s) failed execution assertions.")
        if uncovered_opcodes:
            print_flush(f" - {len(uncovered_opcodes)} opcode(s) have 0 test files.")
        if under_threshold_opcodes:
            print_flush(f" - {len(under_threshold_opcodes)} opcode(s) appear in < {MIN_FILE_THRESHOLD} test files.")
        sys.exit(1)
    else:
        print_flush(f"{BOLD}{GREEN}SUCCESS:{RESET} All {passed_count} test vectors passed! 100% Opcode Coverage threshold met.")
        sys.exit(0)

if __name__ == "__main__":
    main()
