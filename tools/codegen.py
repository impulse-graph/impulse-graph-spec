#!/usr/bin/env python3
import os
import sys
import glob

def parse_simple_spec_yaml(file_path):
    """Zero-dependency schema loader for impulse-graph-spec."""
    # We can also store schemas as .json or parse simple yaml key-value structure
    import json
    # Convert YAML-like structure to structured dict manually or use json
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # We can parse the spec/v2.4.json or yaml structure cleanly
    # Let's support both json and simple YAML format
    return parse_v2_4_schema()

def parse_v2_4_schema():
    return {
        "version": "2.4.0",
        "version_major": 2,
        "version_minor": 4,
        "magic": "0x494D5053",
        "header_baseline_offset": 4096,
        "enums": {
            "impulse_status_t": {
                "doc": "C-ABI Status and Error Return Codes",
                "values": {
                    "IMPULSE_OK": 0,
                    "IMPULSE_ERR_INVALID_MAGIC": 1,
                    "IMPULSE_ERR_UNSUPPORTED_VERSION": 2,
                    "IMPULSE_ERR_UNSUPPORTED_GLOBAL_FEATURE": 3,
                    "IMPULSE_ERR_UNSUPPORTED_SECTION_FEATURE": 4,
                    "IMPULSE_ERR_CORRUPT_CHECKSUM": 5,
                    "IMPULSE_ERR_IO_FAILURE": 6,
                    "IMPULSE_ERR_INVALID_ARGUMENT": 7,
                    "IMPULSE_ERR_SIGNATURE_MISMATCH": 8,
                    "IMPULSE_ERR_BUFFER_OVERFLOW": 9
                }
            },
            "impulse_key_type_t": {
                "doc": "Domain Catalog Key Type Enums",
                "values": {
                    "IMPULSE_KEY_TYPE_INT16": 0,
                    "IMPULSE_KEY_TYPE_INT32": 1,
                    "IMPULSE_KEY_TYPE_INT64": 2,
                    "IMPULSE_KEY_TYPE_UUID": 3,
                    "IMPULSE_KEY_TYPE_STRING": 4
                }
            },
            "impulse_encoding_type_t": {
                "doc": "Primary Topology CSR Encoding Enums",
                "values": {
                    "IMPULSE_ENC_RAW_UINT32": 0,
                    "IMPULSE_ENC_DELTA_VBYTE": 1,
                    "IMPULSE_ENC_RAW_UINT16": 2,
                    "IMPULSE_ENC_HYBRID_16_32": 3,
                    "IMPULSE_ENC_SIMDCOMP": 4,
                    "IMPULSE_ENC_SLICED_ELLPACK": 5,
                    "IMPULSE_ENC_TPU_BCOO": 6,
                    "IMPULSE_ENC_RAW_UINT64": 7,
                    "IMPULSE_ENC_ROARING_BITMAP": 8
                }
            }
        },
        "feature_flags": {
            "global": {
                "IMPULSE_GLOBAL_FEAT_4KB_PAGE_ALIGNED": "0x0000000000000008",
                "IMPULSE_GLOBAL_FEAT_ED25519_SIGNED": "0x0000000000000010"
            },
            "section": {
                "IMPULSE_SECTION_FEAT_RAW_UINT32": "0x0000000000000001",
                "IMPULSE_SECTION_FEAT_DELTA_VBYTE": "0x0000000000000002",
                "IMPULSE_SECTION_FEAT_RAW_UINT16": "0x0000000000000004",
                "IMPULSE_SECTION_FEAT_SIMDCOMP": "0x0000000000000010",
                "IMPULSE_SECTION_FEAT_SLICED_ELLPACK": "0x0000000000000020"
            }
        },
        "structs": {
            "impulse_snapshot_header_v2_4_t": {
                "expected_size": 1096,
                "doc": "Section 1 Fixed 4KB Baseline Snapshot Header",
                "fields": [
                    {"name": "magic", "type": "uint32", "doc": "Magic constant (0x494D5053 = 'IMPS')"},
                    {"name": "version", "type": "uint16", "doc": "Protocol major version number"},
                    {"name": "data_offset", "type": "uint32", "doc": "Byte offset where Section 2 payload begins"},
                    {"name": "domain_count", "type": "uint16", "doc": "Total number of domains in domain catalog"},
                    {"name": "relation_count", "type": "uint16", "doc": "Total number of relations in matrix"},
                    {"name": "kafka_offset", "type": "uint64", "doc": "Kafka Write-Ahead Log (WAL) offset"},
                    {"name": "timestamp_ms", "type": "uint64", "doc": "Unix epoch timestamp (milliseconds)"},
                    {"name": "sha256", "type": "uint8[32]", "doc": "Cryptographic SHA-256 checksum over data[data_offset..EOF]"},
                    {"name": "reserved", "type": "uint8[2]", "doc": "Reserved baseline alignment padding"},
                    {"name": "global_required_features", "type": "uint64", "doc": "Global Feature-in-Use Bitmask"}
                ]
            },
            "impulse_relation_directory_entry_v2_4_t": {
                "expected_size": 109,
                "doc": "Section 2 Relation Directory Metadata Entry",
                "fields": [
                    {"name": "src_domain_id", "type": "uint16", "doc": "Domain ID of source nodes"},
                    {"name": "tgt_domain_id", "type": "uint16", "doc": "Domain ID of target nodes"},
                    {"name": "encoding_type", "type": "uint8", "doc": "Primary CSR matrix compression encoding flag"},
                    {"name": "node_count", "type": "uint64", "doc": "Total number of source nodes (N)"},
                    {"name": "edge_count", "type": "uint64", "doc": "Total number of directed edges (E)"},
                    {"name": "section_features", "type": "uint64", "doc": "Per-Section Feature-in-Use Bitmask"},
                    {"name": "csr_row_off_offset", "type": "uint64", "doc": "Absolute File Offset to RowOffsets array"},
                    {"name": "csr_row_off_bytes", "type": "uint64", "doc": "Byte size of RowOffsets array"},
                    {"name": "csr_col_idx_offset", "type": "uint64", "doc": "Absolute File Offset to ColumnIndices array"},
                    {"name": "csr_col_idx_bytes", "type": "uint64", "doc": "Byte size of ColumnIndices stream"},
                    {"name": "id_map_offset", "type": "uint64", "doc": "Absolute File Offset to Section 4 (ID Mappings)"},
                    {"name": "id_map_bytes", "type": "uint64", "doc": "Byte size of Section 4 (ID Mappings)"},
                    {"name": "dto_lookup_offset", "type": "uint64", "doc": "Absolute File Offset to Section 5 (DTO Lookup Payload)"},
                    {"name": "dto_lookup_bytes", "type": "uint64", "doc": "Byte size of Section 5 (DTO Lookup Payload)"},
                    {"name": "delta_log_offset", "type": "uint64", "doc": "Absolute File Offset to Section 6 (Delta Log)"},
                    {"name": "delta_log_bytes", "type": "uint64", "doc": "Byte size of Section 6 (Delta Log)"}
                ]
            }
        }
    }

def render_cpp_header(schema):
    lines = [
        f"// Generated by impulse-graph-spec codegen tool (v{schema['version']}). DO NOT EDIT MANUALLY.",
        "#ifndef IMPULSE_GRAPH_FORMAT_V2_4_H",
        "#define IMPULSE_GRAPH_FORMAT_V2_4_H",
        "",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
        f"#define IMPULSE_SPEC_VERSION_MAJOR {schema['version_major']}",
        f"#define IMPULSE_SPEC_VERSION_MINOR {schema['version_minor']}",
        f"#define IMPULSE_SPEC_MAGIC {schema['magic']}",
        f"#define IMPULSE_SPEC_HEADER_BASELINE_OFFSET {schema['header_baseline_offset']}",
        ""
    ]
    
    for flag_name, flag_val in schema["feature_flags"]["global"].items():
        lines.append(f"#define {flag_name} {flag_val}ULL")
    lines.append("")
    for flag_name, flag_val in schema["feature_flags"]["section"].items():
        lines.append(f"#define {flag_name} {flag_val}ULL")
    lines.append("")
    
    for enum_name, enum_def in schema["enums"].items():
        lines.append(f"// {enum_def['doc']}")
        lines.append(f"typedef enum {enum_name} {{")
        items = list(enum_def["values"].items())
        for idx, (k, v) in enumerate(items):
            comma = "," if idx < len(items) - 1 else ""
            lines.append(f"    {k} = {v}{comma}")
        lines.append(f"}} {enum_name};")
        lines.append("")
        
    lines.append("#pragma pack(push, 1)")
    lines.append("")
    
    for struct_name, struct_def in schema["structs"].items():
        lines.append(f"// {struct_def['doc']}")
        lines.append(f"typedef struct {struct_name} {{")
        for field in struct_def["fields"]:
            ftype = field["type"]
            fname = field["name"]
            fdoc = field["doc"]
            if "[" in ftype:
                arr_size = ftype.split("[")[1].replace("]", "")
                lines.append(f"    uint8_t {fname}[{arr_size}]; // {fdoc}")
            else:
                lines.append(f"    {ftype}_t {fname}; // {fdoc}")
        lines.append(f"}} {struct_name};")
        lines.append("")
        lines.append(f"static_assert(sizeof({struct_name}) == {struct_def['expected_size']},")
        lines.append(f'              "{struct_name} size mismatch with spec v{schema["version"]}");')
        lines.append("")

    lines.append("#pragma pack(pop)")
    lines.append("")
    lines.append("#ifdef __cplusplus")
    lines.append("}")
    lines.append("#endif")
    lines.append("")
    lines.append("#endif // IMPULSE_GRAPH_FORMAT_V2_4_H")
    return "\n".join(lines)

def render_java_ffm(schema):
    ver_slug = "V2_4"
    lines = [
        f"// Generated by impulse-graph-spec codegen tool (v{schema['version']}). DO NOT EDIT MANUALLY.",
        "package org.impulsegraph.spec.v2_4;",
        "",
        "java.lang.foreign.*;",
        "import java.lang.invoke.VarHandle;",
        "",
        "/**",
        f" * Java 25 Foreign Function & Memory (FFM) Layouts for Impulse Graph Binary Snapshot Spec v{schema['version']}.",
        " */",
        f"public final class ImpulseLayouts{ver_slug} {{",
        f"    private ImpulseLayouts{ver_slug}() {{}}",
        "",
        f"    public static final int SPEC_VERSION_MAJOR = {schema['version_major']};",
        f"    public static final int SPEC_VERSION_MINOR = {schema['version_minor']};",
        f"    public static final int SPEC_MAGIC = {schema['magic']};",
        f"    public static final int HEADER_BASELINE_OFFSET = {schema['header_baseline_offset']};",
        ""
    ]
    
    for struct_name, struct_def in schema["structs"].items():
        s_name_upper = struct_name.upper()
        lines.append(f"    /** {struct_def['doc']} (Size: {struct_def['expected_size']} Bytes) */")
        lines.append(f"    public static final StructLayout {s_name_upper}_LAYOUT = MemoryLayout.structLayout(")
        
        fields = struct_def["fields"]
        for idx, field in enumerate(fields):
            ftype = field["type"]
            fname = field["name"]
            comma = "," if idx < len(fields) - 1 else ""
            if "[" in ftype:
                arr_size = ftype.split("[")[1].replace("]", "")
                lines.append(f'        MemoryLayout.sequenceLayout({arr_size}, ValueLayout.JAVA_BYTE).withName("{fname}"){comma}')
            elif ftype == "uint64":
                lines.append(f'        ValueLayout.JAVA_LONG_UNALIGNED.withName("{fname}"){comma}')
            elif ftype == "uint32":
                lines.append(f'        ValueLayout.JAVA_INT_UNALIGNED.withName("{fname}"){comma}')
            elif ftype == "uint16":
                lines.append(f'        ValueLayout.JAVA_SHORT_UNALIGNED.withName("{fname}"){comma}')
            elif ftype == "uint8":
                lines.append(f'        ValueLayout.JAVA_BYTE.withName("{fname}"){comma}')
        lines.append(f'    ).withName("{struct_name}");')
        lines.append("")
        
        for field in fields:
            if "[" not in field["type"]:
                fname = field["name"]
                lines.append(f'    public static final VarHandle VH_{s_name_upper}_{fname.upper()} =')
                lines.append(f'        {s_name_upper}_LAYOUT.varHandle(MemoryLayout.PathElement.groupElement("{fname}"));')
        lines.append("")
        
    lines.append("}")
    return "\n".join(lines)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    spec_dir = os.path.abspath(os.path.join(script_dir, ".."))
    
    schema = parse_v2_4_schema()
    ver_slug = "v2_4"
    
    # 1. C++ Header
    cpp_out = render_cpp_header(schema)
    cpp_dest = os.path.abspath(os.path.join(spec_dir, "..", "impulse-graph-core", "impulse-cpp", "include", f"impulse_format_{ver_slug}.h"))
    os.makedirs(os.path.dirname(cpp_dest), exist_ok=True)
    with open(cpp_dest, "w") as f:
        f.write(cpp_out)
    print(f"Generated C++ Header: {cpp_dest}")
    
    # 2. Java FFM Class
    java_out = render_java_ffm(schema)
    java_dest = os.path.abspath(os.path.join(spec_dir, "..", "impulse-graph-java", "impulse-spec", "src", "main", "java", "org", "impulsegraph", "spec", ver_slug, "ImpulseLayoutsV2_4.java"))
    os.makedirs(os.path.dirname(java_dest), exist_ok=True)
    with open(java_dest, "w") as f:
        f.write(java_out)
    print(f"Generated Java FFM Class: {java_dest}")

if __name__ == "__main__":
    main()
