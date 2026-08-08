#!/usr/bin/env python3
import os
import sys
import glob

def get_v0_9_schema():
    return {
        "version": "0.9.0",
        "version_major": 0,
        "version_minor": 9,
        "magic": "0x494D5053",
        "header_baseline_offset": 4096,
        "enums": {
            "impulse_status_t": {
                "doc": "C-ABI Status and Error Return Codes (v0.9.0)",
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
                "doc": "Domain Catalog Key Type Enums (v0.9.0)",
                "values": {
                    "IMPULSE_KEY_TYPE_INT8": 1,
                    "IMPULSE_KEY_TYPE_INT16": 2,
                    "IMPULSE_KEY_TYPE_INT32": 3,
                    "IMPULSE_KEY_TYPE_INT64": 4,
                    "IMPULSE_KEY_TYPE_UINT8": 5,
                    "IMPULSE_KEY_TYPE_UINT16": 6,
                    "IMPULSE_KEY_TYPE_UINT32": 7,
                    "IMPULSE_KEY_TYPE_UINT64": 8,
                    "IMPULSE_KEY_TYPE_FLOAT32": 9,
                    "IMPULSE_KEY_TYPE_FLOAT64": 10,
                    "IMPULSE_KEY_TYPE_VAR_STRING": 11,
                    "IMPULSE_KEY_TYPE_UUID128": 12
                }
            },
            "impulse_encoding_type_t": {
                "doc": "Primary Topology CSR Encoding Enums (v0.9.0)",
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
                "IMPULSE_GLOBAL_FEAT_4KB_PAGE_ALIGNED": "0x0000000000000001",
                "IMPULSE_GLOBAL_FEAT_CRYPTO_SIGNED": "0x0000000000000002",
                "IMPULSE_GLOBAL_FEAT_FOOTER_CATALOG": "0x0000000000000004"
            },
            "section": {
                "IMPULSE_SECTION_FEAT_RAW_UINT32": "0x0000000000000001",
                "IMPULSE_SECTION_FEAT_DELTA_VBYTE": "0x0000000000000002",
                "IMPULSE_SECTION_FEAT_RAW_UINT16": "0x0000000000000004",
                "IMPULSE_SECTION_FEAT_SIMDCOMP": "0x0000000000000010"
            }
        },
        "structs": {
            "impulse_snapshot_header_v0_9_t": {
                "expected_size": 4096,
                "doc": "Section 1 Fixed 4KB Baseline Snapshot Header (Spec v0.9.0)",
                "fields": [
                    {"name": "magic", "type": "uint32", "doc": "Magic constant (0x494D5053 = 'IMPS')"},
                    {"name": "version", "type": "uint16", "doc": "Protocol version number (0x0009)"},
                    {"name": "data_offset", "type": "uint32", "doc": "Byte offset where Section 2 payload begins (4096)"},
                    {"name": "domain_count", "type": "uint16", "doc": "Total number of domains in catalog"},
                    {"name": "relation_count", "type": "uint16", "doc": "Total number of relations in matrix"},
                    {"name": "timestamp_ms", "type": "uint64", "doc": "Unix epoch timestamp (milliseconds)"},
                    {"name": "required_features", "type": "uint64", "doc": "Global feature flags bitmask"},
                    {"name": "footer_directory_offset", "type": "uint64", "doc": "Absolute file offset to Footer Directory Table"},
                    {"name": "footer_directory_bytes", "type": "uint64", "doc": "Byte size of Footer Directory Table"},
                    {"name": "snapshot_uuid", "type": "uint8[16]", "doc": "128-bit Binary UUID"},
                    {"name": "header_checksum", "type": "uint16", "doc": "CRC-16-CCITT checksum over bytes 0x00..0x3D"},
                    {"name": "header_padding", "type": "uint8[4032]", "doc": "Reserved header expansion padding"}
                ]
            },
            "impulse_domain_catalog_entry_v0_9_t": {
                "expected_size": 16,
                "doc": "Section 2 Domain Catalog Entry (16 Bytes)",
                "fields": [
                    {"name": "domain_id", "type": "uint16", "doc": "Zero-indexed domain identifier"},
                    {"name": "key_type", "type": "uint8", "doc": "Domain key primitive type enum"},
                    {"name": "reserved", "type": "uint8", "doc": "Alignment padding"},
                    {"name": "name_offset", "type": "uint32", "doc": "Offset into Shared String Table"},
                    {"name": "node_count", "type": "uint64", "doc": "Total node count in domain"}
                ]
            },
            "impulse_relation_directory_entry_v0_9_t": {
                "expected_size": 128,
                "doc": "Section 2 Relation Directory Entry (128 Bytes)",
                "fields": [
                    {"name": "relation_id", "type": "uint16", "doc": "Zero-indexed relation identifier"},
                    {"name": "src_domain_id", "type": "uint16", "doc": "Source domain ID"},
                    {"name": "tgt_domain_id", "type": "uint16", "doc": "Target domain ID"},
                    {"name": "encoding_id", "type": "uint8", "doc": "Topology encoding type enum"},
                    {"name": "node_id_width", "type": "uint8", "doc": "Node index width (bits)"},
                    {"name": "edge_index_width", "type": "uint8", "doc": "Edge index width (bits)"},
                    {"name": "reserved1", "type": "uint8[3]", "doc": "Reserved alignment"},
                    {"name": "name_offset", "type": "uint32", "doc": "Offset into Shared String Table"},
                    {"name": "node_count", "type": "uint64", "doc": "Source node count"},
                    {"name": "edge_count", "type": "uint64", "doc": "Edge count"},
                    {"name": "section_features", "type": "uint64", "doc": "Section feature bitmask"},
                    {"name": "csr_row_off_offset", "type": "uint64", "doc": "CSR row offsets file offset"},
                    {"name": "csr_row_off_bytes", "type": "uint64", "doc": "CSR row offsets byte size"},
                    {"name": "csr_col_idx_offset", "type": "uint64", "doc": "CSR col indices file offset"},
                    {"name": "csr_col_idx_bytes", "type": "uint64", "doc": "CSR col indices byte size"},
                    {"name": "csc_row_off_offset", "type": "uint64", "doc": "CSC row offsets file offset"},
                    {"name": "csc_row_off_bytes", "type": "uint64", "doc": "CSC row offsets byte size"},
                    {"name": "csc_col_idx_offset", "type": "uint64", "doc": "CSC col indices file offset"},
                    {"name": "csc_col_idx_bytes", "type": "uint64", "doc": "CSC col indices byte size"},
                    {"name": "attribute_count", "type": "uint16", "doc": "Number of edge attribute descriptors"},
                    {"name": "reserved2", "type": "uint8[22]", "doc": "Directory entry expansion padding"}
                ]
            },
            "impulse_footer_trailer_v0_9_t": {
                "expected_size": 16,
                "doc": "16-Byte Footer Trailer at EOF",
                "fields": [
                    {"name": "footer_length", "type": "uint64", "doc": "Byte size of Footer Block"},
                    {"name": "spec_version", "type": "uint32", "doc": "Spec version (0x0009)"},
                    {"name": "footer_magic", "type": "uint32", "doc": "Footer magic (0x494D5053 = 'IMPS')"}
                ]
            }
        }
    }

def render_cpp_header(schema):
    ver_slug = f"v{schema['version_major']}_{schema['version_minor']}"
    guard = f"IMPULSE_GRAPH_FORMAT_{ver_slug.upper()}_H"
    lines = [
        f"// Generated by impulse-graph-spec codegen tool (v{schema['version']}). DO NOT EDIT MANUALLY.",
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
        f"#define IMPULSE_SPEC_VERSION_MAJOR_{ver_slug.upper()} {schema['version_major']}",
        f"#define IMPULSE_SPEC_VERSION_MINOR_{ver_slug.upper()} {schema['version_minor']}",
        f"#define IMPULSE_SPEC_MAGIC_{ver_slug.upper()} {schema['magic']}",
        f"#define IMPULSE_SPEC_HEADER_BASELINE_OFFSET_{ver_slug.upper()} {schema['header_baseline_offset']}",
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
            fname = field["name"]
            ftype = field["type"]
            fdoc = field.get("doc", "")
            
            if "[" in ftype and "]" in ftype:
                base_type, arr_spec = ftype.split("[")
                arr_len = arr_spec.rstrip("]")
                type_str = f"{base_type} {fname}[{arr_len}];"
            else:
                type_str = f"{ftype}_t {fname};" if ftype in ["uint8", "uint16", "uint32", "uint64", "int8", "int16", "int32", "int64"] else f"{ftype} {fname};"
                
            comment_str = f" // {fdoc}" if fdoc else ""
            lines.append(f"    {type_str:<32}{comment_str}")
        lines.append(f"}} {struct_name};")
        lines.append("")
        
    lines.append("#pragma pack(pop)")
    lines.append("")
    lines.append("#ifdef __cplusplus")
    lines.append("}")
    lines.append("#endif")
    lines.append("")
    lines.append(f"#endif // {guard}")
    return "\n".join(lines)

def render_java_ffm(schema):
    ver_slug = f"v{schema['version_major']}_{schema['version_minor']}"
    class_name = f"ImpulseLayoutsV{schema['version_major']}_{schema['version_minor']}"
    lines = [
        f"// Generated by impulse-graph-spec codegen tool (v{schema['version']}). DO NOT EDIT MANUALLY.",
        f"package org.impulsegraph.spec.{ver_slug};",
        "",
        "import java.lang.foreign.MemoryLayout;",
        "import java.lang.foreign.ValueLayout;",
        "import java.lang.foreign.StructLayout;",
        "",
        f"public final class {class_name} {{",
        f"    private {class_name}() {{}}",
        "",
        f"    public static final short VERSION_MAJOR = {schema['version_major']};",
        f"    public static final short VERSION_MINOR = {schema['version_minor']};",
        f"    public static final int MAGIC = {schema['magic']};",
        f"    public static final int HEADER_BASELINE_OFFSET = {schema['header_baseline_offset']};",
        ""
    ]
    
    for struct_name, struct_def in schema["structs"].items():
        layout_name = f"{struct_name.upper()}_LAYOUT"
        lines.append(f"    // {struct_def['doc']}")
        lines.append(f"    public static final StructLayout {layout_name} = MemoryLayout.structLayout(")
        
        field_lines = []
        for field in struct_def["fields"]:
            fname = field["name"]
            ftype = field["type"]
            
            if "[" in ftype and "]" in ftype:
                base_type, arr_spec = ftype.split("[")
                arr_len = int(arr_spec.rstrip("]"))
                field_lines.append(f'        MemoryLayout.sequenceLayout({arr_len}, ValueLayout.JAVA_BYTE).withName("{fname}")')
            elif ftype in ["uint8", "int8"]:
                field_lines.append(f'        ValueLayout.JAVA_BYTE.withName("{fname}")')
            elif ftype in ["uint16", "int16"]:
                field_lines.append(f'        ValueLayout.JAVA_SHORT.withName("{fname}")')
            elif ftype in ["uint32", "int32"]:
                field_lines.append(f'        ValueLayout.JAVA_INT.withName("{fname}")')
            elif ftype in ["uint64", "int64"]:
                field_lines.append(f'        ValueLayout.JAVA_LONG.withName("{fname}")')
            else:
                field_lines.append(f'        ValueLayout.JAVA_BYTE.withName("{fname}")')
                
        lines.append(",\n".join(field_lines))
        lines.append(f'    ).withName("{struct_name}");')
        lines.append("")
        
    lines.append("}")
    return "\n".join(lines)

def render_markdown_spec(schema):
    ver_dot = f"v{schema['version_major']}.{schema['version_minor']}"
    lines = [
        f"# Normative Binary Specification: Impulse Graph Format ({schema['version']})",
        "",
        f"This document is automatically generated from the normative specification schema `{ver_dot}.yaml`.",
        "",
        "---",
        "",
        "## 1. Executive Summary & Header Baseline",
        "",
        f"- **Magic Constant**: `{schema['magic']}` (`IMPS`)",
        f"- **Protocol Version**: `{schema['version']}` (`0x{schema['version_major']:02X}{schema['version_minor']:02X}`)",
        f"- **Header Offset Baseline**: `{schema['header_baseline_offset']}` bytes (Page 0)",
        "",
        "---",
        "",
        "## 2. Enumeration Types",
        ""
    ]
    
    for enum_name, enum_def in schema["enums"].items():
        lines.append(f"### `{enum_name}`")
        lines.append(f"*{enum_def['doc']}*")
        lines.append("")
        lines.append("| Name | Value |")
        lines.append("| :--- | :--- |")
        for k, v in enum_def["values"].items():
            lines.append(f"| `{k}` | `{v}` |")
        lines.append("")
        
    lines.append("---")
    lines.append("")
    lines.append("## 3. Binary Layout Structs")
    lines.append("")
    
    for struct_name, struct_def in schema["structs"].items():
        lines.append(f"### `{struct_name}`")
        lines.append(f"*{struct_def['doc']}* (Expected Size: {struct_def['expected_size']} bytes)")
        lines.append("")
        lines.append("| Field Name | Type | Description |")
        lines.append("| :--- | :--- | :--- |")
        for field in struct_def["fields"]:
            lines.append(f"| `{field['name']}` | `{field['type']}` | {field.get('doc', '')} |")
        lines.append("")
        
    return "\n".join(lines)

def render_spec_version_index():
    return """# Impulse Graph Binary Snapshot Specification Hub

Welcome to the **Impulse Graph C-ABI Binary Snapshot Specification** hub.

The specification defines the zero-copy, memory-mapped binary snapshot layout (`*.imps`) used across C++, Java 25, Rust, Python, Go, and C#.

---

## Available Specification Versions

| Version | Status | Highlights | Specification Document |
| :--- | :--- | :--- | :--- |
| **v0.9.0** | 🟢 **Current Baseline** | 4KB Page 0 Header Baseline, Shared String Table, 128-Byte Alignment, Single-Pass Cloud S3 Writer | [Read Specification v0.9.0](v0.9.0.md) |

---

## Version Compatibility Policy

- **Minor Version Bumps (e.g. v0.9 -> v0.10)**: Fully backward-compatible. Additive feature bitmask flags or appended optional sections.
- **Major Version Bumps (e.g. v0.9 -> v1.0)**: May change structural header layouts or binary alignment bounds.
"""

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    spec_dir = os.path.abspath(os.path.join(script_dir, ".."))
    website_dir = os.path.abspath(os.path.join(spec_dir, "..", "impulse-website"))
    
    schemas = [get_v0_9_schema()]
    
    for schema in schemas:
        ver_slug = f"v{schema['version_major']}_{schema['version_minor']}"
        ver_dot = f"v{schema['version_major']}.{schema['version_minor']}"
        print(f"Processing spec schema: {ver_dot} ({schema['version']})")
        
        # 1. C++ Header
        cpp_out = render_cpp_header(schema)
        cpp_dest = os.path.abspath(os.path.join(spec_dir, "..", "impulse-graph-core", "impulse-cpp", "include", f"impulse_format_{ver_slug}.h"))
        os.makedirs(os.path.dirname(cpp_dest), exist_ok=True)
        with open(cpp_dest, "w") as f:
            f.write(cpp_out)
        print(f"  Generated C++ Header: {cpp_dest}")
        
        # 2. Java FFM Class
        java_out = render_java_ffm(schema)
        java_dest = os.path.abspath(os.path.join(spec_dir, "..", "impulse-graph-java", "impulse-spec", "src", "main", "java", "org", "impulsegraph", "spec", ver_slug, f"ImpulseLayoutsV{schema['version_major']}_{schema['version_minor']}.java"))
        os.makedirs(os.path.dirname(java_dest), exist_ok=True)
        with open(java_dest, "w") as f:
            f.write(java_out)
        print(f"  Generated Java FFM Class: {java_dest}")
        
        # 3. Markdown Spec Documents
        md_out = render_markdown_spec(schema)
        
        # In impulse-graph-spec/docs/
        spec_doc_dest = os.path.join(spec_dir, "docs", f"spec_{ver_dot}.md")
        with open(spec_doc_dest, "w") as f:
            f.write(md_out)
        print(f"  Generated Spec Doc: {spec_doc_dest}")
        
        # In impulse-website/docs/reference/spec/
        web_doc_dest = os.path.join(website_dir, "docs", "reference", "spec", f"{ver_dot}.md")
        os.makedirs(os.path.dirname(web_doc_dest), exist_ok=True)
        with open(web_doc_dest, "w") as f:
            f.write(md_out)
        print(f"  Generated Website Spec Doc: {web_doc_dest}")

    # 4. Generate Website Version Hub (index.md)
    web_hub_dest = os.path.join(website_dir, "docs", "reference", "spec", "index.md")
    with open(web_hub_dest, "w") as f:
        f.write(render_spec_version_index())
    print(f"  Generated Website Version Hub: {web_hub_dest}")

if __name__ == "__main__":
    main()
