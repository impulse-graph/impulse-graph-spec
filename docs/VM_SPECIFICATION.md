# Normative Specification: ImpulseVM Virtual Machine & ImpOps Instruction Set

* **Specification Version**: 0.9.0
* **Document Status**: Standard Reference Specification
* **Target Architecture**: 64-bit Register-based Virtual Machine (off-heap execution focus)

This document defines the formal normative specification for the **ImpulseVM** register machine and its register type system, execution state layout, status flags, and the **ImpOps** bytecode instruction set. All implementations of the ImpulseVM and associated assemblers/compilers **MUST** comply with this specification.

---

## 1. Terminology & Compliance (RFC 2119)

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

---

## 2. Virtual Machine Register Architecture

The ImpulseVM is a register-based virtual machine operating on a bank of general-purpose and specialized registers.

### 2.1 General-Purpose Registers
- The VM **MUST** expose exactly 64 general-purpose registers, designated `R0` through `R63`.
- Each register is exactly 64 bits wide and **SHALL** store a 64-bit integer, float, pointer, or off-heap object handle.
- Each register **MUST** have an associated 8-bit type tag (see §2.4) that defines the semantic interpretation of the 64-bit value.

### 2.2 Program Counter (PC)
- The execution context **MUST** maintain a 32-bit unsigned Program Counter (`pc`).
- The `pc` register represents the zero-indexed instruction array offset to be executed next.

### 2.3 Status Flags Register (FLAGS)
The execution state **MUST** maintain a 64-bit status flags register (`flags`). The lower bits are mapped as follows:

| Bit Index | Flag | Constant Name | Semantic Description |
| :--- | :--- | :--- | :--- |
| `Bit 0` | **ZF** | `IMPULSE_VM_FLAG_ZF` | Zero Flag: Set if candidate set or arithmetic result is empty / zero. |
| `Bit 1` | **LT** | `IMPULSE_VM_FLAG_LT` | Less Than Flag: Set if comparison result is strictly less than. |
| `Bit 2` | **GT** | `IMPULSE_VM_FLAG_GT` | Greater Than Flag: Set if comparison result is strictly greater than. |
| `Bit 3` | **EQ** | `IMPULSE_VM_FLAG_EQ` | Equal Flag: Set if comparison result is equal. |
| `Bit 4` | **ST** | `IMPULSE_VM_FLAG_ST` | Stable Flag: Set by convergence check operations. |

### 2.4 Register Type Tags
To ensure off-heap memory safety and prevent undefined behavior during FFI calls, the VM **MUST** perform strict dynamic type validation using the following 8-bit type tags:

| Value | Type Identifier | Register Type Description |
| :--- | :--- | :--- |
| `0x00` | `TYPE_NULL` | Empty, uninitialized, or invalid register state. |
| `0x01` | `TYPE_INT64` | 64-bit signed or unsigned integer value. |
| `0x02` | `TYPE_NODE_ID` | 64-bit unsigned unique node identifier. |
| `0x03` | `TYPE_RELATION_ID` | 16-bit unsigned relationship identifier. |
| `0x04` | `TYPE_BITSET_HANDLE` | Integer handle pointing to an off-heap BitSet. |
| `0x05` | `TYPE_NODE_VECTOR` | Integer handle pointing to an off-heap node array. |
| `0x06` | `TYPE_CSR_SPAN` | Direct memory span pointer matching CSR slice. |
| `0x07` | `TYPE_BOOLEAN` | Boolean flag (`0` = false, `1` = true). |
| `0x08` | `TYPE_FLOAT` | 32-bit IEEE 754 single-precision float constant. |
| `0x09` | `TYPE_DOUBLE` | 64-bit IEEE 754 double-precision float constant. |
| `0x0A` | `TYPE_VALUE_MAP` | Integer handle pointing to an off-heap hash map. |
| `0x0B` | `TYPE_STRING_VECTOR` | Integer handle pointing to an off-heap string array. |
| `0x0C` | `TYPE_FLOAT_VECTOR` | Integer handle pointing to an off-heap float array. |
| `0x0D` | `TYPE_DOUBLE_VECTOR` | Integer handle pointing to an off-heap double array. |
| `0x0E` | `TYPE_UINT64_VECTOR` | Integer handle pointing to an off-heap uint64 array. |

---

## 3. Physical Layout Specifications

### 3.1 VM Execution State Frame (`impulse_vm_state_t`)
The execution state frame **MUST** represent a contiguous 640-byte memory block, aligned to a 64-byte boundary. The fields are defined as follows:

| Byte Offset | C-ABI Type | Field Name | Description |
| :--- | :--- | :--- | :--- |
| `0x0000` – `0x0003` | `uint32_t` | `pc` | Program Counter offset. |
| `0x0004` – `0x0007` | `uint32_t` | `reserved` | Alignment padding (MUST be 0). |
| `0x0008` – `0x000F` | `uint64_t` | `flags` | Lower status flags register. |
| `0x0010` – `0x020F` | `uint64_t[64]` | `registers` | 64-bit general-purpose registers `R0`..`R63`. |
| `0x0210` – `0x024F` | `uint8_t[64]` | `register_types` | Associated type tags for `R0`..`R63`. |
| `0x0250` – `0x0257` | `void*` | `query_context` | Pointer to off-heap execution context. |
| `0x0258` – `0x0277` | `uint32_t[8]` | `call_stack` | 8-frame subroutine return stack. |
| `0x0278` – `0x027B` | `uint32_t` | `call_stack_depth` | Subroutine return stack pointer / depth. |
| `0x027C` – `0x027F` | `uint32_t` | `reserved2` | Aligns struct to 640-byte boundary. |

### 3.2 8-Byte Packed Instruction Layout (`impulse_instruction_t`)
Every executable instruction **MUST** be packed into exactly 8 bytes (64 bits), structured as:

| Byte Offset | Field Name | Type | Semantic Role |
| :--- | :--- | :--- | :--- |
| `0x00` | `opcode` | `uint8_t` | The ImpOps bytecode opcode identifier (`0x00`..`0xFF`). |
| `0x01` | `flags` | `uint8_t` | Instruction modifiers (see §3.3). |
| `0x02` – `0x03` | `dst_reg` | `uint16_t` | Destination register index (`0`..`63`). |
| `0x04` – `0x07` | `payload` | `uint32_t` | Operands, constants, offsets, or jump addresses. |

### 3.3 Instruction Modifier Flags
The `flags` byte in the instruction structure is a bitmask defined as:
- **`Bit 0` (`0x01` / `IMPULSE_VM_OP_FLAG_MODE_BITSET`)**: Mode BitSet flag. When set, operations operate on or return BitSet handles.
- **`Bit 1` (`0x02` / `IMPULSE_VM_OP_FLAG_ACCUMULATE`)**: Accumulate flag. Instructs the VM to accumulate results into the destination register rather than overwriting.
- **`Bit 2` (`0x04` / `IMPULSE_VM_OP_FLAG_INVERT`)**: Invert flag. Negates conditions, filters, or set tests.
- **`Bit 3` (`0x08` / `IMPULSE_VM_OP_FLAG_OFFHEAP`)**: Off-heap flag. Explicitly forces off-heap memory evaluations.

---

## 4. VM Lifecycle and FFI API Requirements

The native engine library **MUST** export standard C-linkage FFI methods to interact with VM contexts and query states. The FFI boundary **MUST** support the following operations:
1. `impulse_vm_context_create(const impulse_snapshot_t* snapshot)`: Allocates and pre-indexes an execution context.
2. `impulse_vm_context_destroy(impulse_vm_context_t* ctx)`: Safely deallocates all off-heap arenas.
3. `impulse_vm_context_acquire_bitset(impulse_vm_context_t* ctx)`: Returns a free BitSet slot handle index.
4. `impulse_vm_context_release_bitset(impulse_vm_context_t* ctx, size_t handle)`: Clears and frees a BitSet handle for reuse.

---

## 5. ImpOps Instruction Set Reference

The VM **MUST** execute bytecode instructions matching the opcode values and rules listed below. If an instruction executes with invalid registers, type mismatches, or out-of-bounds parameters, the VM **MUST** halt execution and return the appropriate `impulse_vm_status_t` error.

### 5.1 Setup and Input Instructions
- **`OP_NOP`** (`0x00`)
  - **Behavior**: Increment `pc`. Do nothing.
- **`OP_INIT_INPUT_NODE`** (`0x01`)
  - **Behavior**: Copy the single scalar query parameter Node ID into `dst_reg`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_NODE_ID`.
- **`OP_INIT_INPUT_SET`** (`0x02`)
  - **Behavior**: Fetch input parameters, populate a new off-heap BitSet, and store its handle in `dst_reg`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_BITSET_HANDLE`.
- **`OP_LOAD_CONST_INT`** (`0x03`)
  - **Behavior**: Load a 64-bit integer into `dst_reg`. If the `OFFHEAP` modifier is set, the payload represents a pointer or offset; otherwise, it is loaded directly.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_INT64`.
- **`OP_MAP_KEYS_TO_DENSE`** (`0x04`)
  - **Behavior**: Maps external keys to continuous internal node indices.
- **`OP_LOAD_CONST_FLOAT`** (`0x05`)
  - **Behavior**: Load a 32-bit single-precision float into `dst_reg`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_FLOAT`.
- **`OP_LOAD_CONST_STR_PREFIX`** (`0x06`)
  - **Behavior**: Load a string prefix reference index into `dst_reg`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_INT64`.
- **`OP_LOAD_INLINE_ARRAY`** (`0x07`)
  - **Behavior**: Load address of embedded array in bytecode stream.
- **`OP_INIT_MOCK_GRAPH`** (`0x08`)
  - **Behavior**: Load a mock snapshot struct reference into `dst_reg`.

### 5.2 Traversal and Filter Instructions
- **`OP_CSR_WALK`** (`0x10`)
  - **Behavior**: Traverse relationship edges using Compressed Sparse Row topology. Takes source nodes from a register, follows the relation ID, and writes target nodes into `dst_reg`.
  - **Type Requirements**: Source nodes register **MUST** be `TYPE_BITSET_HANDLE` or `TYPE_NODE_ID`. Relation ID **MUST** be `TYPE_RELATION_ID`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_BITSET_HANDLE`.
- **`OP_CSR_WALK_FILTERED`** (`0x11`)
  - **Behavior**: Walk CSR applying attribute filter constraints.
- **`OP_CSR_DEGREE`** (`0x12`)
  - **Behavior**: Computes the degree of specified nodes.
- **`OP_CSR_WALK_PREDICATE`** (`0x13`)
  - **Behavior**: Walk CSR and evaluate boolean predicate.
- **`OP_NODE_FILTER`** (`0x14`)
  - **Behavior**: Filter node identifiers using an attribute constraint.
- **`OP_NODE_FILTER_STR_PREFIX`** (`0x15`)
  - **Behavior**: Filter nodes using a string prefix matching condition.
- **`OP_CSR_WALK_REDUCE_SUM`** (`0x16`)
  - **Behavior**: Walk CSR and calculate reduction sum.
- **`OP_CSR_WALK_REDUCE`** (`0x17`)
  - **Behavior**: Walk CSR and evaluate reduction logic.
- **`OP_CSC_WALK`** (`0x18`)
  - **Behavior**: Traverse relationship edges backwards using Compressed Sparse Column topology.
  - **Type Requirements**: Source nodes register **MUST** be `TYPE_BITSET_HANDLE` or `TYPE_NODE_ID`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_BITSET_HANDLE`.
- **`OP_HAS_CSR`** (`0x19`)
  - **Behavior**: Verify if relation has a CSR layout. Sets `flags[EQ]` accordingly.
- **`OP_HAS_CSC`** (`0x1A`)
  - **Behavior**: Verify if relation has a CSC layout. Sets `flags[EQ]` accordingly.
- **`OP_HAS_COO`** (`0x1B`)
  - **Behavior**: Verify if relation has a COO layout. Sets `flags[EQ]` accordingly.
- **`OP_HAS_KEY_CATALOG`** (`0x1C`)
  - **Behavior**: Verify if domain catalog exists. Sets `flags[EQ]` accordingly.

### 5.3 Set Mathematics and Algebra Instructions
- **`OP_SET_UNION`** (`0x30`)
  - **Behavior**: Union bitset arrays from two source registers.
  - **Type Requirements**: Source registers **MUST** be `TYPE_BITSET_HANDLE`.
- **`OP_SET_INTERSECT`** (`0x31`)
  - **Behavior**: Intersect bitset arrays from two source registers.
  - **Type Requirements**: Source registers **MUST** be `TYPE_BITSET_HANDLE`.
- **`OP_SET_DIFFERENCE`** (`0x32`)
  - **Behavior**: Subtract second register bitset from the first register bitset.
  - **Type Requirements**: Source registers **MUST** be `TYPE_BITSET_HANDLE`.
- **`OP_SET_CARDINALITY`** (`0x33`)
  - **Behavior**: Compute population count of BitSet. Writes count to `dst_reg`.
  - **Type Transition**: `dst_reg` type tag **MUST** become `TYPE_INT64`.
- **`OP_VECTOR_MUL_ATTR`** (`0x34`)
  - **Behavior**: Element-wise multiplication of vector and attribute arrays.
- **`OP_VECTOR_REDUCE_SUM`** (`0x35`)
  - **Behavior**: Compute sum of elements in a vector register.
- **`OP_VECTOR_DIV`** (`0x36`)
  - **Behavior**: Element-wise division.
- **`OP_VECTOR_STR_CONCAT`** (`0x37`)
  - **Behavior**: Join vector string fields.
- **`OP_FLOAT_VECTOR_SCALE`** (`0x38`)
  - **Behavior**: Perform float vector scaling operation.
- **`OP_L1_NORM_DIFF`** (`0x39`)
  - **Behavior**: Calculate L1 Norm of differences between vectors.

### 5.4 GraphBLAS and Matrix Instructions
- **`OP_CC_AFFOREST`** (`0x40`)
  - **Behavior**: Component step in Afforest algorithm.
- **`OP_MXV`** (`0x41`)
  - **Behavior**: Multiply adjacency matrix by a vector using GraphBLAS semirings.
- **`OP_VXM`** (`0x42`)
  - **Behavior**: Multiply vector by adjacency matrix using GraphBLAS semirings.
- **`OP_EWISE_ADD`** (`0x43`)
  - **Behavior**: Element-wise addition.
- **`OP_EWISE_MULT`** (`0x44`)
  - **Behavior**: Element-wise multiplication.
- **`OP_REDUCE`** (`0x45`)
  - **Behavior**: Reduce matrix rows/columns.
- **`OP_CC_HOOK_COMPRESS`** (`0x46`)
  - **Behavior**: Tree compress operation.
- **`OP_TC_SWEEP_BATCH`** (`0x47`)
  - **Behavior**: Parallel batch sweep for Triangle Counting.
- **`OP_BRANDES_FORWARD`** (`0x48`)
  - **Behavior**: Brandes betweenness centrality forward traversal.
- **`OP_BRANDES_BACKWARD`** (`0x49`)
  - **Behavior**: Brandes betweenness centrality dependency accumulation.
- **`OP_DELTA_STEP_RELAX`** (`0x4A`)
  - **Behavior**: Relaxes shortest path distance boundaries.
- **`OP_READ_EDGE_WEIGHT`** (`0x4B`)
  - **Behavior**: Reads weight value associated with edge offset.

### 5.5 Control Flow and Branching Instructions
- **`OP_JMP`** (`0x50`)
  - **Behavior**: Set program counter `pc` to execution offset in payload.
- **`OP_JZ`** (`0x51`)
  - **Behavior**: If `flags[ZF]` is set to 1, set `pc` to payload execution offset.
- **`OP_JNZ`** (`0x52`)
  - **Behavior**: If `flags[ZF]` is set to 0, set `pc` to payload execution offset.
- **`OP_LOOP_DECR`** (`0x53`)
  - **Behavior**: Decrement `dst_reg` (which **MUST** be `TYPE_INT64`). If result > 0, set `pc` to payload execution offset.
- **`OP_STABLE_CHECK`** (`0x54`)
  - **Behavior**: Check convergence between two set states. Sets `flags[ST]` if converged.
- **`OP_CALL`** (`0x55`)
  - **Behavior**: Save current `pc` to subroutine stack, then set `pc` to payload execution offset.
  - **Constraint**: If call stack pointer exceeds depth limits, return `IMPULSE_VM_ERR_STACK_OVERFLOW`.
- **`OP_RET`** (`0x56`)
  - **Behavior**: Pop caller PC from subroutine stack and set `pc`.
  - **Constraint**: If call stack is empty, return `IMPULSE_VM_ERR_STACK_UNDERFLOW`.
- **`OP_THROW`** (`0x5A`)
  - **Behavior**: Stop execution and return custom runtime exception status.
  - **Outcome**: Returns status `IMPULSE_VM_ERR_USER_THROW`.
- **`OP_ASSERT`** (`0x5B`)
  - **Behavior**: Verify invariant condition on register values or flags. If check fails, return `IMPULSE_VM_ERR_ASSERTION_FAILED`.
- **`OP_TRAP`** (`0x5C`)
  - **Behavior**: Interrupt execution context and invoke registered debugger hooks. Returns `IMPULSE_VM_ERR_TRAP`.

### 5.6 Extended Operations
- **`OP_SAMPLE_NEIGHBORS`** (`0x60`)
  - **Behavior**: Perform neighbor sampling (GNN target).
- **`OP_RANDOM_WALK`** (`0x61`)
  - **Behavior**: Perform node random walk traversals.
- **`OP_SCATTER_GATHER`** (`0x62`)
  - **Behavior**: Gather attributes from neighbors and scatter to state vectors.
- **`OP_REBAC_CHECK`** (`0x63`)
  - **Behavior**: Relationship-Based Access Control Zanzibar check path evaluation.
- **`OP_ROARING_BITMAP_AND`** (`0x64`)
  - **Behavior**: Compute logical AND on compressed roaring bitmap structures.
- **`OP_ISLAND_DETECT`** (`0x65`)
  - **Behavior**: Power grid component island traversal.
- **`OP_SPARSE_MATVEC`** (`0x66`)
  - **Behavior**: Compute sparse matrix-vector product.
- **`OP_LOUVAIN_MODULARITY`** (`0x67`)
  - **Behavior**: Louvain community clustering modularity optimization step.
- **`OP_KCORE_DECOMPOSITION`** (`0x68`)
  - **Behavior**: Node k-core graph shell decomposition.
- **`OP_MOTIF_MATCH_3`** (`0x69`)
  - **Behavior**: Search and list 3-node motifs/subgraphs.
- **`OP_GRAPH_ISOMORPHISM`** (`0x6A`)
  - **Behavior**: Compare structure topology similarity.
- **`OP_ROARING_BITMAP_OR`** (`0x6B`)
  - **Behavior**: Bitwise logical OR on roaring bitmaps.
- **`OP_ROARING_BITMAP_AND_NOT`** (`0x6C`)
  - **Behavior**: Bitwise logical AND-NOT subtraction on roaring bitmaps.

### 5.7 Registers and Memory Management Instructions
- **`OP_MOV`** (`0x70`)
  - **Behavior**: Copy value and type tag from source register (payload) into `dst_reg`.
- **`OP_CLEAR_REG`** (`0x71`)
  - **Behavior**: Set `dst_reg` value to 0 and type tag to `TYPE_NULL`.
- **`OP_LOAD_INDIRECT`** (`0x72`)
  - **Behavior**: Load value into `dst_reg` from address located in source register.
- **`OP_ALLOC_SCRATCH`** (`0x73`)
  - **Behavior**: Allocate local thread-private memory chunk.
- **`OP_ASSERT_SCRATCH_BYTES`** (`0x74`)
  - **Behavior**: Assert scratch space matches bounds constraints.
- **`OP_SET_MAX_DOP`** (`0x75`)
  - **Behavior**: Set concurrency limits (maximum degree of parallelism) for multi-threaded opcodes.

### 5.8 Materialization and Output Instructions
- **`OP_COLLECT_BITSET`** (`0x90`)
  - **Behavior**: Materialize target BitSet items into caller array buffer.
- **`OP_COLLECT_ARRAY`** (`0x91`)
  - **Behavior**: Copy values from node vector register into client memory.
- **`OP_MAP_DENSE_TO_KEYS`** (`0x92`)
  - **Behavior**: Resolve dense offsets into user domain key formats.
- **`OP_COLLECT_VALUE_MAP`** (`0x93`)
  - **Behavior**: Materialize map keys/values into FFI structs.
- **`OP_HALT`** (`0xFF`)
  - **Behavior**: Stop virtual machine execution. Return execution status `IMPULSE_VM_OK`.
