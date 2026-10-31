# C# / .NET Execution Engine Specification (`impulse-vm`)

This document details the compatibility between `impulse-vm` and the .NET Common Intermediate Language (CIL / CLR), off-heap memory management via `Span<T>` and `System.Runtime.Intrinsics`, dynamic IL compilation (`DynamicMethod`), and non-executable sample code for the **C# / .NET 9+ Engine Target**.

---

## 1. CIL Compatibility & Architectural Mapping

While the .NET Common Intermediate Language (CIL / ECMA-335) is fundamentally a **stack-based virtual machine**, `impulse-vm` is a **64-bit register-based virtual machine** (`R0`..`R63`).

This architectural difference is an advantage: modern .NET JIT compilers (RyuJIT) translate stack operations into CPU registers. Mapping `impulse-vm`'s fixed registers (`R0`..`R63`) to C# `ref struct` slots allows RyuJIT to perform direct hardware register allocation.

```
+-----------------------------------------------------------------------------------------+
| Feature              | Java 25 FFM Target            | C# / .NET 9+ Target              |
+----------------------+-------------------------------+----------------------------------+
| Off-Heap Memory      | `java.lang.foreign.MemorySegment` | `System.Span<T>` / `byte*` Pointers |
| SIMD Intrinsics      | `java.util.vector.VectorAPI`  | `System.Runtime.Intrinsics.Arm/X86` |
| JIT Inlining Target  | `java.lang.invoke.MethodHandle`| `System.Reflection.Emit.DynamicMethod` |
| Zero-GC Abstraction | `MemoryArena`                 | `ref struct` / `NativeMemory`    |
| Package Target       | Maven (`impulse-core`)        | NuGet (`ImpulseGraph.VM`)        |
+----------------------+-------------------------------+----------------------------------+
```

### 1.1 P/Invoke Native C++ Wrapper vs. Pure Managed C# Engine

A core design question for .NET is: **"Why build a pure C# engine when we can simply P/Invoke the native C++ engine?"**

Both approaches offer distinct trade-offs:

| Evaluation Criteria | Option A: Native C++ P/Invoke (`[LibraryImport]`) | Option B: Pure Managed C# Engine (`ImpulseGraph.VM`) |
| :--- | :--- | :--- |
| **Code Maintenance** | **100% Shared C++ Code**: Single C++ kernel maintained across Python, Node.js, C#, C++. | Dual C++/C# code maintenance for VM opcodes. |
| **Call Transition Overhead** | **~5 to 15 ns per P/Invoke call** (Managed-to-Native transition frame overhead). | **0 ns transition overhead** (Runs 100% in-proc in managed CLR stack). |
| **Micro-Query Latency** | Adds 15 ns to a 45 ns query (**~33% latency penalty** for ultra-fast queries). | **Sub-microsecond (< 45 ns)** with zero boundary transitions. |
| **Cross-Platform Deployment** | Requires packaging native shared libraries (`.so`, `.dylib`, `.dll`) per OS/arch. | **100% Portable**: Single pure .NET DLL runs on Windows, Linux, macOS, and WebAssembly (WASM). |
| **Process Crash Safety** | A C++ null-pointer segment violation crashes the entire `dotnet` process. | Throws standard C# `NullReferenceException` catchable by managed code. |

#### Recommended Hybrid Strategy
In enterprise .NET deployments (`impulse-platform`), `ImpulseGraph.VM` supports **both modes**:
1. **P/Invoke High-Throughput Path (`ImpulseGraph.Native`)**: Uses `[LibraryImport]` for bulk macro-analytic queries (PageRank, BFS) where native C++ computed `goto` and vectorization dominate execution time.
2. **Pure Managed C# Path (`ImpulseGraph.VM`)**: Uses `DynamicMethod` / `Span<T>` for ultra-fast micro-queries (<50 ns), serverless deployments, or WebAssembly (Blazor/WASM) environments where native `.dll`/`.so` binaries cannot be loaded.


---

## 2. C# Engine Execution Mechanics

The C# / .NET port (`ImpulseGraph.VM`) implements two execution strategies:

### 2.1 Strategy A: Zero-Allocation `ref struct` Interpreter Loop
A fast, zero-GC interpreter loop using `ReadOnlySpan<byte>` for instruction decoding and `Unsafe` memory dereferencing over off-heap memory-mapped `.imps` files.

### 2.2 Strategy B: `DynamicMethod` CIL JIT Compiler
Translates a 64-bit `.impb` bytecode program into an inlined CIL `DynamicMethod` at runtime using `ILGenerator`. RyuJIT compiles the generated CIL into direct, unmanaged x86-64 / ARM64 machine code with **zero loop dispatch overhead**.

---

## 3. Hardware SIMD Intrinsics & Zero-GC Memory Management

### 3.1 AVX-512 / ARM Neon Hardware Acceleration
C# in .NET 9/10 exposes zero-overhead SIMD vector intrinsics via `System.Runtime.Intrinsics.X86` and `System.Runtime.Intrinsics.Arm`:

```csharp
// Sample C# SIMD Bitwise OR for OP_SET_UNION (Non-executable illustrative spec)
using System.Runtime.Intrinsics.X86;

public static unsafe void VectorUnion(ulong* dst, ulong* src, int qwordCount) {
    int i = 0;
    if (Avx512F.IsSupported) {
        for (; i <= qwordCount - 8; i += 8) {
            Vector512<ulong> vDst = Avx512F.LoadVector512(dst + i);
            Vector512<ulong> vSrc = Avx512F.LoadVector512(src + i);
            Vector512<ulong> vRes = Avx512F.Or(vDst, vSrc);
            Avx512F.Store(dst + i, vRes);
        }
    }
    // Fallback scalar loop for remainder
    for (; i < qwordCount; i++) {
        dst[i] |= src[i];
    }
}
```

### 3.2 Off-Heap `ref struct` Scratchpad (`VmQueryContext`)
`VmQueryContext` in C# allocates scratchpad arenas using `System.Runtime.InteropServices.NativeMemory.AllocZeroed()`, completely bypassing the .NET Garbage Collector (GC):

```csharp
// Sample C# VmState Layout (Non-executable illustrative spec)
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential, Size = 640)]
public unsafe struct VmState {
    public uint Pc;
    public uint Reserved;
    public ulong Flags;
    public fixed ulong Registers[64];
    public fixed byte RegisterTypes[64];
    public void* QueryContextPtr;
}
```

---

## 4. Non-Executable Sample Code: `DynamicMethod` CIL Compiler

The following sample illustrates how `ImpulseVmCompiler` in C# compiles bytecode into a dynamic CIL delegate.

```csharp
// Sample C# DynamicMethod Compiler (Non-executable illustrative spec)
namespace ImpulseGraph.VM;

using System;
using System.Reflection.Emit;

public unsafe static class ImpulseCilCompiler {

    public delegate long QueryExecutionDelegate(VmState* state, void* snapshotPtr, void* inputPtr);

    public static QueryExecutionDelegate Compile(ReadOnlySpan<byte> bytecodeSpan) {
        DynamicMethod dm = new DynamicMethod(
            "ImpulseCompiledQuery",
            typeof(long),
            new[] { typeof(VmState*), typeof(void*), typeof(void*) },
            typeof(ImpulseCilCompiler).Module,
            skipVisibility: true
        );

        ILGenerator il = dm.GetILGenerator();

        int instructionCount = bytecodeSpan.Length / 8;
        fixed (byte* ptr = bytecodeSpan) {
            ulong* words = (ulong*)ptr;
            for (int i = 0; i < instructionCount; i++) {
                ulong inst = words[i];
                byte opcode = (byte)(inst & 0xFF);
                ushort dstReg = (ushort)((inst >> 16) & 0xFFFF);
                uint payload = (uint)((inst >> 32) & 0xFFFFFFFF);

                switch (opcode) {
                    case 0x01: // OP_INIT_INPUT_NODE
                        il.Emit(OpCodes.Ldarg_0); // VmState*
                        il.Emit(OpCodes.Ldc_I4, (int)dstReg);
                        il.Emit(OpCodes.Ldarg_2); // inputPtr
                        il.EmitCall(OpCodes.Call, typeof(VmHandlers).GetMethod("InitInputNode")!, null);
                        break;

                    case 0x10: // OP_CSR_WALK
                        il.Emit(OpCodes.Ldarg_0);
                        il.Emit(OpCodes.Ldarg_1); // snapshotPtr
                        il.Emit(OpCodes.Ldc_I4, (int)dstReg);
                        il.Emit(OpCodes.Ldc_I4, (int)payload); // srcReg / relId
                        il.EmitCall(OpCodes.Call, typeof(VmHandlers).GetMethod("CsrWalk")!, null);
                        break;

                    case 0xFF: // OP_HALT
                        il.Emit(OpCodes.Ldarg_0);
                        il.EmitCall(OpCodes.Call, typeof(VmHandlers).GetMethod("GetReturnRegister")!, null);
                        il.Emit(OpCodes.Ret);
                        break;
                }
            }
        }

        return (QueryExecutionDelegate)dm.CreateDelegate(typeof(QueryExecutionDelegate));
    }
}
```

---

## 5. Ecosystem & NuGet Distribution Plan

The C# / .NET port is packaged as part of the standard multi-platform matrix:

1. **`ImpulseGraph.VM`**: Pure C# managed runtime library containing `ImpulseCilCompiler`, `ref struct` state helpers, and `DynamicMethod` emitters.
2. **`ImpulseGraph.Native`**: Cross-platform native binary wrappers linking `libimpulse_graph_static.a` / `.dll` via `LibraryImport` (`P/Invoke`).
3. **`ImpulseGraph`**: High-level fluent API (`ImpulseGraphQuery.Builder()`) providing compile-time type-checked query building for .NET developers.

---

## 6. Performance Projections & JIT Fusion Benchmark Ranking

Why does managed JIT execution (Java 25 `MethodHandle` and C# `DynamicMethod`) outperform baseline C++ interpreter loops?

```
+----------------------------------------------------------------------------------------------------+
| Traditional C++ Computed-goto Interpreter:                                                         |
|   [op_INIT] -> goto *table[op1] -> [op_WALK_1] -> goto *table[op2] -> [op_WALK_2] -> goto *table[op3] |
|   (Label-to-label jumps cause i-cache jumps & register reloading)                                  |
+----------------------------------------------------------------------------------------------------+
                                                vs
+----------------------------------------------------------------------------------------------------+
| Managed JIT Pipeline Fusion (Java 25 MethodHandle / C# DynamicMethod):                              |
|   [ Single Inlined Native Machine Code Block: Load -> AVX512_Or -> AVX512_Or -> Return ]           |
|   (Zero dispatch overhead: RyuJIT / C2 JIT fuses all opcodes into a single contiguous block)       |
+----------------------------------------------------------------------------------------------------+
```

### 6.1 Projected Benchmark Ranking (3-Hop Reachability Traversal)

| Execution Runtime Engine | Instruction Dispatch Architecture | Projected 3-Hop Micro-Query Latency | Performance Rank |
| :--- | :--- | :--- | :--- |
| **Pure C# (`DynamicMethod` + RyuJIT)** | **Pipeline Fusion (CIL JIT)** | **~35 ns - 42 ns** | 🥇 **#1 (Fastest)** |
| **Java 25 (`MethodHandle` Fusion)** | **Pipeline Fusion (C2 JIT)** | **~38 ns - 45 ns** | 🥈 **#2** |
| **C++ Computed `goto` (GCC/Clang)** | **Indirect Threading (`&&label`)**| **~48 ns - 55 ns** | 🥉 **#3** |
| **C++ Standard `switch` (MSVC)** | **Monolithic `switch` Loop** | **~75 ns - 95 ns** | 🏅 **#4** |
| **Baseline Java AST Visitor** | **Recursive Step Evaluation** | **~850 ns** | 🎖️ **Baseline** |

### 6.2 Why Pure C# RyuJIT Is Projected to Take #1

1. **Pipeline Fusion**: `DynamicMethod` compiles the entire query pipeline into a single CIL method. .NET RyuJIT inlines the whole query into a single contiguous native assembly block (**0 ns loop dispatch**).
2. **Zero Bounds Checking**: `ref struct` and raw pointers (`byte*`, `Unsafe.Add`) allow RyuJIT to emit bare-metal memory dereferences without Java's FFM bounds check heuristics.
3. **Deterministic AVX-512 Hardware Intrinsics**: `System.Runtime.Intrinsics.X86.Avx512F` calls translate directly to native vector machine instructions with zero JIT auto-vectorizer uncertainty.
