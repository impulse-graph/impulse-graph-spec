#!/usr/bin/env python3
"""
fuzz_vm_contracts.py — Contract-Guided Differential VM Fuzzer
Generates syntactically and type-valid bytecode instruction sequences
using formal opcode contract metadata and verifies 100% bitwise state
consensus (including ICTX v1 context hash) across:
  - C++ (Optimizations ON)
  - C++ (Optimizations OFF)
  - Java 25 (FFM & Vector API)
  - OCaml (Normative Oracle)
"""

import os
import sys
import json
import random
import struct
import argparse
import subprocess
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).resolve().parent
SPEC_DIR = TOOLS_DIR.parent
ROOT_DIR = SPEC_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from run_vm_asm_suite import (
    Instruction, VmState, OPCODES, parse_impas_file, STATUS_NAMES
)
from four_way_validation import run_cpp, run_java, run_ocaml, compare_state

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Register Type Bitmask Constants (impulse_register_type_t)
TYPE_NULL            = 0
TYPE_INT64           = 1
TYPE_NODE_ID         = 2
TYPE_RELATION_ID     = 3
TYPE_BITSET_HANDLE   = 4
TYPE_NODE_VECTOR     = 5
TYPE_CSR_SPAN        = 6
TYPE_BOOLEAN         = 7
TYPE_FLOAT           = 8
TYPE_DOUBLE          = 9
TYPE_VALUE_MAP       = 10
TYPE_STRING_VECTOR   = 11
TYPE_FLOAT_VECTOR    = 12
TYPE_DOUBLE_VECTOR   = 13
TYPE_UINT64_VECTOR   = 14
TYPE_FRONTIER_STATE  = 15
TYPE_LANE_FRONTIER   = 16

TYPE_NAMES = {
    TYPE_NULL: "NULL",
    TYPE_INT64: "INT64",
    TYPE_NODE_ID: "NODE_ID",
    TYPE_BITSET_HANDLE: "BITSET",
    TYPE_NODE_VECTOR: "NODE_VEC",
    TYPE_FLOAT: "FLOAT",
    TYPE_FLOAT_VECTOR: "FLOAT_VEC",
    TYPE_LANE_FRONTIER: "LANE_FRONTIER",
    TYPE_FRONTIER_STATE: "FRONTIER_STATE"
}

def type_bit(t: int) -> int:
    return 1 << t

def get_possible_types_from_mask(mask: int) -> list[int]:
    res = []
    for t in range(17):
        if (mask & (1 << t)) != 0:
            res.append(t)
    return res

class VmContractFuzzer:
    def __init__(self, contracts_path: Path):
        with open(contracts_path, "r") as f:
            raw_contracts = json.load(f)

        # Filter executable fuzzer contracts (exclude shaders and direct halts)
        self.contracts = []
        for c in raw_contracts:
            m = c["mnemonic"]
            if m.startswith("OP_STREAM_") or m in ("OP_HALT", "OP_TRAP", "OP_THROW", "OP_RET", "OP_LEAVE_FRAME"):
                continue
            self.contracts.append(c)

    def generate_program(self, seed: int, max_instructions: int = 15) -> str:
        rng = random.Random(seed)
        
        # Virtual Register State: reg -> set of active type tags
        reg_state: dict[int, set[int]] = {i: {TYPE_NULL} for i in range(64)}
        
        # Preamble: Initialize topology & initial typed registers
        lines = [
            f"; CONTRACT-GUIDED FUZZ TEST (Seed: {seed})",
            "; {EXPECT: STATUS = IMPULSE_VM_OK}",
            ".fuel 5000",
            "",
            ".data",
            ".csr_inline FUZZ_GRAPH = {",
            "    0: [1, 2],",
            "    1: [2, 3],",
            "    2: [3],",
            "    3: []",
            "}",
            ".array_float ATTR_FLOAT = [1.5, 2.5, 3.5, 4.5]",
            ".array_int ATTR_INT = [10, 20, 30, 40]",
            "",
            ".text",
            "0x00: OP_INIT_MOCK_GRAPH         R0, FUZZ_GRAPH",
            "0x01: OP_LOAD_CONST_INT          R1, 42",
            "0x02: OP_LOAD_CONST_FLOAT        R2, 3.5",
            "0x03: OP_INIT_INPUT_NODE         R3, 0",
            "0x04: OP_INIT_INPUT_SET          R4",
            "0x05: OP_LOAD_INLINE_ARRAY       R5, ATTR_FLOAT",
            "0x06: OP_LOAD_INLINE_INT_ARRAY   R6, ATTR_INT",
        ]
        
        # Update initial register state
        reg_state[1] = {TYPE_INT64}
        reg_state[2] = {TYPE_FLOAT}
        reg_state[3] = {TYPE_NODE_ID}
        reg_state[4] = {TYPE_BITSET_HANDLE}
        reg_state[5] = {TYPE_FLOAT_VECTOR}
        reg_state[6] = {TYPE_NODE_VECTOR}
        
        pc = 7
        
        for _ in range(max_instructions):
            # Find eligible contracts that can accept available register types
            eligible = []
            for c in self.contracts:
                allowed_src = c["allowed_src_types"]
                allowed_aux1 = c["allowed_aux1_types"]
                allowed_aux2 = c["allowed_aux2_types"]
                
                src_regs = [r for r, types in reg_state.items() if (allowed_src == 0) or any((allowed_src & (1 << t)) for t in types)]
                if allowed_src != 0 and not src_regs:
                    continue
                    
                aux1_regs = [r for r, types in reg_state.items() if (allowed_aux1 == 0) or c["allow_zero_skip_aux1"] or any((allowed_aux1 & (1 << t)) for t in types)]
                if allowed_aux1 != 0 and not c["allow_zero_skip_aux1"] and not aux1_regs:
                    continue

                aux2_regs = [r for r, types in reg_state.items() if (allowed_aux2 == 0) or c["allow_zero_skip_aux2"] or any((allowed_aux2 & (1 << t)) for t in types)]
                if allowed_aux2 != 0 and not c["allow_zero_skip_aux2"] and not aux2_regs:
                    continue

                eligible.append(c)

            if not eligible:
                break
                
            c = rng.choice(eligible)
            mnemonic = c["mnemonic"]
            
            # Destination register: choose destination from R10..R31
            dst_reg = rng.randint(10, 31)
            
            # Select valid src register
            src_reg = 0
            if c["allowed_src_types"] != 0:
                valid_srcs = [r for r, types in reg_state.items() if any((c["allowed_src_types"] & (1 << t)) for t in types)]
                src_reg = rng.choice(valid_srcs) if valid_srcs else 0
                
            # Select valid aux1 register
            aux1_reg = 0
            if c["allowed_aux1_types"] != 0:
                valid_aux1 = [r for r, types in reg_state.items() if any((c["allowed_aux1_types"] & (1 << t)) for t in types)]
                if c["allow_zero_skip_aux1"] and rng.random() < 0.3:
                    aux1_reg = 0
                elif valid_aux1:
                    aux1_reg = rng.choice(valid_aux1)
                    
            # Select valid aux2 register
            aux2_reg = 0
            if c["allowed_aux2_types"] != 0:
                valid_aux2 = [r for r, types in reg_state.items() if any((c["allowed_aux2_types"] & (1 << t)) for t in types)]
                if c["allow_zero_skip_aux2"] and rng.random() < 0.3:
                    aux2_reg = 0
                elif valid_aux2:
                    aux2_reg = rng.choice(valid_aux2)
                    
            # Format instruction based on mnemonic syntax
            instr_str = self._format_instruction(pc, c, dst_reg, src_reg, aux1_reg, aux2_reg, rng)
            if instr_str:
                lines.append(instr_str)
                # Update output register type
                out_types = get_possible_types_from_mask(c["output_dst_types"])
                if out_types and c["modifies_dst_state"]:
                    reg_state[dst_reg] = {rng.choice(out_types)}
                pc += 1

        lines.append(f"0x{pc:02X}: OP_HALT")
        return "\n".join(lines) + "\n"

    def _format_instruction(self, pc: int, c: dict, dst: int, src: int, aux1: int, aux2: int, rng: random.Random) -> str:
        m = c["mnemonic"]
        hex_pc = f"0x{pc:02X}"
        
        if m in ("OP_CSR_WALK", "OP_CSC_WALK", "OP_ADAPTIVE_WALK", "OP_CSR_DEGREE"):
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, 0"
        elif m in ("OP_SET_UNION", "OP_SET_INTERSECT", "OP_SET_DIFFERENCE"):
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, R{aux1}"
        elif m == "OP_SET_CARDINALITY":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}"
        elif m == "OP_MOV":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}"
        elif m == "OP_CLEAR_REG":
            return f"{hex_pc}: {m:<24} R{dst}"
        elif m in ("OP_VEC_CMP_EQ", "OP_VEC_CMP_GT", "OP_VEC_CMP_LT"):
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, R{aux1}"
        elif m == "OP_VEC_MATH_UNARY":
            # Unary math opcodes 0..4 (abs, neg, sqrt, etc.)
            sub_op = rng.randint(0, 4)
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, {sub_op}"
        elif m == "OP_VEC_MATH_BINARY":
            # Binary math opcodes 0..3 (add, sub, mul, div)
            sub_op = rng.randint(0, 3)
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, R{aux1}, {sub_op}"
        elif m == "OP_VECTOR_REDUCE_SUM":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}"
        elif m == "OP_FLOAT_VECTOR_SCALE":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, 2"
        elif m == "OP_EXTRACT_VALIDITY":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}"
        elif m == "OP_LANE_INIT_SEEDS":
            return f"{hex_pc}: {m:<24} R{dst}, 0"
        elif m == "OP_LANE_INIT_GROUPS":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}"
        elif m in ("OP_LANE_CSR_WALK", "OP_LANE_CSC_WALK"):
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, 0"
        elif m == "OP_LANE_FILTER_QUORUM":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, 1"
        elif m == "OP_LANE_REDUCE_AND":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}"
        elif m == "OP_VECTOR_ANN_SEARCH":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, 2, 0, 0"
        elif m == "OP_VECTOR_RERANK_DOT":
            return f"{hex_pc}: {m:<24} R{dst}, R{src}, R{aux1}, 0, 0"
        elif m == "OP_LOAD_CONST_INT":
            val = rng.randint(1, 100)
            return f"{hex_pc}: {m:<24} R{dst}, {val}"
        elif m == "OP_LOAD_CONST_FLOAT":
            val = round(rng.uniform(0.1, 10.0), 2)
            return f"{hex_pc}: {m:<24} R{dst}, {val}"
        elif m == "OP_ASSERT":
            return f"{hex_pc}: {m:<24} R{src}, 0"
        else:
            return None

def main():
    parser = argparse.ArgumentParser(description="ImpulseVM Contract-Guided Differential Fuzzer")
    parser.add_argument("--iterations", type=int, default=25, help="Number of fuzzing iterations")
    parser.add_argument("--seed", type=int, default=1337, help="Starting random seed")
    parser.add_argument("--max-instrs", type=int, default=12, help="Max random instructions per program")
    parser.add_argument("--shrink", action="store_true", help="Perform delta-debugging shrinking on discrepancies")
    parser.add_argument("--contracts", type=str, default=str(TOOLS_DIR / "contracts.json"), help="Path to contracts.json")
    parser.add_argument("--dump-dir", type=str, default=str(TOOLS_DIR / "fuzz_findings"), help="Directory to save finding artifacts")
    args = parser.parse_args()

    print(f"{BOLD}{BLUE}==============================================================={RESET}")
    print(f"{BOLD}{BLUE} ImpulseVM Contract-Guided Differential Fuzzer                 {RESET}")
    print(f"{BOLD}{BLUE} Validating C++(ON & OFF) vs Java 25 vs OCaml Context Hashes   {RESET}")
    print(f"{BOLD}{BLUE}==============================================================={RESET}\n")

    lib_on_path = os.environ.get("IMPULSE_LIB_PATH_ON")
    lib_off_path = os.environ.get("IMPULSE_LIB_PATH_OFF")
    if not lib_on_path or not lib_off_path:
        print(f"{RED}Error: IMPULSE_LIB_PATH_ON and IMPULSE_LIB_PATH_OFF must be set.{RESET}")
        sys.exit(1)

    import ctypes
    lib_on = ctypes.CDLL(lib_on_path)
    lib_off = ctypes.CDLL(lib_off_path)
    for lib in [lib_on, lib_off]:
        lib.impulse_vm_context_create.argtypes = [ctypes.c_void_p]
        lib.impulse_vm_context_create.restype = ctypes.c_void_p
        lib.impulse_vm_context_destroy.argtypes = [ctypes.c_void_p]
        lib.impulse_vm_context_destroy.restype = None
        lib.impulse_vm_context_bind_inline_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        lib.impulse_vm_context_bind_inline_data.restype = None
        lib.impulse_vm_context_set_fuel.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        lib.impulse_vm_context_set_fuel.restype = None
        lib.impulse_vm_execute.argtypes = [ctypes.POINTER(Instruction), ctypes.c_size_t, ctypes.POINTER(VmState), ctypes.c_uint64]
        lib.impulse_vm_execute.restype = ctypes.c_int
        lib.impulse_vm_state_hash_hex.argtypes = [ctypes.POINTER(VmState), ctypes.c_int32, ctypes.c_char_p]
        lib.impulse_vm_state_hash_hex.restype = ctypes.c_int

    java_dir = ROOT_DIR / "impulse-graph-java"
    cp_file = java_dir / "impulse-vm" / "cp.txt"
    if not cp_file.exists():
        subprocess.run(["mvn", "dependency:build-classpath", "-Dmdep.outputFile=cp.txt", "-pl", "impulse-vm"], cwd=java_dir, check=True)
    with open(cp_file, "r") as f:
        maven_cp = f.read().strip()
    cp = f"impulse-vm/target/classes:impulse-vm/target/test-classes:impulse-api/target/classes:impulse-storage/target/classes:impulse-spec/target/classes:{maven_cp}"

    fuzzer = VmContractFuzzer(Path(args.contracts))
    dump_dir = Path(args.dump_dir)
    dump_dir.mkdir(parents=True, exist_ok=True)

    passed_count = 0
    divergence_count = 0
    temp_impas = TOOLS_DIR / ".fuzz_tmp.impas"

    print(f"Running {args.iterations} fuzzing iterations (seed={args.seed}, max_instrs={args.max_instrs})...\n")

    for i in range(args.iterations):
        iter_seed = args.seed + i
        prog_text = fuzzer.generate_program(iter_seed, max_instructions=args.max_instrs)
        
        with open(temp_impas, "w") as f:
            f.write(prog_text)

        try:
            instrs, data_bytes, expectations, _ = parse_impas_file(temp_impas)
            c_instrs = (Instruction * len(instrs))(*instrs)
            
            impb_file = temp_impas.with_suffix('.impb')
            with open(impb_file, 'wb') as f:
                f.write(bytes(c_instrs))
                
            impb_data_file = temp_impas.with_suffix('.impb_data')
            with open(impb_data_file, 'wb') as f:
                f.write(data_bytes)

            c_on = run_cpp(lib_on, temp_impas)
            c_off = run_cpp(lib_off, temp_impas)
            j_state = run_java(temp_impas, impb_file, impb_data_file, cp)
            o_state = run_ocaml(temp_impas, impb_file, impb_data_file)

            diffs = compare_state(c_on, c_off, j_state, o_state, expectations)
            if diffs:
                divergence_count += 1
                print(f"{YELLOW}[DIVERGENCE #{divergence_count}]{RESET} Iteration {i+1} (Seed: {iter_seed}):")
                for d in diffs[:4]:
                    print(f"       -> {d}")
                repro_path = dump_dir / f"fuzz_repro_seed_{iter_seed}.impas"
                with open(repro_path, "w") as f:
                    f.write(prog_text)
                print(f"       Saved repro to: {repro_path.name}")
            else:
                passed_count += 1
                h = c_on["context_hash"][:16]
                print(f"{GREEN}[CONSENSUS]{RESET} Iter {i+1:3d} (Seed {iter_seed}): Hash={h}... Status={c_on['status']} PC={c_on['pc']}")

        except Exception as e:
            print(f"{RED}[ERROR]{RESET} Iteration {i+1} execution failed: {e}")
        finally:
            if temp_impas.exists(): temp_impas.unlink()
            if (TOOLS_DIR / ".fuzz_tmp.impb").exists(): (TOOLS_DIR / ".fuzz_tmp.impb").unlink()
            if (TOOLS_DIR / ".fuzz_tmp.impb_data").exists(): (TOOLS_DIR / ".fuzz_tmp.impb_data").unlink()

    print(f"\n{BOLD}{BLUE}==============================================================={RESET}")
    print(f"Fuzzing Complete: {passed_count} Consensus Matches, {divergence_count} Divergences Captured")
    print(f"Reproducing artifacts saved in: {dump_dir}")
    print(f"{BOLD}{BLUE}==============================================================={RESET}\n")

if __name__ == "__main__":
    main()
