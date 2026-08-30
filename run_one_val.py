import subprocess
import sys
impas = "test-vectors/vm-impas/04_graph_and_matrix/tc09_traversals_pos.impas"

cmd1 = ["../impulse-graph-core/impulse-cpp/build/tools/vm_test_runner", impas]
res_cpp = subprocess.run(cmd1, capture_output=True, text=True)

cmd2 = ["python3", "tools/run_vm_asm_suite.py", impas]
res_java = subprocess.run(cmd2, capture_output=True, text=True)

print("C++ OUT:")
print(res_cpp.stdout)
print("----------------")
print("Java OUT:")
print(res_java.stdout)
