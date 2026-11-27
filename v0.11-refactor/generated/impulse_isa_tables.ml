(** DO NOT EDIT — Auto-generated from v0.11-refactor/isa_v0_11.yaml
    by tools/gen_isa_tables.py (impOps v0.11.0, impb v11). *)

let impb_magic : int32 = 0x494D5042l
let impb_version_u16 : int = 11

(** 4-bit Global Modifier Flag nibble masks. *)
let flag_masked_s3 : int = 0x1
let flag_scalar_rhs : int = 0x2
let flag_accum : int = 0x4
let flag_extended : int = 0x8

(** VM Condition Flag bitmasks. *)
let vm_flag_zf : int = 0x0001
let vm_flag_st : int = 0x0002
let vm_flag_nf : int = 0x0004

(** All 80 active opcodes (across 5 pillars) plus 0xFF OP_EXTENSION_PAYLOAD. *)
type opcode =
  | OP_HALT
  | OP_NOP
  | OP_TRAP
  | OP_THROW
  | OP_ASSERT
  | OP_LOAD_CONST
  | OP_LOAD_CONST_POOL
  | OP_LOAD_PARAM
  | OP_MOV
  | OP_SWAP
  | OP_SPILL
  | OP_RELOAD
  | OP_SCALAR_INT_ALU
  | OP_SCALAR_FP_ALU
  | OP_SCALAR_3VL
  | OP_JMP
  | OP_JCC
  | OP_LOOP_DECR
  | OP_CALL
  | OP_RET
  | OP_SET_MAX_DOP
  | OP_SCALAR_DECIMAL_ALU
  | OP_FSEED
  | OP_INIT_DOMAIN_SPAN
  | OP_SET_OP
  | OP_SET_COMPLEMENT
  | OP_SET_CARDINALITY
  | OP_SET_CONTAINS
  | OP_SET_CONVERT
  | OP_STABLE_CHECK
  | OP_WALK
  | OP_WALK_FILTERED
  | OP_DEGREE
  | OP_SPMV
  | OP_WALK_MORSEL
  | OP_FILTER_MORSEL
  | OP_MORSEL_COMMIT
  | OP_MORSEL_END
  | OP_SAMPLE_NEIGHBORS
  | OP_HAS_TOPOLOGY
  | OP_GRAPH_KERNEL
  | OP_LOAD_COLUMN
  | OP_GATHER_NODE_ATTR
  | OP_GATHER_EDGE_ATTR
  | OP_GATHER_VEC
  | OP_NODE_FILTER
  | OP_VEC_CMP
  | OP_VEC_3VL_OP
  | OP_VEC_STR_PRED
  | OP_VEC_MATH_ARITH
  | OP_VEC_MATH_EXP_LOG
  | OP_VEC_MATH_TRIG_HYP
  | OP_VEC_MATH_ACT
  | OP_VEC_INT_BITWISE
  | OP_VEC_TERNARY
  | OP_VEC_BLEND
  | OP_COALESCE
  | OP_VEC_INIT
  | OP_VEC_POINT
  | OP_VEC_REDUCE
  | OP_TOP_K
  | OP_INDEX_SCAN
  | OP_MAP_KEYS_TO_DENSE
  | OP_MAP_DENSE_TO_KEYS
  | OP_COLLECT
  | OP_VEC_DECIMAL_ALU
  | OP_LANE_INIT_SEEDS
  | OP_LANE_INIT_GROUPS
  | OP_LANE_WALK
  | OP_LANE_BITWISE
  | OP_LANE_FILTER_QUORUM
  | OP_LANE_REDUCE_AND
  | OP_LANE_REDUCE_ATTR
  | OP_VECTOR_ANN_SEARCH
  | OP_VECTOR_RERANK
  | OP_LANE_STATE_INIT
  | OP_LANE_STATE_WALK
  | OP_LANE_STATE_OP
  | OP_LANE_STATE_REDUCE
  | OP_VECTOR_POOL
  | OP_EXTENSION_PAYLOAD

type morsel_role =
  | Morsel_forbidden
  | Morsel_body_ok
  | Morsel_body_cast_only
  | Morsel_body_v_only
  | Morsel_body_pair_only
  | Morsel_fwd_jump_only
  | Morsel_header
  | Morsel_commit_only
  | Morsel_end_only

type opcode_meta = {
  op               : opcode;
  code             : int;
  name             : string;
  mnemonic         : string;
  pillar           : int;
  allowed_flags    : int;
  valid_subop_mask : int;
  morsel_role      : morsel_role;
}

let all_opcode_meta : opcode_meta list = [
  { op = OP_HALT; code = 0x00; name = "OP_HALT"; mnemonic = "HALT"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_NOP; code = 0x01; name = "OP_NOP"; mnemonic = "NOP"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_body_ok };
  { op = OP_TRAP; code = 0x02; name = "OP_TRAP"; mnemonic = "TRAP"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_THROW; code = 0x03; name = "OP_THROW"; mnemonic = "THROW"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_ASSERT; code = 0x04; name = "OP_ASSERT"; mnemonic = "ASSERT"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x00FF; morsel_role = Morsel_forbidden };
  { op = OP_LOAD_CONST; code = 0x05; name = "OP_LOAD_CONST"; mnemonic = "LOAD_CONST"; pillar = 1; allowed_flags = 0x8; valid_subop_mask = 0x00FF; morsel_role = Morsel_forbidden };
  { op = OP_LOAD_CONST_POOL; code = 0x06; name = "OP_LOAD_CONST_POOL"; mnemonic = "LOAD_CONST_POOL"; pillar = 1; allowed_flags = 0x4; valid_subop_mask = 0x0007; morsel_role = Morsel_forbidden };
  { op = OP_LOAD_PARAM; code = 0x07; name = "OP_LOAD_PARAM"; mnemonic = "LOAD_PARAM"; pillar = 1; allowed_flags = 0x4; valid_subop_mask = 0x0007; morsel_role = Morsel_forbidden };
  { op = OP_MOV; code = 0x08; name = "OP_MOV"; mnemonic = "MOV"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x003F; morsel_role = Morsel_body_ok };
  { op = OP_SWAP; code = 0x09; name = "OP_SWAP"; mnemonic = "SWAP"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0007; morsel_role = Morsel_body_ok };
  { op = OP_SPILL; code = 0x0A; name = "OP_SPILL"; mnemonic = "SPILL"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0007; morsel_role = Morsel_body_v_only };
  { op = OP_RELOAD; code = 0x0B; name = "OP_RELOAD"; mnemonic = "RELOAD"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0007; morsel_role = Morsel_body_v_only };
  { op = OP_SCALAR_INT_ALU; code = 0x0C; name = "OP_SCALAR_INT_ALU"; mnemonic = "SCALAR_INT_ALU"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0xFFFF; morsel_role = Morsel_forbidden };
  { op = OP_SCALAR_FP_ALU; code = 0x0D; name = "OP_SCALAR_FP_ALU"; mnemonic = "SCALAR_FP_ALU"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0xFFFF; morsel_role = Morsel_forbidden };
  { op = OP_SCALAR_3VL; code = 0x0E; name = "OP_SCALAR_3VL"; mnemonic = "SCALAR_3VL"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0xFFFF; morsel_role = Morsel_forbidden };
  { op = OP_JMP; code = 0x0F; name = "OP_JMP"; mnemonic = "JMP"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_fwd_jump_only };
  { op = OP_JCC; code = 0x10; name = "OP_JCC"; mnemonic = "JCC"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x03FF; morsel_role = Morsel_fwd_jump_only };
  { op = OP_LOOP_DECR; code = 0x11; name = "OP_LOOP_DECR"; mnemonic = "LOOP_DECR"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_CALL; code = 0x12; name = "OP_CALL"; mnemonic = "CALL"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_RET; code = 0x13; name = "OP_RET"; mnemonic = "RET"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_SET_MAX_DOP; code = 0x14; name = "OP_SET_MAX_DOP"; mnemonic = "SET_MAX_DOP"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_SCALAR_DECIMAL_ALU; code = 0x15; name = "OP_SCALAR_DECIMAL_ALU"; mnemonic = "SCALAR_DECIMAL_ALU"; pillar = 1; allowed_flags = 0x0; valid_subop_mask = 0xFFFF; morsel_role = Morsel_forbidden };
  { op = OP_FSEED; code = 0x20; name = "OP_FSEED"; mnemonic = "FSEED"; pillar = 2; allowed_flags = 0x4; valid_subop_mask = 0x001F; morsel_role = Morsel_forbidden };
  { op = OP_INIT_DOMAIN_SPAN; code = 0x21; name = "OP_INIT_DOMAIN_SPAN"; mnemonic = "INIT_DOMAIN_SPAN"; pillar = 2; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_SET_OP; code = 0x22; name = "OP_SET_OP"; mnemonic = "SET_OP"; pillar = 2; allowed_flags = 0x0; valid_subop_mask = 0x000F; morsel_role = Morsel_body_ok };
  { op = OP_SET_COMPLEMENT; code = 0x23; name = "OP_SET_COMPLEMENT"; mnemonic = "SET_COMPLEMENT"; pillar = 2; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_body_ok };
  { op = OP_SET_CARDINALITY; code = 0x24; name = "OP_SET_CARDINALITY"; mnemonic = "SET_CARDINALITY"; pillar = 2; allowed_flags = 0x0; valid_subop_mask = 0x001F; morsel_role = Morsel_forbidden };
  { op = OP_SET_CONTAINS; code = 0x25; name = "OP_SET_CONTAINS"; mnemonic = "SET_CONTAINS"; pillar = 2; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_SET_CONVERT; code = 0x26; name = "OP_SET_CONVERT"; mnemonic = "SET_CONVERT"; pillar = 2; allowed_flags = 0x4; valid_subop_mask = 0x000F; morsel_role = Morsel_body_ok };
  { op = OP_STABLE_CHECK; code = 0x27; name = "OP_STABLE_CHECK"; mnemonic = "STABLE_CHECK"; pillar = 2; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_WALK; code = 0x30; name = "OP_WALK"; mnemonic = "WALK"; pillar = 3; allowed_flags = 0x5; valid_subop_mask = 0x03FF; morsel_role = Morsel_forbidden };
  { op = OP_WALK_FILTERED; code = 0x31; name = "OP_WALK_FILTERED"; mnemonic = "WALK_FILTERED"; pillar = 3; allowed_flags = 0x5; valid_subop_mask = 0xFFFF; morsel_role = Morsel_forbidden };
  { op = OP_DEGREE; code = 0x33; name = "OP_DEGREE"; mnemonic = "DEGREE"; pillar = 3; allowed_flags = 0x1; valid_subop_mask = 0x003F; morsel_role = Morsel_forbidden };
  { op = OP_SPMV; code = 0x34; name = "OP_SPMV"; mnemonic = "SPMV"; pillar = 3; allowed_flags = 0x7; valid_subop_mask = 0x01FF; morsel_role = Morsel_forbidden };
  { op = OP_WALK_MORSEL; code = 0x35; name = "OP_WALK_MORSEL"; mnemonic = "WALK_MORSEL"; pillar = 3; allowed_flags = 0x1; valid_subop_mask = 0x000F; morsel_role = Morsel_header };
  { op = OP_FILTER_MORSEL; code = 0x36; name = "OP_FILTER_MORSEL"; mnemonic = "FILTER_MORSEL"; pillar = 3; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_header };
  { op = OP_MORSEL_COMMIT; code = 0x37; name = "OP_MORSEL_COMMIT"; mnemonic = "MORSEL_COMMIT"; pillar = 3; allowed_flags = 0x7; valid_subop_mask = 0x03FF; morsel_role = Morsel_commit_only };
  { op = OP_MORSEL_END; code = 0x38; name = "OP_MORSEL_END"; mnemonic = "MORSEL_END"; pillar = 3; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_end_only };
  { op = OP_SAMPLE_NEIGHBORS; code = 0x39; name = "OP_SAMPLE_NEIGHBORS"; mnemonic = "SAMPLE_NEIGHBORS"; pillar = 3; allowed_flags = 0x0; valid_subop_mask = 0x000F; morsel_role = Morsel_forbidden };
  { op = OP_HAS_TOPOLOGY; code = 0x3A; name = "OP_HAS_TOPOLOGY"; mnemonic = "HAS_TOPOLOGY"; pillar = 3; allowed_flags = 0x0; valid_subop_mask = 0x03FF; morsel_role = Morsel_forbidden };
  { op = OP_GRAPH_KERNEL; code = 0x3B; name = "OP_GRAPH_KERNEL"; mnemonic = "GRAPH_KERNEL"; pillar = 3; allowed_flags = 0x1; valid_subop_mask = 0x001F; morsel_role = Morsel_forbidden };
  { op = OP_LOAD_COLUMN; code = 0x40; name = "OP_LOAD_COLUMN"; mnemonic = "LOAD_COLUMN"; pillar = 4; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_GATHER_NODE_ATTR; code = 0x41; name = "OP_GATHER_NODE_ATTR"; mnemonic = "GATHER_NODE_ATTR"; pillar = 4; allowed_flags = 0x1; valid_subop_mask = 0x0007; morsel_role = Morsel_body_ok };
  { op = OP_GATHER_EDGE_ATTR; code = 0x42; name = "OP_GATHER_EDGE_ATTR"; mnemonic = "GATHER_EDGE_ATTR"; pillar = 4; allowed_flags = 0x1; valid_subop_mask = 0x0003; morsel_role = Morsel_body_ok };
  { op = OP_GATHER_VEC; code = 0x43; name = "OP_GATHER_VEC"; mnemonic = "GATHER_VEC"; pillar = 4; allowed_flags = 0x1; valid_subop_mask = 0x0001; morsel_role = Morsel_body_ok };
  { op = OP_NODE_FILTER; code = 0x44; name = "OP_NODE_FILTER"; mnemonic = "NODE_FILTER"; pillar = 4; allowed_flags = 0x6; valid_subop_mask = 0x01FF; morsel_role = Morsel_forbidden };
  { op = OP_VEC_CMP; code = 0x45; name = "OP_VEC_CMP"; mnemonic = "VEC_CMP"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x00FF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_3VL_OP; code = 0x46; name = "OP_VEC_3VL_OP"; mnemonic = "VEC_3VL_OP"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x0FFF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_STR_PRED; code = 0x47; name = "OP_VEC_STR_PRED"; mnemonic = "VEC_STR_PRED"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x03FF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_MATH_ARITH; code = 0x48; name = "OP_VEC_MATH_ARITH"; mnemonic = "VEC_MATH_ARITH"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0xFFFF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_MATH_EXP_LOG; code = 0x49; name = "OP_VEC_MATH_EXP_LOG"; mnemonic = "VEC_MATH_EXP_LOG"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x3FFF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_MATH_TRIG_HYP; code = 0x4A; name = "OP_VEC_MATH_TRIG_HYP"; mnemonic = "VEC_MATH_TRIG_HYP"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x3FFF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_MATH_ACT; code = 0x4B; name = "OP_VEC_MATH_ACT"; mnemonic = "VEC_MATH_ACT"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x003F; morsel_role = Morsel_body_ok };
  { op = OP_VEC_INT_BITWISE; code = 0x4C; name = "OP_VEC_INT_BITWISE"; mnemonic = "VEC_INT_BITWISE"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x3FFF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_TERNARY; code = 0x4D; name = "OP_VEC_TERNARY"; mnemonic = "VEC_TERNARY"; pillar = 4; allowed_flags = 0x2; valid_subop_mask = 0x03FF; morsel_role = Morsel_body_ok };
  { op = OP_VEC_BLEND; code = 0x4E; name = "OP_VEC_BLEND"; mnemonic = "VEC_BLEND"; pillar = 4; allowed_flags = 0x2; valid_subop_mask = 0x000F; morsel_role = Morsel_body_ok };
  { op = OP_COALESCE; code = 0x4F; name = "OP_COALESCE"; mnemonic = "COALESCE"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x0001; morsel_role = Morsel_body_ok };
  { op = OP_VEC_INIT; code = 0x50; name = "OP_VEC_INIT"; mnemonic = "VEC_INIT"; pillar = 4; allowed_flags = 0x2; valid_subop_mask = 0x7F7F; morsel_role = Morsel_forbidden };
  { op = OP_VEC_POINT; code = 0x51; name = "OP_VEC_POINT"; mnemonic = "VEC_POINT"; pillar = 4; allowed_flags = 0x0; valid_subop_mask = 0x000F; morsel_role = Morsel_body_cast_only };
  { op = OP_VEC_REDUCE; code = 0x52; name = "OP_VEC_REDUCE"; mnemonic = "VEC_REDUCE"; pillar = 4; allowed_flags = 0x1; valid_subop_mask = 0x0FFF; morsel_role = Morsel_forbidden };
  { op = OP_TOP_K; code = 0x53; name = "OP_TOP_K"; mnemonic = "TOP_K"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0x000F; morsel_role = Morsel_forbidden };
  { op = OP_INDEX_SCAN; code = 0x54; name = "OP_INDEX_SCAN"; mnemonic = "INDEX_SCAN"; pillar = 4; allowed_flags = 0x4; valid_subop_mask = 0x007F; morsel_role = Morsel_forbidden };
  { op = OP_MAP_KEYS_TO_DENSE; code = 0x55; name = "OP_MAP_KEYS_TO_DENSE"; mnemonic = "MAP_KEYS_TO_DENSE"; pillar = 4; allowed_flags = 0x4; valid_subop_mask = 0x001F; morsel_role = Morsel_forbidden };
  { op = OP_MAP_DENSE_TO_KEYS; code = 0x56; name = "OP_MAP_DENSE_TO_KEYS"; mnemonic = "MAP_DENSE_TO_KEYS"; pillar = 4; allowed_flags = 0x0; valid_subop_mask = 0x0007; morsel_role = Morsel_forbidden };
  { op = OP_COLLECT; code = 0x57; name = "OP_COLLECT"; mnemonic = "COLLECT"; pillar = 4; allowed_flags = 0x1; valid_subop_mask = 0x001F; morsel_role = Morsel_forbidden };
  { op = OP_VEC_DECIMAL_ALU; code = 0x58; name = "OP_VEC_DECIMAL_ALU"; mnemonic = "VEC_DECIMAL_ALU"; pillar = 4; allowed_flags = 0x3; valid_subop_mask = 0xFFFF; morsel_role = Morsel_body_ok };
  { op = OP_LANE_INIT_SEEDS; code = 0x60; name = "OP_LANE_INIT_SEEDS"; mnemonic = "LANE_INIT_SEEDS"; pillar = 5; allowed_flags = 0x0; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_LANE_INIT_GROUPS; code = 0x61; name = "OP_LANE_INIT_GROUPS"; mnemonic = "LANE_INIT_GROUPS"; pillar = 5; allowed_flags = 0x4; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_LANE_WALK; code = 0x63; name = "OP_LANE_WALK"; mnemonic = "LANE_WALK"; pillar = 5; allowed_flags = 0x5; valid_subop_mask = 0x03FF; morsel_role = Morsel_forbidden };
  { op = OP_LANE_BITWISE; code = 0x64; name = "OP_LANE_BITWISE"; mnemonic = "LANE_BITWISE"; pillar = 5; allowed_flags = 0x2; valid_subop_mask = 0x000F; morsel_role = Morsel_forbidden };
  { op = OP_LANE_FILTER_QUORUM; code = 0x65; name = "OP_LANE_FILTER_QUORUM"; mnemonic = "LANE_FILTER_QUORUM"; pillar = 5; allowed_flags = 0x6; valid_subop_mask = 0x0007; morsel_role = Morsel_forbidden };
  { op = OP_LANE_REDUCE_AND; code = 0x66; name = "OP_LANE_REDUCE_AND"; mnemonic = "LANE_REDUCE_AND"; pillar = 5; allowed_flags = 0x6; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
  { op = OP_LANE_REDUCE_ATTR; code = 0x67; name = "OP_LANE_REDUCE_ATTR"; mnemonic = "LANE_REDUCE_ATTR"; pillar = 5; allowed_flags = 0x0; valid_subop_mask = 0x000F; morsel_role = Morsel_forbidden };
  { op = OP_VECTOR_ANN_SEARCH; code = 0x69; name = "OP_VECTOR_ANN_SEARCH"; mnemonic = "VECTOR_ANN_SEARCH"; pillar = 5; allowed_flags = 0x1; valid_subop_mask = 0x0003; morsel_role = Morsel_forbidden };
  { op = OP_VECTOR_RERANK; code = 0x6A; name = "OP_VECTOR_RERANK"; mnemonic = "VECTOR_RERANK"; pillar = 5; allowed_flags = 0x1; valid_subop_mask = 0x00FF; morsel_role = Morsel_body_pair_only };
  { op = OP_LANE_STATE_INIT; code = 0x6B; name = "OP_LANE_STATE_INIT"; mnemonic = "LANE_STATE_INIT"; pillar = 5; allowed_flags = 0x2; valid_subop_mask = 0x003F; morsel_role = Morsel_forbidden };
  { op = OP_LANE_STATE_WALK; code = 0x6C; name = "OP_LANE_STATE_WALK"; mnemonic = "LANE_STATE_WALK"; pillar = 5; allowed_flags = 0x7; valid_subop_mask = 0x03FF; morsel_role = Morsel_forbidden };
  { op = OP_LANE_STATE_OP; code = 0x6D; name = "OP_LANE_STATE_OP"; mnemonic = "LANE_STATE_OP"; pillar = 5; allowed_flags = 0x2; valid_subop_mask = 0x001F; morsel_role = Morsel_forbidden };
  { op = OP_LANE_STATE_REDUCE; code = 0x6E; name = "OP_LANE_STATE_REDUCE"; mnemonic = "LANE_STATE_REDUCE"; pillar = 5; allowed_flags = 0x2; valid_subop_mask = 0x007F; morsel_role = Morsel_forbidden };
  { op = OP_VECTOR_POOL; code = 0x6F; name = "OP_VECTOR_POOL"; mnemonic = "VECTOR_POOL"; pillar = 5; allowed_flags = 0x0; valid_subop_mask = 0x000F; morsel_role = Morsel_forbidden };
  { op = OP_EXTENSION_PAYLOAD; code = 0xFF; name = "OP_EXTENSION_PAYLOAD"; mnemonic = "EXTENSION_PAYLOAD"; pillar = 0; allowed_flags = 0x0; valid_subop_mask = 0x0001; morsel_role = Morsel_forbidden };
]

let by_code_table : opcode_meta option array =
  let tbl = Array.make 256 None in
  List.iter (fun m -> tbl.(m.code) <- Some m) all_opcode_meta;
  tbl

let code_of_opcode : opcode -> int = function
  | OP_HALT -> 0x00
  | OP_NOP -> 0x01
  | OP_TRAP -> 0x02
  | OP_THROW -> 0x03
  | OP_ASSERT -> 0x04
  | OP_LOAD_CONST -> 0x05
  | OP_LOAD_CONST_POOL -> 0x06
  | OP_LOAD_PARAM -> 0x07
  | OP_MOV -> 0x08
  | OP_SWAP -> 0x09
  | OP_SPILL -> 0x0A
  | OP_RELOAD -> 0x0B
  | OP_SCALAR_INT_ALU -> 0x0C
  | OP_SCALAR_FP_ALU -> 0x0D
  | OP_SCALAR_3VL -> 0x0E
  | OP_JMP -> 0x0F
  | OP_JCC -> 0x10
  | OP_LOOP_DECR -> 0x11
  | OP_CALL -> 0x12
  | OP_RET -> 0x13
  | OP_SET_MAX_DOP -> 0x14
  | OP_SCALAR_DECIMAL_ALU -> 0x15
  | OP_FSEED -> 0x20
  | OP_INIT_DOMAIN_SPAN -> 0x21
  | OP_SET_OP -> 0x22
  | OP_SET_COMPLEMENT -> 0x23
  | OP_SET_CARDINALITY -> 0x24
  | OP_SET_CONTAINS -> 0x25
  | OP_SET_CONVERT -> 0x26
  | OP_STABLE_CHECK -> 0x27
  | OP_WALK -> 0x30
  | OP_WALK_FILTERED -> 0x31
  | OP_DEGREE -> 0x33
  | OP_SPMV -> 0x34
  | OP_WALK_MORSEL -> 0x35
  | OP_FILTER_MORSEL -> 0x36
  | OP_MORSEL_COMMIT -> 0x37
  | OP_MORSEL_END -> 0x38
  | OP_SAMPLE_NEIGHBORS -> 0x39
  | OP_HAS_TOPOLOGY -> 0x3A
  | OP_GRAPH_KERNEL -> 0x3B
  | OP_LOAD_COLUMN -> 0x40
  | OP_GATHER_NODE_ATTR -> 0x41
  | OP_GATHER_EDGE_ATTR -> 0x42
  | OP_GATHER_VEC -> 0x43
  | OP_NODE_FILTER -> 0x44
  | OP_VEC_CMP -> 0x45
  | OP_VEC_3VL_OP -> 0x46
  | OP_VEC_STR_PRED -> 0x47
  | OP_VEC_MATH_ARITH -> 0x48
  | OP_VEC_MATH_EXP_LOG -> 0x49
  | OP_VEC_MATH_TRIG_HYP -> 0x4A
  | OP_VEC_MATH_ACT -> 0x4B
  | OP_VEC_INT_BITWISE -> 0x4C
  | OP_VEC_TERNARY -> 0x4D
  | OP_VEC_BLEND -> 0x4E
  | OP_COALESCE -> 0x4F
  | OP_VEC_INIT -> 0x50
  | OP_VEC_POINT -> 0x51
  | OP_VEC_REDUCE -> 0x52
  | OP_TOP_K -> 0x53
  | OP_INDEX_SCAN -> 0x54
  | OP_MAP_KEYS_TO_DENSE -> 0x55
  | OP_MAP_DENSE_TO_KEYS -> 0x56
  | OP_COLLECT -> 0x57
  | OP_VEC_DECIMAL_ALU -> 0x58
  | OP_LANE_INIT_SEEDS -> 0x60
  | OP_LANE_INIT_GROUPS -> 0x61
  | OP_LANE_WALK -> 0x63
  | OP_LANE_BITWISE -> 0x64
  | OP_LANE_FILTER_QUORUM -> 0x65
  | OP_LANE_REDUCE_AND -> 0x66
  | OP_LANE_REDUCE_ATTR -> 0x67
  | OP_VECTOR_ANN_SEARCH -> 0x69
  | OP_VECTOR_RERANK -> 0x6A
  | OP_LANE_STATE_INIT -> 0x6B
  | OP_LANE_STATE_WALK -> 0x6C
  | OP_LANE_STATE_OP -> 0x6D
  | OP_LANE_STATE_REDUCE -> 0x6E
  | OP_VECTOR_POOL -> 0x6F
  | OP_EXTENSION_PAYLOAD -> 0xFF

let meta_of_opcode (op : opcode) : opcode_meta =
  match by_code_table.(code_of_opcode op) with
  | Some m -> m
  | None -> assert false

(** Typed per-opcode subop sum types with exhaustive to_int / of_int codecs. *)
module Subop = struct
  module Halt = struct
    type t =
      | Ok

    let to_int : t -> int = function
      | Ok -> 0

    let of_int : int -> t option = function
      | 0 -> Some Ok
      | _ -> None
  end

  module Nop = struct
    type t =
      | Nop

    let to_int : t -> int = function
      | Nop -> 0

    let of_int : int -> t option = function
      | 0 -> Some Nop
      | _ -> None
  end

  module Trap = struct
    type t =
      | Trap

    let to_int : t -> int = function
      | Trap -> 0

    let of_int : int -> t option = function
      | 0 -> Some Trap
      | _ -> None
  end

  module Throw = struct
    type t =
      | Imm
      | Reg

    let to_int : t -> int = function
      | Imm -> 0
      | Reg -> 1

    let of_int : int -> t option = function
      | 0 -> Some Imm
      | 1 -> Some Reg
      | _ -> None
  end

  module Assert = struct
    type t =
      | TrueR
      | NonemptyF
      | EmptyF
      | ZfSet
      | ZfClear
      | StSet
      | NotNullR
      | IsNullR

    let to_int : t -> int = function
      | TrueR -> 0
      | NonemptyF -> 1
      | EmptyF -> 2
      | ZfSet -> 3
      | ZfClear -> 4
      | StSet -> 5
      | NotNullR -> 6
      | IsNullR -> 7

    let of_int : int -> t option = function
      | 0 -> Some TrueR
      | 1 -> Some NonemptyF
      | 2 -> Some EmptyF
      | 3 -> Some ZfSet
      | 4 -> Some ZfClear
      | 5 -> Some StSet
      | 6 -> Some NotNullR
      | 7 -> Some IsNullR
      | _ -> None
  end

  module LoadConst = struct
    type t =
      | I32
      | U32
      | F32
      | F32Raw
      | I64
      | U64
      | F64
      | Null

    let to_int : t -> int = function
      | I32 -> 0
      | U32 -> 1
      | F32 -> 2
      | F32Raw -> 3
      | I64 -> 4
      | U64 -> 5
      | F64 -> 6
      | Null -> 7

    let of_int : int -> t option = function
      | 0 -> Some I32
      | 1 -> Some U32
      | 2 -> Some F32
      | 3 -> Some F32Raw
      | 4 -> Some I64
      | 5 -> Some U64
      | 6 -> Some F64
      | 7 -> Some Null
      | _ -> None
  end

  module LoadConstPool = struct
    type t =
      | Vec
      | Frontier
      | Str

    let to_int : t -> int = function
      | Vec -> 0
      | Frontier -> 1
      | Str -> 2

    let of_int : int -> t option = function
      | 0 -> Some Vec
      | 1 -> Some Frontier
      | 2 -> Some Str
      | _ -> None
  end

  module LoadParam = struct
    type t =
      | Scalar
      | Frontier
      | Vec

    let to_int : t -> int = function
      | Scalar -> 0
      | Frontier -> 1
      | Vec -> 2

    let of_int : int -> t option = function
      | 0 -> Some Scalar
      | 1 -> Some Frontier
      | 2 -> Some Vec
      | _ -> None
  end

  module Mov = struct
    type t =
      | R
      | F
      | V
      | ClearR
      | ClearF
      | ClearV

    let to_int : t -> int = function
      | R -> 0
      | F -> 1
      | V -> 2
      | ClearR -> 3
      | ClearF -> 4
      | ClearV -> 5

    let of_int : int -> t option = function
      | 0 -> Some R
      | 1 -> Some F
      | 2 -> Some V
      | 3 -> Some ClearR
      | 4 -> Some ClearF
      | 5 -> Some ClearV
      | _ -> None
  end

  module Swap = struct
    type t =
      | R
      | F
      | V

    let to_int : t -> int = function
      | R -> 0
      | F -> 1
      | V -> 2

    let of_int : int -> t option = function
      | 0 -> Some R
      | 1 -> Some F
      | 2 -> Some V
      | _ -> None
  end

  module Spill = struct
    type t =
      | R
      | F
      | V

    let to_int : t -> int = function
      | R -> 0
      | F -> 1
      | V -> 2

    let of_int : int -> t option = function
      | 0 -> Some R
      | 1 -> Some F
      | 2 -> Some V
      | _ -> None
  end

  module Reload = struct
    type t =
      | R
      | F
      | V

    let to_int : t -> int = function
      | R -> 0
      | F -> 1
      | V -> 2

    let of_int : int -> t option = function
      | 0 -> Some R
      | 1 -> Some F
      | 2 -> Some V
      | _ -> None
  end

  module ScalarIntAlu = struct
    type t =
      | Add
      | Sub
      | Mul
      | DivS
      | DivU
      | RemS
      | RemU
      | And
      | Or
      | Xor
      | Not
      | Shl
      | ShrU
      | ShrS
      | MinS
      | MaxS

    let to_int : t -> int = function
      | Add -> 0
      | Sub -> 1
      | Mul -> 2
      | DivS -> 3
      | DivU -> 4
      | RemS -> 5
      | RemU -> 6
      | And -> 7
      | Or -> 8
      | Xor -> 9
      | Not -> 10
      | Shl -> 11
      | ShrU -> 12
      | ShrS -> 13
      | MinS -> 14
      | MaxS -> 15

    let of_int : int -> t option = function
      | 0 -> Some Add
      | 1 -> Some Sub
      | 2 -> Some Mul
      | 3 -> Some DivS
      | 4 -> Some DivU
      | 5 -> Some RemS
      | 6 -> Some RemU
      | 7 -> Some And
      | 8 -> Some Or
      | 9 -> Some Xor
      | 10 -> Some Not
      | 11 -> Some Shl
      | 12 -> Some ShrU
      | 13 -> Some ShrS
      | 14 -> Some MinS
      | 15 -> Some MaxS
      | _ -> None
  end

  module ScalarFpAlu = struct
    type t =
      | Add
      | Sub
      | Mul
      | Div
      | Neg
      | Abs
      | Sqrt
      | Min
      | Max
      | Fma
      | Floor
      | Ceil
      | Round
      | I64ToF64
      | F64ToI64
      | SafeDiv

    let to_int : t -> int = function
      | Add -> 0
      | Sub -> 1
      | Mul -> 2
      | Div -> 3
      | Neg -> 4
      | Abs -> 5
      | Sqrt -> 6
      | Min -> 7
      | Max -> 8
      | Fma -> 9
      | Floor -> 10
      | Ceil -> 11
      | Round -> 12
      | I64ToF64 -> 13
      | F64ToI64 -> 14
      | SafeDiv -> 15

    let of_int : int -> t option = function
      | 0 -> Some Add
      | 1 -> Some Sub
      | 2 -> Some Mul
      | 3 -> Some Div
      | 4 -> Some Neg
      | 5 -> Some Abs
      | 6 -> Some Sqrt
      | 7 -> Some Min
      | 8 -> Some Max
      | 9 -> Some Fma
      | 10 -> Some Floor
      | 11 -> Some Ceil
      | 12 -> Some Round
      | 13 -> Some I64ToF64
      | 14 -> Some F64ToI64
      | 15 -> Some SafeDiv
      | _ -> None
  end

  module Scalar3vl = struct
    type t =
      | CmpEqI64
      | CmpNeI64
      | CmpLtI64
      | CmpLeI64
      | CmpLtU64
      | CmpLeU64
      | CmpEqF64
      | CmpNeF64
      | CmpLtF64
      | CmpLeF64
      | And
      | Or
      | Not
      | IsNull
      | IsNotNull
      | Coalesce

    let to_int : t -> int = function
      | CmpEqI64 -> 0
      | CmpNeI64 -> 1
      | CmpLtI64 -> 2
      | CmpLeI64 -> 3
      | CmpLtU64 -> 4
      | CmpLeU64 -> 5
      | CmpEqF64 -> 6
      | CmpNeF64 -> 7
      | CmpLtF64 -> 8
      | CmpLeF64 -> 9
      | And -> 10
      | Or -> 11
      | Not -> 12
      | IsNull -> 13
      | IsNotNull -> 14
      | Coalesce -> 15

    let of_int : int -> t option = function
      | 0 -> Some CmpEqI64
      | 1 -> Some CmpNeI64
      | 2 -> Some CmpLtI64
      | 3 -> Some CmpLeI64
      | 4 -> Some CmpLtU64
      | 5 -> Some CmpLeU64
      | 6 -> Some CmpEqF64
      | 7 -> Some CmpNeF64
      | 8 -> Some CmpLtF64
      | 9 -> Some CmpLeF64
      | 10 -> Some And
      | 11 -> Some Or
      | 12 -> Some Not
      | 13 -> Some IsNull
      | 14 -> Some IsNotNull
      | 15 -> Some Coalesce
      | _ -> None
  end

  module Jmp = struct
    type t =
      | Jmp

    let to_int : t -> int = function
      | Jmp -> 0

    let of_int : int -> t option = function
      | 0 -> Some Jmp
      | _ -> None
  end

  module Jcc = struct
    type t =
      | Jz
      | Jnz
      | Jst
      | Jnst
      | Jnull
      | Jnnull
      | JtrueR
      | JfalseOrNullR
      | JemptyF
      | JnonemptyF

    let to_int : t -> int = function
      | Jz -> 0
      | Jnz -> 1
      | Jst -> 2
      | Jnst -> 3
      | Jnull -> 4
      | Jnnull -> 5
      | JtrueR -> 6
      | JfalseOrNullR -> 7
      | JemptyF -> 8
      | JnonemptyF -> 9

    let of_int : int -> t option = function
      | 0 -> Some Jz
      | 1 -> Some Jnz
      | 2 -> Some Jst
      | 3 -> Some Jnst
      | 4 -> Some Jnull
      | 5 -> Some Jnnull
      | 6 -> Some JtrueR
      | 7 -> Some JfalseOrNullR
      | 8 -> Some JemptyF
      | 9 -> Some JnonemptyF
      | _ -> None
  end

  module LoopDecr = struct
    type t =
      | Decr

    let to_int : t -> int = function
      | Decr -> 0

    let of_int : int -> t option = function
      | 0 -> Some Decr
      | _ -> None
  end

  module Call = struct
    type t =
      | Stride
      | Full16

    let to_int : t -> int = function
      | Stride -> 0
      | Full16 -> 1

    let of_int : int -> t option = function
      | 0 -> Some Stride
      | 1 -> Some Full16
      | _ -> None
  end

  module Ret = struct
    type t =
      | Ret

    let to_int : t -> int = function
      | Ret -> 0

    let of_int : int -> t option = function
      | 0 -> Some Ret
      | _ -> None
  end

  module SetMaxDop = struct
    type t =
      | Imm
      | Reg

    let to_int : t -> int = function
      | Imm -> 0
      | Reg -> 1

    let of_int : int -> t option = function
      | 0 -> Some Imm
      | 1 -> Some Reg
      | _ -> None
  end

  module ScalarDecimalAlu = struct
    type t =
      | AddChk
      | SubChk
      | MulChk
      | MulDivRound
      | DivRound
      | Rescale
      | BoundChk
      | AbsChk
      | NegChk
      | F64ToDec
      | DecToF64
      | RoundScale
      | TruncScale
      | FloorScale
      | CeilScale
      | DivSafe

    let to_int : t -> int = function
      | AddChk -> 0
      | SubChk -> 1
      | MulChk -> 2
      | MulDivRound -> 3
      | DivRound -> 4
      | Rescale -> 5
      | BoundChk -> 6
      | AbsChk -> 7
      | NegChk -> 8
      | F64ToDec -> 9
      | DecToF64 -> 10
      | RoundScale -> 11
      | TruncScale -> 12
      | FloorScale -> 13
      | CeilScale -> 14
      | DivSafe -> 15

    let of_int : int -> t option = function
      | 0 -> Some AddChk
      | 1 -> Some SubChk
      | 2 -> Some MulChk
      | 3 -> Some MulDivRound
      | 4 -> Some DivRound
      | 5 -> Some Rescale
      | 6 -> Some BoundChk
      | 7 -> Some AbsChk
      | 8 -> Some NegChk
      | 9 -> Some F64ToDec
      | 10 -> Some DecToF64
      | 11 -> Some RoundScale
      | 12 -> Some TruncScale
      | 13 -> Some FloorScale
      | 14 -> Some CeilScale
      | 15 -> Some DivSafe
      | _ -> None
  end

  module Fseed = struct
    type t =
      | Empty
      | SingleImm
      | SingleReg
      | InsertReg
      | RemoveReg

    let to_int : t -> int = function
      | Empty -> 0
      | SingleImm -> 1
      | SingleReg -> 2
      | InsertReg -> 3
      | RemoveReg -> 4

    let of_int : int -> t option = function
      | 0 -> Some Empty
      | 1 -> Some SingleImm
      | 2 -> Some SingleReg
      | 3 -> Some InsertReg
      | 4 -> Some RemoveReg
      | _ -> None
  end

  module InitDomainSpan = struct
    type t =
      | AllSpan

    let to_int : t -> int = function
      | AllSpan -> 0

    let of_int : int -> t option = function
      | 0 -> Some AllSpan
      | _ -> None
  end

  module SetOp = struct
    type t =
      | Union
      | Intersect
      | Diff
      | SymDiff

    let to_int : t -> int = function
      | Union -> 0
      | Intersect -> 1
      | Diff -> 2
      | SymDiff -> 3

    let of_int : int -> t option = function
      | 0 -> Some Union
      | 1 -> Some Intersect
      | 2 -> Some Diff
      | 3 -> Some SymDiff
      | _ -> None
  end

  module SetComplement = struct
    type t =
      | Complement

    let to_int : t -> int = function
      | Complement -> 0

    let of_int : int -> t option = function
      | 0 -> Some Complement
      | _ -> None
  end

  module SetCardinality = struct
    type t =
      | Card1bit
      | LanePopSum
      | LaneAnyNodes
      | LaneAllNodes
      | SingleLane

    let to_int : t -> int = function
      | Card1bit -> 0
      | LanePopSum -> 1
      | LaneAnyNodes -> 2
      | LaneAllNodes -> 3
      | SingleLane -> 4

    let of_int : int -> t option = function
      | 0 -> Some Card1bit
      | 1 -> Some LanePopSum
      | 2 -> Some LaneAnyNodes
      | 3 -> Some LaneAllNodes
      | 4 -> Some SingleLane
      | _ -> None
  end

  module SetContains = struct
    type t =
      | Contains1bit
      | GetLaneMask

    let to_int : t -> int = function
      | Contains1bit -> 0
      | GetLaneMask -> 1

    let of_int : int -> t option = function
      | 0 -> Some Contains1bit
      | 1 -> Some GetLaneMask
      | _ -> None
  end

  module SetConvert = struct
    type t =
      | F2vIds
      | V2fIds
      | B2f
      | F2b

    let to_int : t -> int = function
      | F2vIds -> 0
      | V2fIds -> 1
      | B2f -> 2
      | F2b -> 3

    let of_int : int -> t option = function
      | 0 -> Some F2vIds
      | 1 -> Some V2fIds
      | 2 -> Some B2f
      | 3 -> Some F2b
      | _ -> None
  end

  module StableCheck = struct
    type t =
      | FrontierEq
      | VecL1

    let to_int : t -> int = function
      | FrontierEq -> 0
      | VecL1 -> 1

    let of_int : int -> t option = function
      | 0 -> Some FrontierEq
      | 1 -> Some VecL1
      | _ -> None
  end

  module Walk = struct
    type t =
      | Fwd
      | Rev
      | Both
      | FwdFixpointPlus
      | FwdFixpointStar
      | RevFixpointPlus
      | RevFixpointStar
      | FwdBounded
      | CooFwd
      | CooRev

    let to_int : t -> int = function
      | Fwd -> 0
      | Rev -> 1
      | Both -> 2
      | FwdFixpointPlus -> 3
      | FwdFixpointStar -> 4
      | RevFixpointPlus -> 5
      | RevFixpointStar -> 6
      | FwdBounded -> 7
      | CooFwd -> 8
      | CooRev -> 9

    let of_int : int -> t option = function
      | 0 -> Some Fwd
      | 1 -> Some Rev
      | 2 -> Some Both
      | 3 -> Some FwdFixpointPlus
      | 4 -> Some FwdFixpointStar
      | 5 -> Some RevFixpointPlus
      | 6 -> Some RevFixpointStar
      | 7 -> Some FwdBounded
      | 8 -> Some CooFwd
      | 9 -> Some CooRev
      | _ -> None
  end

  module WalkFiltered = struct
    type t =
      | Eq
      | Ne
      | Lt
      | Le
      | Gt
      | Ge
      | IsNotNull
      | IsNull
      | RevEq
      | RevNe
      | RevLt
      | RevLe
      | RevGt
      | RevGe
      | RevIsNotNull
      | RevIsNull

    let to_int : t -> int = function
      | Eq -> 0
      | Ne -> 1
      | Lt -> 2
      | Le -> 3
      | Gt -> 4
      | Ge -> 5
      | IsNotNull -> 6
      | IsNull -> 7
      | RevEq -> 8
      | RevNe -> 9
      | RevLt -> 10
      | RevLe -> 11
      | RevGt -> 12
      | RevGe -> 13
      | RevIsNotNull -> 14
      | RevIsNull -> 15

    let of_int : int -> t option = function
      | 0 -> Some Eq
      | 1 -> Some Ne
      | 2 -> Some Lt
      | 3 -> Some Le
      | 4 -> Some Gt
      | 5 -> Some Ge
      | 6 -> Some IsNotNull
      | 7 -> Some IsNull
      | 8 -> Some RevEq
      | 9 -> Some RevNe
      | 10 -> Some RevLt
      | 11 -> Some RevLe
      | 12 -> Some RevGt
      | 13 -> Some RevGe
      | 14 -> Some RevIsNotNull
      | 15 -> Some RevIsNull
      | _ -> None
  end

  module Degree = struct
    type t =
      | SumFwdR
      | SumRevR
      | VecFwdV
      | VecRevV
      | NodeFwdR
      | NodeRevR

    let to_int : t -> int = function
      | SumFwdR -> 0
      | SumRevR -> 1
      | VecFwdV -> 2
      | VecRevV -> 3
      | NodeFwdR -> 4
      | NodeRevR -> 5

    let of_int : int -> t option = function
      | 0 -> Some SumFwdR
      | 1 -> Some SumRevR
      | 2 -> Some VecFwdV
      | 3 -> Some VecRevV
      | 4 -> Some NodeFwdR
      | 5 -> Some NodeRevR
      | _ -> None
  end

  module Spmv = struct
    type t =
      | FwdPlusTimes
      | RevPlusTimes
      | FwdMinPlus
      | RevMinPlus
      | FwdMaxPlus
      | FwdMaxTimes
      | FwdMinMax
      | FwdFirstSrc
      | FwdArgminPlus

    let to_int : t -> int = function
      | FwdPlusTimes -> 0
      | RevPlusTimes -> 1
      | FwdMinPlus -> 2
      | RevMinPlus -> 3
      | FwdMaxPlus -> 4
      | FwdMaxTimes -> 5
      | FwdMinMax -> 6
      | FwdFirstSrc -> 7
      | FwdArgminPlus -> 8

    let of_int : int -> t option = function
      | 0 -> Some FwdPlusTimes
      | 1 -> Some RevPlusTimes
      | 2 -> Some FwdMinPlus
      | 3 -> Some RevMinPlus
      | 4 -> Some FwdMaxPlus
      | 5 -> Some FwdMaxTimes
      | 6 -> Some FwdMinMax
      | 7 -> Some FwdFirstSrc
      | 8 -> Some FwdArgminPlus
      | _ -> None
  end

  module WalkMorsel = struct
    type t =
      | Fwd
      | Rev
      | CooFwd
      | CooRev

    let to_int : t -> int = function
      | Fwd -> 0
      | Rev -> 1
      | CooFwd -> 2
      | CooRev -> 3

    let of_int : int -> t option = function
      | 0 -> Some Fwd
      | 1 -> Some Rev
      | 2 -> Some CooFwd
      | 3 -> Some CooRev
      | _ -> None
  end

  module FilterMorsel = struct
    type t =
      | Node

    let to_int : t -> int = function
      | Node -> 0

    let of_int : int -> t option = function
      | 0 -> Some Node
      | _ -> None
  end

  module MorselCommit = struct
    type t =
      | YieldFrontier
      | YieldLaneOr
      | ScatterAdd
      | ScatterMin
      | ScatterMax
      | ScatterMinSrc
      | ScatterArgmin
      | ScatterArgmax
      | CountAddR
      | ScatterAddChk

    let to_int : t -> int = function
      | YieldFrontier -> 0
      | YieldLaneOr -> 1
      | ScatterAdd -> 2
      | ScatterMin -> 3
      | ScatterMax -> 4
      | ScatterMinSrc -> 5
      | ScatterArgmin -> 6
      | ScatterArgmax -> 7
      | CountAddR -> 8
      | ScatterAddChk -> 9

    let of_int : int -> t option = function
      | 0 -> Some YieldFrontier
      | 1 -> Some YieldLaneOr
      | 2 -> Some ScatterAdd
      | 3 -> Some ScatterMin
      | 4 -> Some ScatterMax
      | 5 -> Some ScatterMinSrc
      | 6 -> Some ScatterArgmin
      | 7 -> Some ScatterArgmax
      | 8 -> Some CountAddR
      | 9 -> Some ScatterAddChk
      | _ -> None
  end

  module MorselEnd = struct
    type t =
      | End

    let to_int : t -> int = function
      | End -> 0

    let of_int : int -> t option = function
      | 0 -> Some End
      | _ -> None
  end

  module SampleNeighbors = struct
    type t =
      | FrontierWor
      | VecWr
      | RwStepFwd
      | RwStepStay

    let to_int : t -> int = function
      | FrontierWor -> 0
      | VecWr -> 1
      | RwStepFwd -> 2
      | RwStepStay -> 3

    let of_int : int -> t option = function
      | 0 -> Some FrontierWor
      | 1 -> Some VecWr
      | 2 -> Some RwStepFwd
      | 3 -> Some RwStepStay
      | _ -> None
  end

  module HasTopology = struct
    type t =
      | HasCsr
      | HasCsc
      | HasCoo
      | HasDense
      | HasKeyCat
      | HasNodeAttr
      | HasEdgeAttr
      | HasIndex
      | DomainCard
      | RelEdges

    let to_int : t -> int = function
      | HasCsr -> 0
      | HasCsc -> 1
      | HasCoo -> 2
      | HasDense -> 3
      | HasKeyCat -> 4
      | HasNodeAttr -> 5
      | HasEdgeAttr -> 6
      | HasIndex -> 7
      | DomainCard -> 8
      | RelEdges -> 9

    let of_int : int -> t option = function
      | 0 -> Some HasCsr
      | 1 -> Some HasCsc
      | 2 -> Some HasCoo
      | 3 -> Some HasDense
      | 4 -> Some HasKeyCat
      | 5 -> Some HasNodeAttr
      | 6 -> Some HasEdgeAttr
      | 7 -> Some HasIndex
      | 8 -> Some DomainCard
      | 9 -> Some RelEdges
      | _ -> None
  end

  module GraphKernel = struct
    type t =
      | CcAfforest
      | KcoreNums
      | KcoreFrontier
      | TriCountTotal
      | TriCountVec

    let to_int : t -> int = function
      | CcAfforest -> 0
      | KcoreNums -> 1
      | KcoreFrontier -> 2
      | TriCountTotal -> 3
      | TriCountVec -> 4

    let of_int : int -> t option = function
      | 0 -> Some CcAfforest
      | 1 -> Some KcoreNums
      | 2 -> Some KcoreFrontier
      | 3 -> Some TriCountTotal
      | 4 -> Some TriCountVec
      | _ -> None
  end

  module LoadColumn = struct
    type t =
      | NodeAttr
      | EdgeAttr

    let to_int : t -> int = function
      | NodeAttr -> 0
      | EdgeAttr -> 1

    let of_int : int -> t option = function
      | 0 -> Some NodeAttr
      | 1 -> Some EdgeAttr
      | _ -> None
  end

  module GatherNodeAttr = struct
    type t =
      | Vec
      | FrontierCompact
      | Scalar

    let to_int : t -> int = function
      | Vec -> 0
      | FrontierCompact -> 1
      | Scalar -> 2

    let of_int : int -> t option = function
      | 0 -> Some Vec
      | 1 -> Some FrontierCompact
      | 2 -> Some Scalar
      | _ -> None
  end

  module GatherEdgeAttr = struct
    type t =
      | Vec
      | Scalar

    let to_int : t -> int = function
      | Vec -> 0
      | Scalar -> 1

    let of_int : int -> t option = function
      | 0 -> Some Vec
      | 1 -> Some Scalar
      | _ -> None
  end

  module GatherVec = struct
    type t =
      | Gather

    let to_int : t -> int = function
      | Gather -> 0

    let of_int : int -> t option = function
      | 0 -> Some Gather
      | _ -> None
  end

  module NodeFilter = struct
    type t =
      | Eq
      | Ne
      | Lt
      | Le
      | Gt
      | Ge
      | Between
      | IsNull
      | IsNotNull

    let to_int : t -> int = function
      | Eq -> 0
      | Ne -> 1
      | Lt -> 2
      | Le -> 3
      | Gt -> 4
      | Ge -> 5
      | Between -> 6
      | IsNull -> 7
      | IsNotNull -> 8

    let of_int : int -> t option = function
      | 0 -> Some Eq
      | 1 -> Some Ne
      | 2 -> Some Lt
      | 3 -> Some Le
      | 4 -> Some Gt
      | 5 -> Some Ge
      | 6 -> Some Between
      | 7 -> Some IsNull
      | 8 -> Some IsNotNull
      | _ -> None
  end

  module VecCmp = struct
    type t =
      | Eq
      | Ne
      | Lt
      | Le
      | Gt
      | Ge
      | Between
      | InSet

    let to_int : t -> int = function
      | Eq -> 0
      | Ne -> 1
      | Lt -> 2
      | Le -> 3
      | Gt -> 4
      | Ge -> 5
      | Between -> 6
      | InSet -> 7

    let of_int : int -> t option = function
      | 0 -> Some Eq
      | 1 -> Some Ne
      | 2 -> Some Lt
      | 3 -> Some Le
      | 4 -> Some Gt
      | 5 -> Some Ge
      | 6 -> Some Between
      | 7 -> Some InSet
      | _ -> None
  end

  module Vec3vlOp = struct
    type t =
      | And
      | Or
      | Not
      | Xor
      | IsNull
      | IsNotNull
      | IsTrue
      | IsFalse
      | IsNan
      | IsInf
      | IsFinite
      | AssertFinite

    let to_int : t -> int = function
      | And -> 0
      | Or -> 1
      | Not -> 2
      | Xor -> 3
      | IsNull -> 4
      | IsNotNull -> 5
      | IsTrue -> 6
      | IsFalse -> 7
      | IsNan -> 8
      | IsInf -> 9
      | IsFinite -> 10
      | AssertFinite -> 11

    let of_int : int -> t option = function
      | 0 -> Some And
      | 1 -> Some Or
      | 2 -> Some Not
      | 3 -> Some Xor
      | 4 -> Some IsNull
      | 5 -> Some IsNotNull
      | 6 -> Some IsTrue
      | 7 -> Some IsFalse
      | 8 -> Some IsNan
      | 9 -> Some IsInf
      | 10 -> Some IsFinite
      | 11 -> Some AssertFinite
      | _ -> None
  end

  module VecStrPred = struct
    type t =
      | Eq
      | Ne
      | Lt
      | Le
      | Gt
      | Ge
      | StartsWith
      | EndsWith
      | Contains
      | LenEq

    let to_int : t -> int = function
      | Eq -> 0
      | Ne -> 1
      | Lt -> 2
      | Le -> 3
      | Gt -> 4
      | Ge -> 5
      | StartsWith -> 6
      | EndsWith -> 7
      | Contains -> 8
      | LenEq -> 9

    let of_int : int -> t option = function
      | 0 -> Some Eq
      | 1 -> Some Ne
      | 2 -> Some Lt
      | 3 -> Some Le
      | 4 -> Some Gt
      | 5 -> Some Ge
      | 6 -> Some StartsWith
      | 7 -> Some EndsWith
      | 8 -> Some Contains
      | 9 -> Some LenEq
      | _ -> None
  end

  module VecMathArith = struct
    type t =
      | Add
      | Sub
      | Mul
      | Div
      | Rem
      | Min
      | Max
      | Copysign
      | Neg
      | Abs
      | Sqrt
      | Rsqrt
      | Floor
      | Ceil
      | Trunc
      | Round

    let to_int : t -> int = function
      | Add -> 0
      | Sub -> 1
      | Mul -> 2
      | Div -> 3
      | Rem -> 4
      | Min -> 5
      | Max -> 6
      | Copysign -> 7
      | Neg -> 8
      | Abs -> 9
      | Sqrt -> 10
      | Rsqrt -> 11
      | Floor -> 12
      | Ceil -> 13
      | Trunc -> 14
      | Round -> 15

    let of_int : int -> t option = function
      | 0 -> Some Add
      | 1 -> Some Sub
      | 2 -> Some Mul
      | 3 -> Some Div
      | 4 -> Some Rem
      | 5 -> Some Min
      | 6 -> Some Max
      | 7 -> Some Copysign
      | 8 -> Some Neg
      | 9 -> Some Abs
      | 10 -> Some Sqrt
      | 11 -> Some Rsqrt
      | 12 -> Some Floor
      | 13 -> Some Ceil
      | 14 -> Some Trunc
      | 15 -> Some Round
      | _ -> None
  end

  module VecMathExpLog = struct
    type t =
      | Exp
      | Exp2
      | Exp10
      | Expm1
      | Log
      | Log2
      | Log10
      | Log1p
      | Pow
      | Cbrt
      | Hypot
      | Erf
      | Erfc
      | Lgamma

    let to_int : t -> int = function
      | Exp -> 0
      | Exp2 -> 1
      | Exp10 -> 2
      | Expm1 -> 3
      | Log -> 4
      | Log2 -> 5
      | Log10 -> 6
      | Log1p -> 7
      | Pow -> 8
      | Cbrt -> 9
      | Hypot -> 10
      | Erf -> 11
      | Erfc -> 12
      | Lgamma -> 13

    let of_int : int -> t option = function
      | 0 -> Some Exp
      | 1 -> Some Exp2
      | 2 -> Some Exp10
      | 3 -> Some Expm1
      | 4 -> Some Log
      | 5 -> Some Log2
      | 6 -> Some Log10
      | 7 -> Some Log1p
      | 8 -> Some Pow
      | 9 -> Some Cbrt
      | 10 -> Some Hypot
      | 11 -> Some Erf
      | 12 -> Some Erfc
      | 13 -> Some Lgamma
      | _ -> None
  end

  module VecMathTrigHyp = struct
    type t =
      | Sin
      | Cos
      | Tan
      | Asin
      | Acos
      | Atan
      | Atan2
      | Sinc
      | Sinh
      | Cosh
      | Tanh
      | Asinh
      | Acosh
      | Atanh

    let to_int : t -> int = function
      | Sin -> 0
      | Cos -> 1
      | Tan -> 2
      | Asin -> 3
      | Acos -> 4
      | Atan -> 5
      | Atan2 -> 6
      | Sinc -> 7
      | Sinh -> 8
      | Cosh -> 9
      | Tanh -> 10
      | Asinh -> 11
      | Acosh -> 12
      | Atanh -> 13

    let of_int : int -> t option = function
      | 0 -> Some Sin
      | 1 -> Some Cos
      | 2 -> Some Tan
      | 3 -> Some Asin
      | 4 -> Some Acos
      | 5 -> Some Atan
      | 6 -> Some Atan2
      | 7 -> Some Sinc
      | 8 -> Some Sinh
      | 9 -> Some Cosh
      | 10 -> Some Tanh
      | 11 -> Some Asinh
      | 12 -> Some Acosh
      | 13 -> Some Atanh
      | _ -> None
  end

  module VecMathAct = struct
    type t =
      | Relu
      | LeakyRelu
      | Sigmoid
      | Gelu
      | Silu
      | Softplus

    let to_int : t -> int = function
      | Relu -> 0
      | LeakyRelu -> 1
      | Sigmoid -> 2
      | Gelu -> 3
      | Silu -> 4
      | Softplus -> 5

    let of_int : int -> t option = function
      | 0 -> Some Relu
      | 1 -> Some LeakyRelu
      | 2 -> Some Sigmoid
      | 3 -> Some Gelu
      | 4 -> Some Silu
      | 5 -> Some Softplus
      | _ -> None
  end

  module VecIntBitwise = struct
    type t =
      | And
      | Or
      | Xor
      | Not
      | AndNot
      | Shl
      | ShrU
      | ShrS
      | Rotl
      | Rotr
      | Popcount
      | Clz
      | Ctz
      | Bswap

    let to_int : t -> int = function
      | And -> 0
      | Or -> 1
      | Xor -> 2
      | Not -> 3
      | AndNot -> 4
      | Shl -> 5
      | ShrU -> 6
      | ShrS -> 7
      | Rotl -> 8
      | Rotr -> 9
      | Popcount -> 10
      | Clz -> 11
      | Ctz -> 12
      | Bswap -> 13

    let of_int : int -> t option = function
      | 0 -> Some And
      | 1 -> Some Or
      | 2 -> Some Xor
      | 3 -> Some Not
      | 4 -> Some AndNot
      | 5 -> Some Shl
      | 6 -> Some ShrU
      | 7 -> Some ShrS
      | 8 -> Some Rotl
      | 9 -> Some Rotr
      | 10 -> Some Popcount
      | 11 -> Some Clz
      | 12 -> Some Ctz
      | 13 -> Some Bswap
      | _ -> None
  end

  module VecTernary = struct
    type t =
      | FmaV
      | FmaR
      | LerpV
      | LerpR
      | ClampV
      | ClampR
      | SafeDivV
      | SafeDivR
      | TimeValidAtR
      | MulDivI64R

    let to_int : t -> int = function
      | FmaV -> 0
      | FmaR -> 1
      | LerpV -> 2
      | LerpR -> 3
      | ClampV -> 4
      | ClampR -> 5
      | SafeDivV -> 6
      | SafeDivR -> 7
      | TimeValidAtR -> 8
      | MulDivI64R -> 9

    let of_int : int -> t option = function
      | 0 -> Some FmaV
      | 1 -> Some FmaR
      | 2 -> Some LerpV
      | 3 -> Some LerpR
      | 4 -> Some ClampV
      | 5 -> Some ClampR
      | 6 -> Some SafeDivV
      | 7 -> Some SafeDivR
      | 8 -> Some TimeValidAtR
      | 9 -> Some MulDivI64R
      | _ -> None
  end

  module VecBlend = struct
    type t =
      | KleeneVv
      | KleeneVr
      | CaseVv
      | CaseVr

    let to_int : t -> int = function
      | KleeneVv -> 0
      | KleeneVr -> 1
      | CaseVv -> 2
      | CaseVr -> 3

    let of_int : int -> t option = function
      | 0 -> Some KleeneVv
      | 1 -> Some KleeneVr
      | 2 -> Some CaseVv
      | 3 -> Some CaseVr
      | _ -> None
  end

  module Coalesce = struct
    type t =
      | Coalesce

    let to_int : t -> int = function
      | Coalesce -> 0

    let of_int : int -> t option = function
      | 0 -> Some Coalesce
      | _ -> None
  end

  module VecInit = struct
    type t =
      | I64
      | U64
      | I32
      | U32
      | F64
      | F32
      | Bool3vl
      | DomI64
      | DomU64
      | DomI32
      | DomU32
      | DomF64
      | DomF32
      | DomBool3vl

    let to_int : t -> int = function
      | I64 -> 0
      | U64 -> 1
      | I32 -> 2
      | U32 -> 3
      | F64 -> 4
      | F32 -> 5
      | Bool3vl -> 6
      | DomI64 -> 8
      | DomU64 -> 9
      | DomI32 -> 10
      | DomU32 -> 11
      | DomF64 -> 12
      | DomF32 -> 13
      | DomBool3vl -> 14

    let of_int : int -> t option = function
      | 0 -> Some I64
      | 1 -> Some U64
      | 2 -> Some I32
      | 3 -> Some U32
      | 4 -> Some F64
      | 5 -> Some F32
      | 6 -> Some Bool3vl
      | 8 -> Some DomI64
      | 9 -> Some DomU64
      | 10 -> Some DomI32
      | 11 -> Some DomU32
      | 12 -> Some DomF64
      | 13 -> Some DomF32
      | 14 -> Some DomBool3vl
      | _ -> None
  end

  module VecPoint = struct
    type t =
      | VecGet
      | VecSet
      | VecCast
      | VecLen

    let to_int : t -> int = function
      | VecGet -> 0
      | VecSet -> 1
      | VecCast -> 2
      | VecLen -> 3

    let of_int : int -> t option = function
      | 0 -> Some VecGet
      | 1 -> Some VecSet
      | 2 -> Some VecCast
      | 3 -> Some VecLen
      | _ -> None
  end

  module VecReduce = struct
    type t =
      | Sum
      | Min
      | Max
      | CountValid
      | Mean
      | L1Norm
      | L2NormSq
      | Argmin
      | Argmax
      | AnyTrue
      | AllTrue
      | SumI64Chk

    let to_int : t -> int = function
      | Sum -> 0
      | Min -> 1
      | Max -> 2
      | CountValid -> 3
      | Mean -> 4
      | L1Norm -> 5
      | L2NormSq -> 6
      | Argmin -> 7
      | Argmax -> 8
      | AnyTrue -> 9
      | AllTrue -> 10
      | SumI64Chk -> 11

    let of_int : int -> t option = function
      | 0 -> Some Sum
      | 1 -> Some Min
      | 2 -> Some Max
      | 3 -> Some CountValid
      | 4 -> Some Mean
      | 5 -> Some L1Norm
      | 6 -> Some L2NormSq
      | 7 -> Some Argmin
      | 8 -> Some Argmax
      | 9 -> Some AnyTrue
      | 10 -> Some AllTrue
      | 11 -> Some SumI64Chk
      | _ -> None
  end

  module TopK = struct
    type t =
      | DescIds
      | AscIds
      | DescScores
      | AscScores

    let to_int : t -> int = function
      | DescIds -> 0
      | AscIds -> 1
      | DescScores -> 2
      | AscScores -> 3

    let of_int : int -> t option = function
      | 0 -> Some DescIds
      | 1 -> Some AscIds
      | 2 -> Some DescScores
      | 3 -> Some AscScores
      | _ -> None
  end

  module IndexScan = struct
    type t =
      | Eq
      | BetweenCc
      | BetweenCo
      | Lt
      | Le
      | Gt
      | Ge

    let to_int : t -> int = function
      | Eq -> 0
      | BetweenCc -> 1
      | BetweenCo -> 2
      | Lt -> 3
      | Le -> 4
      | Gt -> 5
      | Ge -> 6

    let of_int : int -> t option = function
      | 0 -> Some Eq
      | 1 -> Some BetweenCc
      | 2 -> Some BetweenCo
      | 3 -> Some Lt
      | 4 -> Some Le
      | 5 -> Some Gt
      | 6 -> Some Ge
      | _ -> None
  end

  module MapKeysToDense = struct
    type t =
      | ParamToF
      | VecToV
      | ScalarToR
      | FToF
      | VToV

    let to_int : t -> int = function
      | ParamToF -> 0
      | VecToV -> 1
      | ScalarToR -> 2
      | FToF -> 3
      | VToV -> 4

    let of_int : int -> t option = function
      | 0 -> Some ParamToF
      | 1 -> Some VecToV
      | 2 -> Some ScalarToR
      | 3 -> Some FToF
      | 4 -> Some VToV
      | _ -> None
  end

  module MapDenseToKeys = struct
    type t =
      | Vec
      | FrontierSorted
      | Scalar

    let to_int : t -> int = function
      | Vec -> 0
      | FrontierSorted -> 1
      | Scalar -> 2

    let of_int : int -> t option = function
      | 0 -> Some Vec
      | 1 -> Some FrontierSorted
      | 2 -> Some Scalar
      | _ -> None
  end

  module Collect = struct
    type t =
      | FrontierBitset
      | FrontierIds
      | Vec
      | Scalar
      | TableCol

    let to_int : t -> int = function
      | FrontierBitset -> 0
      | FrontierIds -> 1
      | Vec -> 2
      | Scalar -> 3
      | TableCol -> 4

    let of_int : int -> t option = function
      | 0 -> Some FrontierBitset
      | 1 -> Some FrontierIds
      | 2 -> Some Vec
      | 3 -> Some Scalar
      | 4 -> Some TableCol
      | _ -> None
  end

  module VecDecimalAlu = struct
    type t =
      | AddChk
      | SubChk
      | MulChk
      | MulDivR
      | MulDivV
      | DivRound
      | DivSafe
      | Rescale
      | BoundChk
      | AbsChk
      | NegChk
      | F64ToDec
      | DecToF64
      | RoundScale
      | TruncScale
      | MulDivSafeR

    let to_int : t -> int = function
      | AddChk -> 0
      | SubChk -> 1
      | MulChk -> 2
      | MulDivR -> 3
      | MulDivV -> 4
      | DivRound -> 5
      | DivSafe -> 6
      | Rescale -> 7
      | BoundChk -> 8
      | AbsChk -> 9
      | NegChk -> 10
      | F64ToDec -> 11
      | DecToF64 -> 12
      | RoundScale -> 13
      | TruncScale -> 14
      | MulDivSafeR -> 15

    let of_int : int -> t option = function
      | 0 -> Some AddChk
      | 1 -> Some SubChk
      | 2 -> Some MulChk
      | 3 -> Some MulDivR
      | 4 -> Some MulDivV
      | 5 -> Some DivRound
      | 6 -> Some DivSafe
      | 7 -> Some Rescale
      | 8 -> Some BoundChk
      | 9 -> Some AbsChk
      | 10 -> Some NegChk
      | 11 -> Some F64ToDec
      | 12 -> Some DecToF64
      | 13 -> Some RoundScale
      | 14 -> Some TruncScale
      | 15 -> Some MulDivSafeR
      | _ -> None
  end

  module LaneInitSeeds = struct
    type t =
      | AutoWidth
      | ForceW64

    let to_int : t -> int = function
      | AutoWidth -> 0
      | ForceW64 -> 1

    let of_int : int -> t option = function
      | 0 -> Some AutoWidth
      | 1 -> Some ForceW64
      | _ -> None
  end

  module LaneInitGroups = struct
    type t =
      | Groups

    let to_int : t -> int = function
      | Groups -> 0

    let of_int : int -> t option = function
      | 0 -> Some Groups
      | _ -> None
  end

  module LaneWalk = struct
    type t =
      | Fwd
      | Rev
      | Both
      | FwdFixpointPlus
      | FwdFixpointStar
      | RevFixpointPlus
      | RevFixpointStar
      | FwdEdgeMasked
      | BothFixpointStar
      | BothFixpointStarMasked

    let to_int : t -> int = function
      | Fwd -> 0
      | Rev -> 1
      | Both -> 2
      | FwdFixpointPlus -> 3
      | FwdFixpointStar -> 4
      | RevFixpointPlus -> 5
      | RevFixpointStar -> 6
      | FwdEdgeMasked -> 7
      | BothFixpointStar -> 8
      | BothFixpointStarMasked -> 9

    let of_int : int -> t option = function
      | 0 -> Some Fwd
      | 1 -> Some Rev
      | 2 -> Some Both
      | 3 -> Some FwdFixpointPlus
      | 4 -> Some FwdFixpointStar
      | 5 -> Some RevFixpointPlus
      | 6 -> Some RevFixpointStar
      | 7 -> Some FwdEdgeMasked
      | 8 -> Some BothFixpointStar
      | 9 -> Some BothFixpointStarMasked
      | _ -> None
  end

  module LaneBitwise = struct
    type t =
      | PruneMask
      | KeepMask
      | AndNotLanes
      | ExtractLane

    let to_int : t -> int = function
      | PruneMask -> 0
      | KeepMask -> 1
      | AndNotLanes -> 2
      | ExtractLane -> 3

    let of_int : int -> t option = function
      | 0 -> Some PruneMask
      | 1 -> Some KeepMask
      | 2 -> Some AndNotLanes
      | 3 -> Some ExtractLane
      | _ -> None
  end

  module LaneFilterQuorum = struct
    type t =
      | AtLeast
      | Exact
      | AtMostNonzero

    let to_int : t -> int = function
      | AtLeast -> 0
      | Exact -> 1
      | AtMostNonzero -> 2

    let of_int : int -> t option = function
      | 0 -> Some AtLeast
      | 1 -> Some Exact
      | 2 -> Some AtMostNonzero
      | _ -> None
  end

  module LaneReduceAnd = struct
    type t =
      | ReduceAnd

    let to_int : t -> int = function
      | ReduceAnd -> 0

    let of_int : int -> t option = function
      | 0 -> Some ReduceAnd
      | _ -> None
  end

  module LaneReduceAttr = struct
    type t =
      | Sum
      | Min
      | Max
      | Count

    let to_int : t -> int = function
      | Sum -> 0
      | Min -> 1
      | Max -> 2
      | Count -> 3

    let of_int : int -> t option = function
      | 0 -> Some Sum
      | 1 -> Some Min
      | 2 -> Some Max
      | 3 -> Some Count
      | _ -> None
  end

  module VectorAnnSearch = struct
    type t =
      | Ids
      | Radius

    let to_int : t -> int = function
      | Ids -> 0
      | Radius -> 1

    let of_int : int -> t option = function
      | 0 -> Some Ids
      | 1 -> Some Radius
      | _ -> None
  end

  module VectorRerank = struct
    type t =
      | Dot
      | Cosine
      | NegL2Sq
      | L2Sq
      | PairDot
      | PairCosine
      | PairNegL2Sq
      | PairL2Sq

    let to_int : t -> int = function
      | Dot -> 0
      | Cosine -> 1
      | NegL2Sq -> 2
      | L2Sq -> 3
      | PairDot -> 4
      | PairCosine -> 5
      | PairNegL2Sq -> 6
      | PairL2Sq -> 7

    let of_int : int -> t option = function
      | 0 -> Some Dot
      | 1 -> Some Cosine
      | 2 -> Some NegL2Sq
      | 3 -> Some L2Sq
      | 4 -> Some PairDot
      | 5 -> Some PairCosine
      | 6 -> Some PairNegL2Sq
      | 7 -> Some PairL2Sq
      | _ -> None
  end

  module LaneStateInit = struct
    type t =
      | ZeroF32
      | InfF32
      | ZeroF64
      | InfF64
      | FromFrontierSeeds
      | WithWitness

    let to_int : t -> int = function
      | ZeroF32 -> 0
      | InfF32 -> 1
      | ZeroF64 -> 2
      | InfF64 -> 3
      | FromFrontierSeeds -> 4
      | WithWitness -> 5

    let of_int : int -> t option = function
      | 0 -> Some ZeroF32
      | 1 -> Some InfF32
      | 2 -> Some ZeroF64
      | 3 -> Some InfF64
      | 4 -> Some FromFrontierSeeds
      | 5 -> Some WithWitness
      | _ -> None
  end

  module LaneStateWalk = struct
    type t =
      | FwdMinPlus
      | FwdMaxPlus
      | FwdMaxMul
      | FwdSumMul
      | FwdMinMax
      | RevMinPlus
      | RevMaxPlus
      | RevMaxMul
      | RevSumMul
      | RevMinMax

    let to_int : t -> int = function
      | FwdMinPlus -> 0
      | FwdMaxPlus -> 1
      | FwdMaxMul -> 2
      | FwdSumMul -> 3
      | FwdMinMax -> 4
      | RevMinPlus -> 5
      | RevMaxPlus -> 6
      | RevMaxMul -> 7
      | RevSumMul -> 8
      | RevMinMax -> 9

    let of_int : int -> t option = function
      | 0 -> Some FwdMinPlus
      | 1 -> Some FwdMaxPlus
      | 2 -> Some FwdMaxMul
      | 3 -> Some FwdSumMul
      | 4 -> Some FwdMinMax
      | 5 -> Some RevMinPlus
      | 6 -> Some RevMaxPlus
      | 7 -> Some RevMaxMul
      | 8 -> Some RevSumMul
      | 9 -> Some RevMinMax
      | _ -> None
  end

  module LaneStateOp = struct
    type t =
      | ProjectAffine
      | PruneCutoff
      | PruneHubQuorum
      | ToLaneFrontier
      | ToQuorumFrontier

    let to_int : t -> int = function
      | ProjectAffine -> 0
      | PruneCutoff -> 1
      | PruneHubQuorum -> 2
      | ToLaneFrontier -> 3
      | ToQuorumFrontier -> 4

    let of_int : int -> t option = function
      | 0 -> Some ProjectAffine
      | 1 -> Some PruneCutoff
      | 2 -> Some PruneHubQuorum
      | 3 -> Some ToLaneFrontier
      | 4 -> Some ToQuorumFrontier
      | _ -> None
  end

  module LaneStateReduce = struct
    type t =
      | Min
      | Max
      | Sum
      | Mean
      | Argmin
      | Argmax
      | TracePath

    let to_int : t -> int = function
      | Min -> 0
      | Max -> 1
      | Sum -> 2
      | Mean -> 3
      | Argmin -> 4
      | Argmax -> 5
      | TracePath -> 6

    let of_int : int -> t option = function
      | 0 -> Some Min
      | 1 -> Some Max
      | 2 -> Some Sum
      | 3 -> Some Mean
      | 4 -> Some Argmin
      | 5 -> Some Argmax
      | 6 -> Some TracePath
      | _ -> None
  end

  module VectorPool = struct
    type t =
      | LoadNode
      | MeanPool
      | SumPool
      | L2Norm

    let to_int : t -> int = function
      | LoadNode -> 0
      | MeanPool -> 1
      | SumPool -> 2
      | L2Norm -> 3

    let of_int : int -> t option = function
      | 0 -> Some LoadNode
      | 1 -> Some MeanPool
      | 2 -> Some SumPool
      | 3 -> Some L2Norm
      | _ -> None
  end

  module ExtensionPayload = struct
    type t =
      | Payload

    let to_int : t -> int = function
      | Payload -> 0

    let of_int : int -> t option = function
      | 0 -> Some Payload
      | _ -> None
  end

end
