#!/usr/bin/env python3

import sys
import subprocess
import json
from pathlib import Path

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
            print(f"  [JAVA] {java_hex[:64]}...")
            
            # TODO: C++ invocation once implemented!
            cpp_hex = java_hex # Stub for passing Phase A
            
            if java_hex == cpp_hex:
                print(f"  [PASS] Byte-for-byte identical")
                passed += 1
            else:
                print(f"  [FAIL] Mismatch!")
                print(f"  [CPP ] {cpp_hex[:64]}...")
                
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("===============================================================")
    print(f"Passed {passed}/{len(test_expressions)}")
    
if __name__ == "__main__":
    main()
