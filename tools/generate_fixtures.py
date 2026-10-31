#!/usr/bin/env python3
"""
Canonical Topology Fixture Generator for Impulse Graph Engine.
Uses official impulse-graph tooling (impulse-graph generate and impulse-graph build).
Seed: 42 (Rule 3.7 & Rule 3.17).
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

def find_impulse_cli():
    # Priority: explicit env var, then tooling debug/release binary, then PATH
    env_cli = os.environ.get("IMPULSE_CLI")
    if env_cli and os.path.isfile(env_cli) and os.access(env_cli, os.X_OK):
        return Path(env_cli).resolve()

    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "impulse-graph-tooling" / "target" / "debug" / "impulse-graph",
        repo_root / "impulse-graph-tooling" / "target" / "release" / "impulse-graph",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c.resolve()

    which_cli = shutil.which("impulse-graph")
    if which_cli:
        return Path(which_cli).resolve()

    raise RuntimeError(
        "Could not find 'impulse-graph' binary in tooling target directories or PATH. "
        "Please build impulse-graph-tooling (cargo build) or set IMPULSE_CLI."
    )

def main():
    cli = find_impulse_cli()
    print(f"Using official Impulse CLI: {cli}")

    spec_dir = Path(__file__).resolve().parent.parent
    fixtures_dir = spec_dir / "test-fixtures" / "snapshots"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {fixtures_dir}")

    # 1. g0_empty.imps (0 nodes, 0 edges)
    g0_out = fixtures_dir / "g0_empty.imps"
    print(f"Generating {g0_out.name}...")
    subprocess.run([
        str(cli), "generate",
        "--profile", "erdos-renyi",
        "--nodes", "0",
        "--edges", "0",
        "--seed", "42",
        "-o", str(g0_out)
    ], check=True, stdout=subprocess.DEVNULL)

    # 2. g1_self_loop.imps (1 node, 1 directed self-loop)
    g1_out = fixtures_dir / "g1_self_loop.imps"
    print(f"Generating {g1_out.name}...")
    subprocess.run([
        str(cli), "generate",
        "--profile", "erdos-renyi",
        "--nodes", "1",
        "--edges", "1",
        "--allow-self-loops",
        "--include-csc",
        "--seed", "42",
        "-o", str(g1_out)
    ], check=True, stdout=subprocess.DEVNULL)

    # Temporary build staging directory for manifests
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 3. g2_diamond_dag.imps (4 nodes: 0->1, 0->2, 1->3, 2->3)
        g2_dir = tmp_dir / "g2"
        g2_dir.mkdir()
        (g2_dir / "edges.tsv").write_text("0\t1\n0\t2\n1\t3\n2\t3\n")
        g2_manifest = {
            "version": "2.4.0",
            "global_features": ["4kb_page_aligned"],
            "domains": [{"id": 0, "name": "Node", "key_type": "string"}],
            "relations": [{
                "name": "CONNECTS",
                "src_domain": 0,
                "tgt_domain": 0,
                "encoding": "raw_uint32",
                "include_csc": True,
                "file": "edges.tsv"
            }]
        }
        (g2_dir / "manifest.json").write_text(json.dumps(g2_manifest))
        g2_out = fixtures_dir / "g2_diamond_dag.imps"
        print(f"Compiling {g2_out.name}...")
        subprocess.run([
            str(cli), "build",
            "-m", str(g2_dir / "manifest.json"),
            "-o", str(g2_out)
        ], check=True, stdout=subprocess.DEVNULL)

        # 4. g3_directed_cycle_65.imps (65 nodes: 0->1->2...->64->0)
        g3_dir = tmp_dir / "g3"
        g3_dir.mkdir()
        cycle_edges = "\n".join(f"{i}\t{(i + 1) % 65}" for i in range(65)) + "\n"
        (g3_dir / "edges.tsv").write_text(cycle_edges)
        g3_manifest = {
            "version": "2.4.0",
            "global_features": ["4kb_page_aligned"],
            "domains": [{"id": 0, "name": "Node", "key_type": "string"}],
            "relations": [{
                "name": "NEXT",
                "src_domain": 0,
                "tgt_domain": 0,
                "encoding": "raw_uint32",
                "include_csc": True,
                "file": "edges.tsv"
            }]
        }
        (g3_dir / "manifest.json").write_text(json.dumps(g3_manifest))
        g3_out = fixtures_dir / "g3_directed_cycle_65.imps"
        print(f"Compiling {g3_out.name}...")
        subprocess.run([
            str(cli), "build",
            "-m", str(g3_dir / "manifest.json"),
            "-o", str(g3_out)
        ], check=True, stdout=subprocess.DEVNULL)

        # 5. g4_disconnected_stars.imps (3 disjoint star components: center 0, 10, 20)
        g4_dir = tmp_dir / "g4"
        g4_dir.mkdir()
        star_edges = []
        for leaf in range(1, 6):
            star_edges.append(f"0\t{leaf}")
        for leaf in range(11, 16):
            star_edges.append(f"10\t{leaf}")
        for leaf in range(21, 25):
            star_edges.append(f"20\t{leaf}")
        (g4_dir / "edges.tsv").write_text("\n".join(star_edges) + "\n")
        g4_manifest = {
            "version": "2.4.0",
            "global_features": ["4kb_page_aligned"],
            "domains": [{"id": 0, "name": "Node", "key_type": "string"}],
            "relations": [{
                "name": "LINK",
                "src_domain": 0,
                "tgt_domain": 0,
                "encoding": "raw_uint32",
                "include_csc": True,
                "file": "edges.tsv"
            }]
        }
        (g4_dir / "manifest.json").write_text(json.dumps(g4_manifest))
        g4_out = fixtures_dir / "g4_disconnected_stars.imps"
        print(f"Compiling {g4_out.name}...")
        subprocess.run([
            str(cli), "build",
            "-m", str(g4_dir / "manifest.json"),
            "-o", str(g4_out)
        ], check=True, stdout=subprocess.DEVNULL)

        # 6. g5_multi_domain.imps (User -> Device -> IPAddress)
        g5_dir = tmp_dir / "g5"
        g5_dir.mkdir()
        (g5_dir / "uses.tsv").write_text("u0\td0\nu1\td1\nu2\td2\n")
        (g5_dir / "connects.tsv").write_text("d0\tip0\nd1\tip1\nd2\tip2\n")
        g5_manifest = {
            "version": "2.4.0",
            "global_features": ["4kb_page_aligned"],
            "domains": [
                {"id": 0, "name": "User", "key_type": "string"},
                {"id": 1, "name": "Device", "key_type": "string"},
                {"id": 2, "name": "IPAddress", "key_type": "string"}
            ],
            "relations": [
                {
                    "name": "USES",
                    "src_domain": 0,
                    "tgt_domain": 1,
                    "encoding": "raw_uint32",
                    "include_csc": True,
                    "file": "uses.tsv"
                },
                {
                    "name": "CONNECTS_TO",
                    "src_domain": 1,
                    "tgt_domain": 2,
                    "encoding": "raw_uint32",
                    "include_csc": True,
                    "file": "connects.tsv"
                }
            ]
        }
        (g5_dir / "manifest.json").write_text(json.dumps(g5_manifest))
        g5_out = fixtures_dir / "g5_multi_domain.imps"
        print(f"Compiling {g5_out.name}...")
        subprocess.run([
            str(cli), "build",
            "-m", str(g5_dir / "manifest.json"),
            "-o", str(g5_out)
        ], check=True, stdout=subprocess.DEVNULL)

        # 8. g7_bipartite_rebac.imps (User -> Document: viewer, editor)
        g7_dir = tmp_dir / "g7"
        g7_dir.mkdir()
        (g7_dir / "viewer.tsv").write_text("alice\tdoc1\nalice\tdoc2\nbob\tdoc2\n")
        (g7_dir / "editor.tsv").write_text("alice\tdoc1\ncharlie\tdoc3\n")
        g7_manifest = {
            "version": "2.4.0",
            "global_features": ["4kb_page_aligned"],
            "domains": [
                {"id": 0, "name": "User", "key_type": "string"},
                {"id": 1, "name": "Document", "key_type": "string"}
            ],
            "relations": [
                {
                    "name": "viewer",
                    "src_domain": 0,
                    "tgt_domain": 1,
                    "encoding": "raw_uint32",
                    "include_csc": True,
                    "file": "viewer.tsv"
                },
                {
                    "name": "editor",
                    "src_domain": 0,
                    "tgt_domain": 1,
                    "encoding": "raw_uint32",
                    "include_csc": True,
                    "file": "editor.tsv"
                }
            ]
        }
        (g7_dir / "manifest.json").write_text(json.dumps(g7_manifest))
        g7_out = fixtures_dir / "g7_bipartite_rebac.imps"
        print(f"Compiling {g7_out.name}...")
        subprocess.run([
            str(cli), "build",
            "-m", str(g7_dir / "manifest.json"),
            "-o", str(g7_out)
        ], check=True, stdout=subprocess.DEVNULL)

    # 7. g6_weighted_mesh.imps (16 nodes, 4x4 grid with float and double attributes)
    g6_out = fixtures_dir / "g6_weighted_mesh.imps"
    print(f"Generating {g6_out.name}...")
    subprocess.run([
        str(cli), "generate",
        "--profile", "grid",
        "--dim-x", "4",
        "--dim-y", "4",
        "--attributes", "weight:f32,cost:f64",
        "--include-csc",
        "--seed", "42",
        "-o", str(g6_out)
    ], check=True, stdout=subprocess.DEVNULL)

    # Verify all 8 files exist and inspect cleanly
    print("\nValidating all 8 canonical fixture snapshots:")
    for f in sorted(fixtures_dir.glob("g*.imps")):
        res = subprocess.run([str(cli), "inspect", str(f)], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  [OK] {f.name} ({f.stat().st_size} bytes)")
        else:
            print(f"  [FAIL] {f.name} inspection failed: {res.stderr}")
            sys.exit(1)

    print("\nAll 8 canonical snapshot fixtures generated successfully!")

if __name__ == "__main__":
    main()
