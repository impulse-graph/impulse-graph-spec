# Future Optimization & Research Specification (`impulse-vm`)

> **Exploratory Architecture Research & Optimization Todo**  
> *Status: Draft Investigation & Research Blueprint*

This document details future advanced performance optimization candidates, algorithmic trade-off analyses, and implementation difficulty metrics for the **Impulse Graph Bytecode Virtual Machine (`impulse-vm`)**.

---

## 1. Range-Partitioned Writing with Thread-Local Spill Buffers (Roaring)

### 1.1 Problem Statement: The Thread Contention & Random Access Bottleneck
When multi-threaded graph traversals (e.g. parallel BFS or SIMD candidate expansion in `impulse-vm`) discover destination nodes, writing targets into a single shared or unpartitioned `RoaringBitmap` creates severe performance degradation:

1. **Random Container Invalidation**: Target node IDs in general graphs are randomly distributed across the 32-bit/64-bit ID keyspace. Appending randomly into a standard `RoaringBitmap` forces continuous binary searches over chunk key arrays (`keys[]`), container type promotions (Array $\to$ Bitset), and CPU cache line invalidation.
2. **Lock / Merge Contention**: Shared global bitmaps require fine-grained striped locks. Unpartitioned thread-local bitmaps require expensive $O(N)$ multi-way merge reductions at the end of every traversal step.

---

### 1.2 Proposed Architecture: Range-Partitioned Thread-Local Spill Buffers

To achieve lock-free parallel set construction with sub-nanosecond amortized insertion cost, `impulse-vm` explores **Range-Partitioned Writing with Thread-Local Spill Buffers**:

```
+---------------------------------------------------------------------------------------+
|                                  Thread Worker i                                      |
|                                                                                       |
|  OP_CSR_WALK Targets  -->  Partition Hash/Shift (NodeID >>> 16)                       |
|                                     │                                                 |
|                                     ├──> Range 0 Buffer [NodeID_1, NodeID_5, ...]       |
|                                     ├──> Range 1 Buffer [NodeID_65538, ...]             |
|                                     └──> Range M Buffer [ ... ]                       |
|                                             │ (When Buffer Fills: BUF_SIZE = 512)     |
|                                             ▼                                         |
|                                    Bulk Sort & Direct Insert                          |
|                                             │                                         |
+---------------------------------------------│-----------------------------------------+
                                              ▼
                +-----------------------------------------------------------+
                |          Partitioned Roaring Bitmap Containers            |
                |                                                           |
                |   Partition 0 (Chunk 0..65535)    -->  Roaring Container 0 |
                |   Partition 1 (Chunk 65536..)     -->  Roaring Container 1 |
                +-----------------------------------------------------------+
```

#### Mechanism Overview:
1. **Keyspace Partitioning**: The total node index space is divided into $M$ disjoint range partitions matching Roaring 64K ($2^{16}$) chunk boundaries ($M = \lceil N_{\text{max}} / 65536 \rceil$).
2. **Thread-Local Spill Buffers**: Each worker thread in `VmQueryContext` holds a fixed-size ring of small thread-local off-heap arrays: `uint16_t spill_buffers[M][BUF_SIZE]` (where `BUF_SIZE` = 256 or 512 elements).
3. **Lock-Free Append**: During `OP_CSR_WALK`, as target node IDs are traversed, the low 16 bits of the `NodeID` are appended directly to `spill_buffers[NodeID >>> 16]` in $O(1)$ CPU cycle instructions without taking any locks.
4. **Bulk Sort & Vectorized Spill**: When a thread's spill buffer for Range $m$ reaches capacity (`BUF_SIZE` = 512):
   - The thread sorts the 512 elements using SIMD bitonic sort ($O(B \log B)$ in CPU registers).
   - The sorted buffer is appended to Range Partition $m$'s Roaring container via direct linear bulk insertion (`RoaringBitmap.addMany`), eliminating key lookup search overhead entirely.

---

### 1.3 Algorithmic Complexity Analysis

| Operation | Standard Unpartitioned Insert | Range-Partitioned Spill Writing | Speedup Rationale |
| :--- | :--- | :--- | :--- |
| **Per-Element Append Time** | $O(\log C + \log E)$ (Key binary search + container insert) | **$O(1)$ amortized** (Direct array write to thread-local buffer) | Eliminates key lookup per element |
| **Container Sort & Flush** | N/A (Repeated single inserts) | **$O(B \log B)$ in SIMD registers** for 512 elements | Bitonic vector sort on L1 cache |
| **Multi-Thread Merge Time** | $O(T \cdot K)$ where $T$ = threads, $K$ = keys | **$O(K)$ lock-free linear concatenation** | Disjoint partitions merge in parallel |
| **Total Time Complexity** | $O(k \log C)$ | **$O(k + \frac{k}{B} \cdot B \log B)$** | Amortized linear time $O(k)$ |

---

### 1.4 Frontier Cardinality Size Optimization Heuristics

To maximize traversal execution speed, `ImpulseVmCompiler` and the VM interpreter loop use dynamic cardinality thresholds to select the optimal intermediate set structure:

```
                          Active Frontier Cardinality (k)
       1                  1,024                100,000            0.05 * N_max
       +--------------------+--------------------+--------------------+
Tier:  |  TYPE_NODE_VECTOR  | Range-Partitioned  | Flat Off-Heap      |
       |  (Raw uint64[])    | Spill Roaring      | BitSet (AVX-512)   |
       +--------------------+--------------------+--------------------+
```

#### Adaptive Switching Rules:
1. **Tier 1: Small Frontiers ($k \le 1,024$) $\implies$ `TYPE_NODE_VECTOR`**:
   - Bypass all Roaring structures and spill buffers.
   - Use raw contiguous `uint64_t[]` buffers in `VmQueryContext`. Operates with zero encoding overhead.
2. **Tier 2: Medium & Sparse Frontiers ($1,024 < k < 100,000$ and $N > 10^7$) $\implies$ Range-Partitioned Spill Roaring**:
   - Activate Thread-Local Spill Buffers.
   - Converts targets into compressed Array / RLE Roaring containers. Saves 100x+ memory while maintaining high insertion throughput.
3. **Tier 3: High Density Frontiers ($k / N_{\text{max}} > 5\%$) $\implies$ `TYPE_BITSET_HANDLE`**:
   - When active node density exceeds 5%, switch automatically to flat off-heap bitsets (`BitSet`).
   - Enables pure AVX-512 vector bitwise operations (`_mm512_or_si512`) across memory words.

---

### 1.5 VM Implementation Difficulty & Work Breakdown

| Implementation Phase | Difficulty | Key Technical Challenge |
| :--- | :--- | :--- |
| **`VmQueryContext` Spill Memory Layout** | **Low** | Pre-allocate fixed `spill_buffers[M][512]` arrays in thread-local arena (`64-byte` aligned). |
| **SIMD Bitonic Sort for 512-elem Buffers** | **Medium** | Write AVX2/AVX-512 bitonic sort kernel in C++ / Java Vector API to sort 512 `uint16_t`s. |
| **VM Instruction Set Extensions** | **Medium** | Define `OP_SPILL_PUSH`, `OP_SPILL_FLUSH`, and `OP_SPILL_REDUCE` bytecodes in `BYTECODE_INSTRUCTION_SET.md`. |
| **Dynamic Heuristic Compiler Pass** | **High** | Implement runtime feedback monitoring in `ImpulseVmCompiler` to dynamically switch register type tags. |

---

### 1.6 Evaluation & Benchmark Plan

To validate this optimization candidate, the following benchmarks must be implemented in `impulse-benchmarks`:

1. **Insertion Throughput (MTEPS)**: Measure million target insertions per second comparing:
   - Direct `RoaringBitmap.add()`
   - Thread-local `RoaringBitmap` + `FastAggregation.or()`
   - Range-Partitioned Spill Buffer writing.
2. **CPU L1/L3 Cache Miss Rates**: Validate reduction in L1/L3 cache misses using hardware performance counters (`perf_event_open` / JMH perfasm).
3. **Scale Stress Test**: Test on $N = 10^8$ and $N = 10^9$ synthetic power-law graphs with varying thread counts (8, 16, 32, 64 worker threads).

---

## 2. Advanced Column Index Encodings for CSR & CSC Traversal

### 2.1 Problem Rationale & Memory Bandwidth Wall
In graph query engines, the primary hardware bottleneck during forward (CSR - Compressed Sparse Row) and reverse (CSC - Compressed Sparse Column) traversals is **Memory Bus Bandwidth**. When executing `OP_CSR_WALK` or `OP_CSC_WALK`, the virtual machine continuously streams target node ID arrays (`colIndices[]` / `targets[]`) from off-heap memory.

Standard uncompressed 32-bit (`uint32_t`) or 64-bit (`uint64_t`) target arrays consume **4 to 8 bytes per edge**. Advanced column encodings aim to compress `colIndices[]` to **1.0–2.5 bytes per edge** while enabling SIMD vector bit-unpacking directly inside hot execution loops.

---

### 2.2 Encoding Taxonomy & Comparative Analysis

```
                                  CSR / CSC Column Index Encodings
                                                │
         ┌───────────────────────┬──────────────┴────────┬──────────────────────┐
         ▼                       ▼                       ▼                      ▼
    [ SIMDComp ]         [ Sliced ELLPACK ]     [ Faro Shuffle ]       [ Delta-VByte ]
(128-int Bit-Packing)   (Warp/Row Matrix Alignment) (Bit-Plane Interleaving) (Frame-of-Reference)
```

#### 1. SIMDComp (SIMD Bit-Packing)
* **Mechanism**: Partitions `colIndices[]` into fixed 128-integer blocks. For each block, computes bit-width $b = \lceil \log_2(\max(colIndices) + 1) \rceil$ and packs 128 integers into $128 \times b$ bits using AVX-512 / ARM Neon SIMD bit-packing intrinsics (`simdpack128` / `simdunpack128`).
* **CSR/CSC Traversal Speedup**: **2.5x–4x footprint reduction**. AVX-512 vector units unpack 128 target node IDs into registers in ~0.8 ns, eliminating memory bus bandwidth bottlenecks.

#### 2. Sliced ELLPACK (ELLPACK-R Matrix Encoding)
* **Mechanism**: Slices CSR/CSC matrices into fixed row blocks (e.g. 32 or 64 rows per slice matching GPU warp size or AVX-512 vector width). Equalizes row lengths within each slice using minimal padding ($K_{\text{slice}} = \max(\text{degree in slice})$).
* **CSR/CSC Traversal Speedup**: **Eliminates row offset arrays (`offsets[]`) entirely**. Enables GPU warp coalescing and AVX-512 vector gather instructions (`vpgatherd`) without row pointer indirection. Ideal for uniform degree graphs, GNN neighborhood sampling (`impulse-gnn`), and Powergrid SIMD analysis (`impulse-powergrid`).

#### 3. Faro Shuffle Encoding (Bit-Plane Interleaving)
* **Mechanism**: Inspired by the Faro card shuffle, Faro encoding interleaves bit-planes across target column indices (grouping high-order bit planes separately from low-order bit planes across 128-element blocks).
* **CSR/CSC Traversal Speedup**: Allows early SIMD block elimination: if the high-order bit-plane of a 128-element block does not match the target search predicate, the entire 128-element column block is skipped in **1 CPU cycle** without decoding. Ideal for set-intersection heavy graph queries.

#### 4. Delta-VByte (Delta Frame-of-Reference)
* **Mechanism**: Encodes sorted neighbor lists as differential gaps: $\Delta_i = colIndices[i] - colIndices[i-1]$. Applies variable-byte (VByte) or 4-bit nibble packing (Group VByte) to compress small delta gaps.
* **CSR/CSC Traversal Speedup**: **2x–3.5x compression ratio**. Excellent for highly skewed power-law graphs with large dense node degrees where consecutive target IDs are strongly clustered.

---

### 2.3 Encoding Comparison & Hardware Parity Matrix

| Encoding Candidate | Target Compression | Unpack Latency (128 items) | Hardware Acceleration Target | Best CSR / CSC Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **SIMDComp** | **2.5x – 4.0x** | **~0.8 ns** | AVX-512 / ARM Neon | General-purpose CSR & CSC `colIndices[]` |
| **Sliced ELLPACK** | 1.2x – 1.8x | **~0.1 ns** (Direct index) | NVIDIA CUDA / AMD HIP / AVX-512 | GNN Sampling & Dense SIMD Grid Solvers |
| **Faro Shuffle** | **3.0x – 5.0x** | **~1.5 ns** | SIMD Bit-Plane Skips | Multi-relation & ReBAC Set Intersections |
| **Delta-VByte** | 2.0x – 3.5x | ~2.5 ns | CPU Scalar / Group VByte | Ultra-large power-law graphs ($N > 10^9$) |

---

### 2.4 Integration into `impulse-vm` & Binary Snapshot Format v2.4

#### 1. Binary Snapshot Specification (`impulse-graph-spec`)
Section 3 (Compressed CSR/CSC Topology) of the binary snapshot specification supports explicit encoding flag identifiers:

```yaml
# Encoding Mode Identifiers (impulse-graph-spec Section 3)
IMPULSE_ENC_RAW_UINT32:       0x00
IMPULSE_ENC_RAW_UINT64:       0x01
IMPULSE_ENC_SIMDCOMP:         0x02
IMPULSE_ENC_SLICED_ELLPACK:   0x05
IMPULSE_ENC_FARO_SHUFFLE:     0x08
IMPULSE_ENC_DELTA_VBYTE:      0x09
```

#### 2. Bytecode Engine Execution Path (`impulse-vm`)
Inside `OP_CSR_WALK` and `OP_CSC_WALK`, the interpreter checks the pre-indexed `BoundRelationSlot` encoding tag to dispatch to specialized SIMD unpack loops:

```cpp
// C++ Computed-Goto Interpreter Loop Dispatch (Non-executable spec)
op_CSR_WALK: {
    uint8_t reg_dest = READ_REG_A();
    uint8_t reg_src  = READ_REG_B();
    uint16_t rel_id  = READ_REL_ID();

    const BoundRelationSlot& slot = active_snapshot->slots[rel_id];
    switch (slot.encoding_type) {
        case IMPULSE_ENC_SIMDCOMP:
            simdcomp_unpack_and_walk(slot, reg_src, reg_dest);
            break;
        case IMPULSE_ENC_SLICED_ELLPACK:
            ellpack_vector_walk(slot, reg_src, reg_dest);
            break;
        case IMPULSE_ENC_FARO_SHUFFLE:
            faro_bitplane_filter_walk(slot, reg_src, reg_dest);
            break;
        default:
            raw_csr_walk(slot, reg_src, reg_dest);
            break;
    }
    DISPATCH();
}
```

---

### 2.5 Implementation Roadmap & Evaluation Plan

1. **Benchmark Suite (`impulse-benchmarks`)**:
   - Measure decompression throughput (MTEPS) vs memory bandwidth consumption across synthetic graphs (R-MAT, Erdos-Renyi, Western North American Powergrid).
   - Evaluate SIMDComp vs Sliced ELLPACK unpack speeds on x86-64 AVX-512, ARM64 Neon, and Apple M-series chips.
2. **Compiler Tooling Integration (`impulse-graph-tooling`)**:
   - Update `impulse-compile` streaming binary compiler to support `--col-encoding=simdcomp|ellpack|faro|delta-vbyte`.
