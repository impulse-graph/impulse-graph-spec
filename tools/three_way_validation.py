#!/usr/bin/env python3

import os
import re
import sys
import json
import ctypes
import subprocess
from pathlib import Path
from run_vm_asm_suite import OPCODES, OPCODE_ALIASES, STATUS_NAMES, Instruction, VmState, load_native_library, parse_impas_file

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def run_cpp(lib, test_file):
    instrs, data_buf, expectations, opcodes_used = parse_impas_file(test_file)
    if not instrs:
        return None
    
    ctx = lib.impulse_vm_context_create(None)
    if "fuel" in expectations:
        lib.impulse_vm_context_set_fuel(ctx, expectations["fuel"])
    elif os.environ.get("IMPULSE_TEST_ENABLE_FUEL") == "1":
        lib.impulse_vm_context_set_fuel(ctx, 1000000)
    
    c_buf = None
    if data_buf:
        c_buf = (ctypes.c_char * len(data_buf)).from_buffer_copy(data_buf)
        lib.impulse_vm_context_bind_inline_data(ctx, ctypes.cast(c_buf, ctypes.c_void_p), len(data_buf))

    state = VmState()
    state.query_context = ctx
    
    c_instrs = (Instruction * len(instrs))(*instrs)
    status_code = lib.impulse_vm_execute(c_instrs, len(instrs), ctypes.byref(state), 0)
    status_name = STATUS_NAMES.get(status_code, f"UNKNOWN({status_code})")
    
    zf = bool(state.flags & (1 << 0))
    st = bool(state.flags & (1 << 4))
    
    regs = {}
    for i in range(64):
        regs[f"R{i}"] = state.registers[i]
        
    lib.impulse_vm_context_destroy(ctx)
    return {
        "status": status_name,
        "pc": state.pc,
        "flags": {"zf": zf, "st": st},
        "registers": regs
    }

def run_java(test_file, cp):
    java_dir = Path(__file__).resolve().parent.parent.parent / "impulse-graph-java"
    cmd = [
        "java",
        "--add-modules", "jdk.incubator.vector",
        "-cp", cp,
        "org.impulsegraph.vm.JavaVmJsonRunner",
        str(test_file)
    ]
    res = subprocess.run(cmd, cwd=java_dir, capture_output=True, text=True)
    if res.returncode != 0:
        raise Exception(f"Java execution failed: {res.stderr}\nstdout={res.stdout}")
    return json.loads(res.stdout.strip())

def run_ocaml(test_file):
    ocaml_bin = Path(__file__).resolve().parent.parent.parent / "impulse-ocaml" / "_build" / "install" / "default" / "bin" / "impulse-ocaml"
    cmd = [str(ocaml_bin), "--asm", str(test_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(res.stdout.strip())
    except Exception as e:
        raise Exception(f"OCaml execution failed. stdout: {res.stdout}, stderr: {res.stderr}")

def compare_state(cpp_state, java_state, ocaml_state):
    diffs = []
    
    # Compare Status
    if cpp_state["status"] != java_state["status"] or cpp_state["status"] != ocaml_state["status"]:
        diffs.append(f"Status mismatch: C++={cpp_state['status']}, Java={java_state['status']}, OCaml={ocaml_state['status']}")
    
    # Compare PC
    if cpp_state["pc"] != java_state["pc"] or cpp_state["pc"] != ocaml_state["pc"]:
        diffs.append(f"PC mismatch: C++={cpp_state['pc']}, Java={java_state['pc']}, OCaml={ocaml_state['pc']}")
        
    # Compare Flags
    for flag in ["zf", "st"]:
        c_flag = cpp_state["flags"].get(flag, False)
        j_flag = java_state["flags"].get(flag, False)
        o_flag = ocaml_state["flags"].get(flag, False)
        if c_flag != j_flag or c_flag != o_flag:
            diffs.append(f"Flag {flag.upper()} mismatch: C++={c_flag}, Java={j_flag}, OCaml={o_flag}")
            
    # Compare Registers
    for i in range(64):
        reg = f"R{i}"
        c_val = cpp_state["registers"].get(reg, 0)
        j_val = java_state["registers"].get(reg, 0)
        o_val = ocaml_state["registers"].get(reg, 0)
        if c_val != j_val or c_val != o_val:
            diffs.append(f"{reg} mismatch: C++={c_val}, Java={j_val}, OCaml={o_val}")
            
    return diffs

def main():
    print(f"{BOLD}{BLUE}==============================================================={RESET}")
    print(f"{BOLD}{BLUE} ImpulseVM Three-Way Polyglot Validation Suite                 {RESET}")
    print(f"{BOLD}{BLUE} C++ vs Java 25 vs OCaml (Oracle)                              {RESET}")
    print(f"{BOLD}{BLUE}==============================================================={RESET}\n")

    lib = load_native_library()
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

    spec_dir = Path(__file__).resolve().parent.parent
    test_dir = spec_dir / "test-vectors" / "vm-impas"
    if len(sys.argv) > 1:
        pattern = sys.argv[1]
        impas_files = [f for f in test_dir.glob("**/*.impas") if pattern in str(f)]
    else:
        impas_files = list(test_dir.glob("**/*.impas"))

    # Generate Java classpath dynamically
    java_dir = Path(__file__).resolve().parent.parent.parent / "impulse-graph-java"
    cp_file = java_dir / "impulse-vm" / "cp.txt"
    if not cp_file.exists():
        print(f"{YELLOW}Generating Maven classpath...{RESET}")
        subprocess.run(["mvn", "dependency:build-classpath", "-Dmdep.outputFile=cp.txt", "-pl", "impulse-vm"], cwd=java_dir, check=True, stdout=subprocess.DEVNULL)
        
    with open(cp_file, "r") as f:
        maven_cp = f.read().strip()
        
    cp = f"impulse-vm/target/classes:impulse-vm/target/test-classes:impulse-api/target/classes:impulse-storage/target/classes:impulse-spec/target/classes:{maven_cp}"

    passed_count = 0
    failed_count = 0
    skipped_count = 0

    for test_file in sorted(impas_files):
        rel_path = test_file.relative_to(spec_dir)
        print(f"Testing {rel_path}...", flush=True)
        try:
            cpp_state = run_cpp(lib, test_file)
            if not cpp_state:
                print(f"{YELLOW}[SKIP]{RESET} {rel_path} (Empty or no executable instructions)")
                skipped_count += 1
                continue
                
            java_state = run_java(test_file, cp)
            ocaml_state = run_ocaml(test_file)
            
            diffs = compare_state(cpp_state, java_state, ocaml_state)
            
            if not diffs:
                print(f"{GREEN}[PASS]{RESET} {rel_path} (All 3 match)")
                passed_count += 1
            else:
                print(f"{RED}[FAIL]{RESET} {rel_path}")
                for d in diffs:
                    print(f"       -> {RED}{d}{RESET}")
                failed_count += 1
                
        except Exception as e:
            print(f"{RED}[ERROR]{RESET} {rel_path}: {e}")
            failed_count += 1

    print(f"\n{BOLD}{BLUE}==============================================================={RESET}")
    print(f"{BOLD}Total Test Files Examined:{RESET} {len(impas_files)}")
    print(f"{BOLD}{GREEN}Passed (Identical):{RESET} {passed_count}")
    print(f"{BOLD}{RED}Failed (Mismatch/Error):{RESET} {failed_count}")
    print(f"{BOLD}{YELLOW}Skipped:{RESET} {skipped_count}")

    if failed_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
