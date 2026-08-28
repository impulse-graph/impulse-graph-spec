## 5. Null Safety and Validity Semantics

The Impulse Graph Engine supports nullable attributes via 128-byte aligned **Validity Bitmaps** (as defined in the physical format schema, where `Bit 7` of the attribute type code is set to `1`). When executing operations that read or interact with nullable attributes, the VM **MUST** strictly adhere to the following null safety semantics:

### 5.1 Filters and Comparisons
When evaluating predicate opcodes (e.g., `OP_NODE_FILTER`, `OP_NODE_FILTER_STR_PREFIX`, `OP_CSR_WALK_FILTERED`, `OP_VEC_CMP_EQ`):
- If the attribute validity bit for an element is `0` (null), the comparison **MUST** immediately evaluate to `false`.
- Nulls are considered unknown states. `NULL == NULL` evaluates to `false`, and `NULL != VALUE` evaluates to `false`.
- If the `INVERT` flag is set on the instruction, null elements **MUST STILL** evaluate to `false`. An inverted filter returns all *valid* elements that do not match the condition; it **MUST NOT** return null elements.

### 5.2 Aggregations and Reductions
When evaluating reduction opcodes (e.g., `OP_CSR_WALK_REDUCE_SUM`, `OP_REDUCE`, `OP_EWISE_REDUCE_MIN`, `OP_EWISE_REDUCE_MAX`):
- **Skip Semantics**: Aggregators **MUST** skip (ignore) elements where the validity bit is `0`.
  - For example, `OP_CSR_WALK_REDUCE_SUM` over weights `[5.0, NULL, 3.0]` yields `8.0`. 
  - `OP_SET_CARDINALITY` or counting reductions over `[A, NULL, B]` yields `2`.
- **Empty/Null State**: If a reduction operates entirely over null values (or an empty set), the VM **MUST** set the `ZF` (Zero Flag) to `1` and set the destination register to a default empty value (e.g., `0` for sums, `MAX_INT` for mins, `MIN_INT` for maxes).

### 5.3 Element-Wise Vector Algebra
When evaluating vector math opcodes (e.g., `OP_EWISE_ADD`, `OP_EWISE_MULT`, `OP_VEC_MATH_TERNARY`):
- **Poison / Propagation Semantics**: If any source element in a vector operation is null (validity bit is `0`), the resulting vector element **MUST** also be marked as null.
  - For example, `[5.0, NULL, 2.0] + [1.0, 1.0, 1.0] = [6.0, NULL, 3.0]`.
- The destination register containing the resulting vector (`TYPE_FLOAT_VECTOR`, etc.) **MUST** have an associated validity bitmap allocated in the VM Context if any source vector was nullable.

### 5.4 Gather and Indirect Loads
When evaluating `OP_GATHER_NODE_ATTR`, `OP_GATHER_EDGE_ATTR`, or `OP_LOAD_INDIRECT`:
- If the target attribute is schema-defined as nullable, the VM **MUST** load and bind both the data span and the validity bitmap span to the resulting vector register handle. Any downstream opcodes interacting with that register will then correctly apply the semantics from §5.1, §5.2, or §5.3.

