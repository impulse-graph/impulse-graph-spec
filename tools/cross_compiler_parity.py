#!/usr/bin/env python3

import sys
import subprocess
import json
from pathlib import Path

import ctypes
import os

def run_cpp_compiler(type_name, cel_expr):
    cpp_dir = Path(__file__).resolve().parent.parent.parent / "impulse-graph-core" / "impulse-cpp" / "build_temp"
    
    # Load dylib
    if sys.platform == 'darwin':
        lib_path = cpp_dir / "libimpulse_graph.dylib"
    elif sys.platform == 'win32':
        lib_path = cpp_dir / "impulse_graph.dll"
    else:
        lib_path = cpp_dir / "libimpulse_graph.so"
        
    lib = ctypes.CDLL(str(lib_path))
    
    class CompiledQuery(ctypes.Structure):
        _fields_ = [
            ("bytecode", ctypes.POINTER(ctypes.c_uint8)),
            ("bytecode_length", ctypes.c_size_t),
            ("instruction_count", ctypes.c_size_t),
        ]
        
    lib.impulse_compile_cel.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.POINTER(CompiledQuery))]
    lib.impulse_compile_cel.restype = ctypes.c_int
    
    lib.impulse_compiled_query_destroy.argtypes = [ctypes.POINTER(CompiledQuery)]
    lib.impulse_compiled_query_destroy.restype = None
    
    is_proj = 1 if type_name == "project" else 0
    
    out_query = ctypes.POINTER(CompiledQuery)()
    res = lib.impulse_compile_cel(cel_expr.encode('utf-8'), is_proj, ctypes.byref(out_query))
    if res != 0:
        raise Exception(f"C++ Compilation failed with code {res}")
        
    query = out_query.contents
    bytecode_bytes = bytes(query.bytecode[:query.bytecode_length])
    
    hex_str = "".join([f"{b:02x}" for b in bytecode_bytes])
    
    lib.impulse_compiled_query_destroy(out_query)
    
    return hex_str


def run_java_compiler(type_name, cel_expr):
    java_dir = Path(__file__).resolve().parent.parent.parent / "impulse-graph-java"
    cp = (
        "impulse-compiler/target/classes:"
        "impulse-vm/target/classes:"
        "impulse-api/target/classes:"
        "impulse-core/target/classes:"
        "impulse-storage/target/classes"
    )
    cmd = [
        "java",
        "--add-modules", "jdk.incubator.vector",
        "-cp", cp,
        "org.impulsegraph.compiler.harness.CrossCompilerParityHarness",
        type_name,
        cel_expr
    ]
    res = subprocess.run(cmd, cwd=java_dir, capture_output=True, text=True)
    if res.returncode != 0:
        raise Exception(f"Java compilation failed: {res.stderr}\n{res.stdout}")
    
    # Filter out JVM warnings
    for line in res.stdout.split('\n'):
        if line.startswith('{'):
            return json.loads(line)
    
    raise Exception(f"No JSON found in Java output: {res.stdout}")

def main():
    test_expressions = [
        ("filter", "age > 21"),
        ("project", "state.fuel:MIN = (src.cargo * 0.05 + 1.0) * edge.distance"),
        ("filter", "sqrt(edge.val) < 25.0"),
        ("project", "state.visited:OR = src.visited | (1 << node.id)")
    ]
    
    print("===============================================================")
    print(" ImpulseVM Cross-Compiler Parity Validation Harness")
    print("===============================================================")
    
    passed = 0
    
    for type_name, expr in test_expressions:
        print(f"Testing CEL ({type_name}): {expr}")
        
        try:
            java_res = run_java_compiler(type_name, expr)
            if java_res.get("status") != "ok":
                print(f"  [ERROR] Java failed: {java_res.get('error')}")
                continue
                
            java_hex = java_res["hex"]
            print(f"  [JAVA] {java_hex}")
            
            cpp_hex = run_cpp_compiler(type_name, expr)
            
            if java_hex == cpp_hex:
                print(f"  [PASS] Byte-for-byte identical")
                passed += 1
            else:
                print(f"  [FAIL] Mismatch!")
                print(f"  [CPP ] {cpp_hex}")
                
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("===============================================================")
    print(f"Passed {passed}/{len(test_expressions)}")
    
if __name__ == "__main__":
    main()
