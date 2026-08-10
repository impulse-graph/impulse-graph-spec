# Impulse Graph Engine — Snapshot Schema Specification v0.9.0 (`.imps.schema.yaml`)

This document defines the normative specification for **Impulse Graph Snapshot Schemas** (`.imps.schema.yaml`). 

The schema provides a declarative, language-agnostic representation of graph domain catalogs, property attributes, relational cardinalities, and virtual relations. It powers **compile-time type checking**, **automated DTO code generation** (Java, Kotlin, C#, Rust, TypeScript), and **bidirectional CLI validation** across the Impulse Graph Engine ecosystem.

---

## 1. File Naming & Format Conventions

* **File Extension**: `.imps.schema.yaml` or `.imps.schema.json`
* **Encoding**: UTF-8 without BOM.
* **Specification Version**: `"0.9.0"`

---

## 2. Top-Level Schema Structure

An `.imps.schema.yaml` document consists of four primary sections:

1. **`schema_version`**: String version identifier matching specification (e.g., `"0.9.0"`).
2. **`metadata`**: Namespace, package targets, authoring details, and documentation.
3. **`domains`**: List of vertex/entity domain type definitions.
4. **`relations`**: List of physical edge relation definitions (CSR/CSC).
5. **`virtual_relations`**: List of computed/derived relation definitions (`ImpK`/`ImpLog`).

```yaml
schema_version: "0.9.0"
metadata:
  name: "EnterpriseKnowledgeGraph"
  namespace: "com.mycompany.graph.model"
  description: "Organizational graph with users, groups, permissions, and derived reachability."

domains: [...]
relations: [...]
virtual_relations: [...]
```

---

## 3. Domains & Key Types

A **Domain** represents a distinct node/entity classification in the graph catalog (e.g., `User`, `Group`, `Device`).

### 3.1 Domain Attributes
* **`id`**: 16-bit unsigned integer (`0`..`65535`) domain catalog identifier.
* **`name`**: Unique string name (ASCII alphanumeric + underscores).
* **`key_type`**: Primary key data format used for node identity lookup.

### 3.2 Supported Key Types
| Key Type | Binary Format | Description |
| :--- | :--- | :--- |
| `Int32` | 32-bit signed int | Compact integer keys (up to 2 billion nodes). |
| `Int64` | 64-bit signed int | High-range 64-bit integer keys. |
| `UUID128` | 128-bit raw bytes | Standard 16-byte UUID / GUID identifiers. |
| `String` | Variable-length UTF-8 | String keys resolved via Section 2 Global String Table. |

---

## 4. Property Attributes & Data Types

Both **Domains** and **Relations** can contain Structure-of-Arrays (SoA) property attributes.

### 4.1 Attribute Specification Fields
* **`name`**: Attribute string identifier (e.g., `email`, `embedding`).
* **`type`**: Primitive or string data type (see §4.2).
* **`dimension`**: Positive integer indicating array/vector dimension (`1` = scalar, `N` = fixed vector).
* **`nullable`**: Boolean (`true`/`false`), defaults to `false`.

### 4.2 Supported Attribute Data Types

| Data Type | Memory Size | Description |
| :--- | :--- | :--- |
| `Int8` | 1 byte | Signed 8-bit integer. |
| `Int16` | 2 bytes | Signed 16-bit integer. |
| `Int32` | 4 bytes | Signed 32-bit integer. |
| `Int64` | 8 bytes | Signed 64-bit integer. |
| `Float32` | 4 bytes | Single-precision IEEE 754 float. |
| `Float64` | 8 bytes | Double-precision IEEE 754 float. |
| `Bool` | 1 byte | Boolean flag (`0x00` or `0x01`). |
| `TimestampMicro` | 8 bytes | 64-bit microsecond Unix epoch timestamp. |
| `FixedString(N)` | `N` bytes | **Fixed-Length String**: Zero-padded ASCII/UTF-8 string of exact length `N` bytes (e.g. `FixedString(16)` for ISO codes, hashes, currency). Fast fixed-stride scanning. |
| `VarString` | Variable | **Variable-Length String**: Indirect string pool reference pointing to UTF-8 null-terminated bytes in global string table. |

```yaml
domains:
  - id: 0
    name: "User"
    key_type: "UUID128"
    attributes:
      - name: "account_status"
        type: "FixedString(8)"   # e.g., "ACTIVE  ", "SUSPEND "
        dimension: 1
      - name: "display_name"
        type: "VarString"        # Variable length UTF-8
        dimension: 1
      - name: "embedding"
        type: "Float32"          # 128-dimension vector
        dimension: 128
      - name: "last_login"
        type: "TimestampMicro"
        dimension: 1
        nullable: true
```

---

## 5. Physical Relations & Cardinalities

A **Relation** defines a physical adjacency matrix stored in Compressed Sparse Row (CSR) or Compressed Sparse Column (CSC) format.

### 5.1 Relation Specification Fields
* **`id`**: 16-bit unsigned integer relation catalog identifier.
* **`name`**: Relation string name (e.g., `MEMBER_OF`, `FOLLOWS`).
* **`src_domain`**: Name of source domain.
* **`tgt_domain`**: Name of target domain.
* **`cardinality`**: Relational constraint (see §5.2).
* **`encoding`**: Physical index compression format (`RawUint16`, `RawUint32`, `RawUint64`, `DeltaVByte`, `SIMDComp`).
* **`attributes`**: Optional edge property attribute list (e.g., edge weight, role).

### 5.2 Supported Relation Cardinalities

| Cardinality | Expression | Codegen & VM Constraint Rules |
| :--- | :--- | :--- |
| `one_to_one` | $1:1$ | Out-degree $\le 1$, In-degree $\le 1$. Generated DTOs bind directly to scalar single entity references (`User getManager()`). |
| `one_to_many` | $1:N$ | Source has multiple target neighbors; Target has at most 1 source (`List<Order> getOrders()`). |
| `many_to_one` | $N:1$ | Source has at most 1 target neighbor; Target has multiple sources (`Department getDepartment()`). |
| `many_to_many` | $N:M$ | Standard multi-graph relation (`List<Group> getGroups()`). |

```yaml
relations:
  - id: 0
    name: "REPORTS_TO"
    src_domain: "User"
    tgt_domain: "User"
    cardinality: "many_to_one"    # Each user has at most 1 direct manager
    encoding: "RawUint32"

  - id: 1
    name: "MEMBER_OF"
    src_domain: "User"
    tgt_domain: "Group"
    cardinality: "many_to_many"   # Users belong to multiple groups
    encoding: "SIMDComp"
    attributes:
      - name: "role"
        type: "VarString"
        dimension: 1
      - name: "assigned_at"
        type: "TimestampMicro"
        dimension: 1
```

---

## 6. Virtual Relations (Computed & Derived Graphs)

A **Virtual Relation** defines an on-the-fly or cached relation computed dynamically via an **ImpK** (matrix algebra) or **ImpLog** (Datalog rule) expression. Virtual relations consume **zero physical disk space** in `.imps` snapshot files.

### 6.1 Virtual Relation Specification Fields
* **`name`**: Virtual relation name.
* **`src_domain`**: Source domain name.
* **`tgt_domain`**: Target domain name.
* **`cardinality`**: Computed cardinality (`one_to_many`, `many_to_many`).
* **`language`**: Compiler frontend language (`ImpK`, `ImpLog`, or `ImpScheme`).
* **`query`**: Inline query expression or rule defining the edge computation.
* **`caching`**: Execution cache strategy (`none`, `transient`, `materialized`).

```yaml
virtual_relations:
  - name: "TRANSITIVE_MEMBER_OF"
    src_domain: "User"
    tgt_domain: "Group"
    cardinality: "many_to_many"
    language: "ImpLog"
    query: |
      TRANSITIVE_MEMBER_OF(u, g) :- MEMBER_OF(u, g).
      TRANSITIVE_MEMBER_OF(u, g2) :- MEMBER_OF(u, g1), PARENT_GROUP(g1, g2).
    caching: "transient"

  - name: "CO_WORKER"
    src_domain: "User"
    tgt_domain: "User"
    cardinality: "many_to_many"
    language: "ImpK"
    query: |
      MATCH (u1:User)-[:MEMBER_OF]->(g:Group)<-[:MEMBER_OF]-(u2:User)
      WHERE u1 != u2
      RETURN u1, u2
    caching: "none"
```

---

## 7. Codegen & Annotations Specification

The schema serves as the primary metadata source for strongly-typed DTO generation and compile-time `@ImpKQuery` validation.

### 7.1 Java / Kotlin Repository Codegen Example

Given `schema.imps.schema.yaml` with Java codegen target configuration:

```yaml
metadata:
  namespace: "com.mycompany.graph.model"
  codegen:
    java:
      dto_style: "value_class" # Options: "value_class" (Project Valhalla), "record", "pojo"
```

1. `impulse-codegen` generates Java 25+ Project Valhalla `value class` (naked struct) DTOs:
   ```java
   // Project Valhalla Value Class (Zero object header overhead, flattened memory)
   public value class UserDto {
       public final long key;
       public final float score;
       public final double latitude;
       public final double longitude;
   }
   ```
2. Build-time plugins validate `@ImpKQuery` methods against the schema:
   ```java
   @ImpulseRepository
   public interface UserGraphRepository {

       // Verified at build time against schema.imps.schema.yaml
       @ImpKQuery("""
           MATCH (u:User {key: $user.key})-[:TRANSITIVE_MEMBER_OF]->(g:Group)
           RETURN g.title
           """)
       List<String> getTransitiveGroupTitles(UserDto user);
   }
   ```

---

## 8. CLI Tooling Integration (`impulse-cli`)

* **Schema Export (Reversal)**: Reconstruct a `.imps.schema.yaml` file from any physical `.imps` snapshot:
  ```bash
  impulse schema export production.imps -o schema.imps.yaml
  ```
* **Schema Validation**: Validate a YAML schema file for structural syntax and topological consistency:
  ```bash
  impulse schema validate schema.imps.yaml
  ```
* **Schema-Enforced Snapshot Build**: Enforce schema constraints when building `.imps` snapshots from CSV or Parquet files:
  ```bash
  impulse compile --schema schema.imps.yaml dataset/ -o output.imps
  ```
