# Normative Specification: ImpAs (Impulse Assembly) Text Format

* **Specification Version**: 0.9.0
* **Document Status**: Standard Reference Specification
* **Target Audience**: Compiler engineers, VM implementers, and QA engineers writing graph compliance vectors.

This document defines the formal specification for the **ImpAs** (`.impas`) text format. ImpAs is a human-readable assembly language and test-harness format designed to write and validate unit tests for the **ImpulseVM** instruction set.

Implementations of ImpulseVM test runners **MUST** be able to parse compliant `.impas` files, emit the underlying binary representation, execute the VM, and validate the post-execution assertions defined in the file.

---

## 1. File Structure & Sections

An `.impas` file is a line-oriented text format. Empty lines and lines beginning with a semicolon (`;`) are ignored (except for `{{EXPECT: ...}}` assertions, see Section 3).

A file is logically divided into two primary sections:
1. **`.data`**: Contains inline data blocks, attribute arrays, bitset definitions, and environmental parameters (like fuel and relations).
2. **`.text`**: Contains the sequential listing of ImpOps bytecode instructions to be executed.

### 1.1 The `.data` Section
The data section begins with the literal line `.data`. All following lines until `.text` define the test environment.

#### 1.1.1 Relation and Context Bindings
* **`.rel <NAME> = <ID>`**: Defines a physical relationship ID.
* **`.vrel <NAME> = <ID>`**: Defines a virtual (composed) relationship ID.
* **`.fuel <AMOUNT>`**: Sets the initial gas/fuel limit for the VM execution (e.g., `.fuel 1000`).

#### 1.1.2 Inline Arrays and Graphs
Arrays and graphs are packed directly into the VM's `inline_data` context buffer and can be loaded dynamically.
* **`.csr_inline <NAME> = { <src>: [<tgt>, ...], ... }`**: Defines a mock graph explicitly mapping source nodes to target nodes.
* **`.array_float <NAME> = [<float>, <float>, ...]`**: Defines a 32-bit floating-point array.
* **`.array_float <NAME> = [<float>, <float>, ...]`**: Defines a 32-bit floating-point array.
* **`.array_int <NAME> = [<int64>, <int64>, ...]`**: Defines a 64-bit integer array.
* **`.array_node <NAME> = [<uint64>, <uint64>, ...]`**: Defines an array of unsigned 64-bit node IDs.

#### 1.1.3 Polymorphic BitSets
BitSets define subsets of node IDs. To test polymorphic representations within the VM, the following variants are provided. The values in the brackets are the node IDs present in the set.
* **`.set <NAME> = [<id>, <id>, ...]`**: Generic implementation-defined BitSet.
* **`.set_roaring <NAME> = [<id>, <id>, ...]`**: Forces the VM to allocate a Roaring Bitmap representation.
* **`.set_dense <NAME> = [<id>, <id>, ...]`**: Forces the VM to allocate a Dense bitmask representation.

### 1.2 The `.text` Section
The text section begins with the literal line `.text`. All following non-comment lines must be valid instruction mnemonics.

Instructions are formatted as:
`[address]: [OPCODE_MNEMONIC] [ARG1], [ARG2], ...`

* The `[address]:` prefix (e.g., `0x00:`, `0x01:`) is **optional** but highly recommended for readability. The assembler computes physical binary offsets automatically.
* Operands are separated by commas.
* Registers are denoted by `R` followed by the index (e.g., `R0`, `R63`).
* Symbolic names defined in the `.data` section (e.g., `MOCK_PRICES`) can be used as arguments, and the assembler will dynamically inject their `offset` and `count` into the instruction payload.

**Example Instruction:**
```nasm
0x00: OP_LOAD_INLINE_NODE_ARRAY  R1, MOCK_FRONTIER
0x01: OP_NODE_FILTER             R4, R1, R0, 0
0x02: OP_HALT
```

---

## 2. Mock Graph & Attribute Initialization

Testing graph algorithms requires mocking out the storage layer without reading physical `.imps` snapshot files.

1. **`OP_INIT_MOCK_GRAPH R_dst, GRAPH_NAME`**
   Loads an inline `.csr_inline` graph topology into `R_dst` as a mock graph handle. Used by stream opcodes (e.g. `OP_COO_WALK_STREAM`) to traverse the topology.

2. **`OP_INIT_MOCK_NODE_ATTR ATTR_ID, R_data, R_validity`**
   Binds an inline array (loaded in `R_data`) and an optional validity BitSet (`R_validity`) to a globally resolvable Node Attribute ID. If no validity BitSet is needed, `R255` (or any invalid register) can be passed.

3. **`OP_INIT_MOCK_EDGE_ATTR R_rel, R_data, R_validity, ATTR_ID`**
   Extended 128-bit instruction. Identical to node attributes, but binds the attribute to a specific `REL_ID` for edge property gathers.

---

## 3. Test Assertions

Test runners **MUST** validate VM state after the `OP_HALT` instruction executes or the VM traps. Assertions are embedded as specially formatted comments: `; {{EXPECT: [CONDITION]}}`

### 3.1 Status Validation
Validates the `impulse_vm_status_t` return code. If no status is specified, the test runner **MUST** default to expecting `IMPULSE_VM_OK`.
* **`; {{EXPECT: STATUS = IMPULSE_VM_OK}}`**
* **`; {{EXPECT: STATUS = IMPULSE_VM_ERR_INVALID_REGISTER}}`**

### 3.2 Register Validation
Validates the numeric contents of a register. Supported suffixes for floating-point and hexadecimal validation are supported.
* **`; {{EXPECT: REG[R0] = 42}}`** (Integer check)
* **`; {{EXPECT: REG[R1] = 0x2A}}`** (Hexadecimal check)
* **`; {{EXPECT: REG[R2] = 3.14f}}`** (Floating-point check)

### 3.3 Flag Validation
Validates the Boolean state of the `FLAGS` register (Section 2.3 of VM_SPECIFICATION.md).
* **`; {{EXPECT: FLAG = ZF}}`** (Asserts the Zero Flag is `1`)
* **`; {{EXPECT: FLAG = !ZF}}`** (Asserts the Zero Flag is `0`)
* Other flags: `LT`, `GT`, `EQ`, `ST`

### 3.4 Context Validation
Validates the dynamic execution context of the virtual machine.
* **`; {{EXPECT: CALL_DEPTH = 0}}`** (Ensures all functions returned correctly)
* **`; {{EXPECT: SCRATCH = 65536}}`** (Ensures scratch memory was correctly allocated/used)

---

## 4. Full File Example

```nasm
; ====================================================================
; Test: Node Filter with Roaring Bitmap Frontier
; ====================================================================
; {{EXPECT: STATUS = IMPULSE_VM_OK}}
; {{EXPECT: FLAG = ZF}}
; {{EXPECT: REG[R4] = 0}}

.data
.array_float MOCK_PRICES = [1.5, 0.0, 3.14, 0.0]
.set_roaring FRONTIER = [0, 2]

.text
0x00: OP_LOAD_INLINE_ARRAY         R0, MOCK_PRICES
0x01: OP_INIT_MOCK_NODE_ATTR       0, R0, R255
0x02: OP_LOAD_INLINE_SET_ROARING   R3, FRONTIER
0x03: OP_NODE_FILTER               R4, R3, R0, 0
0x04: OP_SET_CARDINALITY           R0, R4
0x05: OP_HALT
```
