#!/usr/bin/env python3
"""
Generate an enhanced, highly detailed 3D GLB model for the Tutor Guardian Protective Shield.
Includes:
- Metallic gold multi-beveled outer rim & back
- Deep emerald jade faceted shield body
- Embossed 3D golden Islamic Arch & Open Book emblem in the center
- glTF 2.0 compliant binary GLB
"""
import struct
import json
import math
from pathlib import Path

def generate_shield_glb(out_path: Path):
    # Contour points for the outer shield (8 points)
    outer_points = [
        (0.0, 1.25, 0.05),     # 0: top peak
        (-0.55, 1.15, 0.04),   # 1: top shoulder left
        (-0.80, 0.40, 0.04),   # 2: mid left
        (-0.65, -0.45, 0.04),  # 3: lower left
        (0.0, -1.35, 0.06),    # 4: bottom point
        (0.65, -0.45, 0.04),   # 5: lower right
        (0.80, 0.40, 0.04),    # 6: mid right
        (0.55, 1.15, 0.04),    # 7: top shoulder right
    ]
    
    # Inner gold border contour (bevel)
    scale_in = 0.82
    inner_points = [
        (p[0] * scale_in, p[1] * scale_in, 0.10) for p in outer_points
    ]
    
    # Back contour
    back_points = [
        (p[0] * 0.98, p[1] * 0.98, -0.08) for p in outer_points
    ]

    center_apex = (0.0, 0.05, 0.18)
    center_back = (0.0, 0.05, -0.08)

    pos_gold = []
    norm_gold = []
    idx_gold = []

    def calc_normal(p1, p2, p3):
        v1 = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v2 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        nx = v1[1] * v2[2] - v1[2] * v2[1]
        ny = v1[2] * v2[0] - v1[0] * v2[2]
        nz = v1[0] * v2[1] - v1[1] * v2[0]
        l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        return (nx / l, ny / l, nz / l)

    def add_quad_gold(p1, p2, p3, p4, normal=None):
        base = len(pos_gold)
        n = normal or calc_normal(p1, p2, p3)
        pos_gold.extend([p1, p2, p3, p4])
        norm_gold.extend([n, n, n, n])
        idx_gold.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def add_tri_gold(p1, p2, p3, normal=None):
        base = len(pos_gold)
        n = normal or calc_normal(p1, p2, p3)
        pos_gold.extend([p1, p2, p3])
        norm_gold.extend([n, n, n])
        idx_gold.extend([base, base + 1, base + 2])

    N = len(outer_points)
    # 1. Front Gold Rim
    for i in range(N):
        nxt = (i + 1) % N
        add_quad_gold(outer_points[i], outer_points[nxt], inner_points[nxt], inner_points[i])

    # 2. Outer Side Walls (Thickness)
    for i in range(N):
        nxt = (i + 1) % N
        add_quad_gold(outer_points[i], back_points[i], back_points[nxt], outer_points[nxt])

    # 3. Back Fan
    base_bk = len(pos_gold)
    pos_gold.append(center_back)
    norm_gold.append((0.0, 0.0, -1.0))
    for i in range(N):
        pos_gold.append(back_points[i])
        norm_gold.append((0.0, 0.0, -1.0))
    for i in range(N):
        nxt = (i + 1) % N
        idx_gold.extend([base_bk, base_bk + 1 + i, base_bk + 1 + nxt])

    # 4. Central Golden Emblem: An Open Book / Islamic Arch Relief
    # Left page & Right page floating atop the emerald dome
    z_emblem = 0.22
    z_spine = 0.20
    # Left page
    lp_top_in = (-0.02, 0.35, z_spine)
    lp_top_out = (-0.38, 0.38, z_emblem)
    lp_mid_out = (-0.42, 0.05, z_emblem)
    lp_bot_out = (-0.35, -0.28, z_emblem)
    lp_bot_in = (-0.02, -0.25, z_spine)
    # Right page
    rp_top_in = (0.02, 0.35, z_spine)
    rp_top_out = (0.38, 0.38, z_emblem)
    rp_mid_out = (0.42, 0.05, z_emblem)
    rp_bot_out = (0.35, -0.28, z_emblem)
    rp_bot_in = (0.02, -0.25, z_spine)
    center_crest = (0.0, 0.55, 0.24)

    # Quads for left page
    add_quad_gold(lp_top_in, lp_top_out, lp_mid_out, ( -0.02, 0.05, z_spine))
    add_quad_gold(( -0.02, 0.05, z_spine), lp_mid_out, lp_bot_out, lp_bot_in)
    # Quads for right page
    add_quad_gold(rp_top_in, (0.02, 0.05, z_spine), rp_mid_out, rp_top_out)
    add_quad_gold((0.02, 0.05, z_spine), rp_bot_in, rp_bot_out, rp_mid_out)
    # Top arch crown peak (crest)
    add_tri_gold(lp_top_in, center_crest, rp_top_in)
    add_tri_gold(lp_top_out, center_crest, lp_top_in)
    add_tri_gold(rp_top_in, center_crest, rp_top_out)

    # --- Primitive 1: Emerald Jade Body ---
    pos_emerald = []
    norm_emerald = []
    idx_emerald = []

    def add_tri_em(p1, p2, p3):
        base = len(pos_emerald)
        n = calc_normal(p1, p2, p3)
        pos_emerald.extend([p1, p2, p3])
        norm_emerald.extend([n, n, n])
        idx_emerald.extend([base, base + 1, base + 2])

    base_em = len(pos_emerald)
    pos_emerald.append(center_apex)
    norm_emerald.append((0.0, 0.0, 1.0))
    for i in range(N):
        pos_emerald.append(inner_points[i])
        n = calc_normal(center_apex, inner_points[i], inner_points[(i + 1) % N])
        norm_emerald.append(n)
    for i in range(N):
        nxt = (i + 1) % N
        idx_emerald.extend([base_em, base_em + 1 + i, base_em + 1 + nxt])

    # Convert to binary
    bin_gold_pos = b''.join(struct.pack('<fff', *p) for p in pos_gold)
    bin_gold_norm = b''.join(struct.pack('<fff', *n) for n in norm_gold)
    bin_gold_idx = b''.join(struct.pack('<H', i) for i in idx_gold)
    if len(bin_gold_idx) % 4 != 0:
        bin_gold_idx += b'\x00' * (4 - (len(bin_gold_idx) % 4))

    bin_em_pos = b''.join(struct.pack('<fff', *p) for p in pos_emerald)
    bin_em_norm = b''.join(struct.pack('<fff', *n) for n in norm_emerald)
    bin_em_idx = b''.join(struct.pack('<H', i) for i in idx_emerald)
    if len(bin_em_idx) % 4 != 0:
        bin_em_idx += b'\x00' * (4 - (len(bin_em_idx) % 4))

    def min_max(positions):
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]

    g_min, g_max = min_max(pos_gold)
    e_min, e_max = min_max(pos_emerald)

    offset = 0
    off_gp, len_gp = offset, len(bin_gold_pos); offset += len_gp
    off_gn, len_gn = offset, len(bin_gold_norm); offset += len_gn
    off_gi, len_gi = offset, len(bin_gold_idx); offset += len_gi
    off_ep, len_ep = offset, len(bin_em_pos); offset += len_ep
    off_en, len_en = offset, len(bin_em_norm); offset += len_en
    off_ei, len_ei = offset, len(bin_em_idx); offset += len_ei

    total_bin = (
        bin_gold_pos + bin_gold_norm + bin_gold_idx +
        bin_em_pos + bin_em_norm + bin_em_idx
    )

    gltf = {
        "asset": {"version": "2.0", "generator": "Tutor Guardian 3D Crest Studio"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "GuardianShieldEmblem", "mesh": 0}],
        "materials": [
            {
                "name": "ImperialGold",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.96, 0.82, 0.38, 1.0],
                    "metallicFactor": 0.95,
                    "roughnessFactor": 0.18
                }
            },
            {
                "name": "EmeraldJade",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.03, 0.28, 0.24, 1.0],
                    "metallicFactor": 0.25,
                    "roughnessFactor": 0.22
                },
                "emissiveFactor": [0.03, 0.15, 0.12]
            }
        ],
        "meshes": [
            {
                "name": "ShieldMesh",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1},
                        "indices": 2,
                        "material": 0
                    },
                    {
                        "attributes": {"POSITION": 3, "NORMAL": 4},
                        "indices": 5,
                        "material": 1
                    }
                ]
            }
        ],
        "accessors": [
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126, "count": len(pos_gold), "type": "VEC3", "min": g_min, "max": g_max},
            {"bufferView": 1, "byteOffset": 0, "componentType": 5126, "count": len(norm_gold), "type": "VEC3"},
            {"bufferView": 2, "byteOffset": 0, "componentType": 5123, "count": len(idx_gold), "type": "SCALAR"},
            {"bufferView": 3, "byteOffset": 0, "componentType": 5126, "count": len(pos_emerald), "type": "VEC3", "min": e_min, "max": e_max},
            {"bufferView": 4, "byteOffset": 0, "componentType": 5126, "count": len(norm_emerald), "type": "VEC3"},
            {"bufferView": 5, "byteOffset": 0, "componentType": 5123, "count": len(idx_emerald), "type": "SCALAR"}
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": off_gp, "byteLength": len_gp, "target": 34962},
            {"buffer": 0, "byteOffset": off_gn, "byteLength": len_gn, "target": 34962},
            {"buffer": 0, "byteOffset": off_gi, "byteLength": len_gi, "target": 34963},
            {"buffer": 0, "byteOffset": off_ep, "byteLength": len_ep, "target": 34962},
            {"buffer": 0, "byteOffset": off_en, "byteLength": len_en, "target": 34962},
            {"buffer": 0, "byteOffset": off_ei, "byteLength": len_ei, "target": 34963}
        ],
        "buffers": [{"byteLength": len(total_bin)}]
    }

    json_str = json.dumps(gltf, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    if len(json_bytes) % 4 != 0:
        json_bytes += b' ' * (4 - (len(json_bytes) % 4))
    if len(total_bin) % 4 != 0:
        total_bin += b'\x00' * (4 - (len(total_bin) % 4))

    total_length = 12 + 8 + len(json_bytes) + 8 + len(total_bin)
    header = struct.pack('<4sII', b'glTF', 2, total_length)
    chunk0_header = struct.pack('<I4s', len(json_bytes), b'JSON')
    chunk1_header = struct.pack('<I4s', len(total_bin), b'BIN\x00')

    with open(out_path, 'wb') as f:
        f.write(header)
        f.write(chunk0_header)
        f.write(json_bytes)
        f.write(chunk1_header)
        f.write(total_bin)

    print(f"Enhanced 3D shield created at: {out_path} ({out_path.stat().st_size} bytes)")

if __name__ == "__main__":
    out_file = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "3d" / "guardian_shield.glb"
    generate_shield_glb(out_file)
