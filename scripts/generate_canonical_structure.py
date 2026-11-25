#!/usr/bin/env python3
"""
INFYNEX Canonical 3D Asset Generator
Enforces the Single-Asset Rule:
Generates one canonical metric mesh (concrete_structure.obj and concrete_structure.glb)
Origin (0,0,0) is at foundation base center with Z-up metric scale.
Shared identically by Gazebo Harmonic, AI Engine 3D Ray-Caster (Trimesh), and Dashboard Three.js.
"""

import os
import trimesh
import numpy as np

def build_box(extents, center, name="box"):
    """Creates an axis-aligned box with given extents [dx, dy, dz] and center [x, y, z]."""
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(center)
    mesh.metadata['name'] = name
    return mesh

def create_canonical_structure():
    parts = []

    # 1. Reinforced Concrete Foundation Pad (Z: 0.0 to 0.6m)
    # 14.0m x 9.0m x 0.6m centered at (0, 0, 0.3)
    parts.append(build_box([14.0, 9.0, 0.6], [0.0, 0.0, 0.3], name="foundation_pad"))

    # 2. North Structural Column / Pier (Z: 0.6 to 5.6m, Height: 5.0m)
    # 1.4m x 1.4m x 5.0m centered at (0.0, 2.5, 3.1)
    parts.append(build_box([1.4, 1.4, 5.0], [0.0, 2.5, 3.1], name="north_pillar"))

    # 3. South Structural Column / Pier (Z: 0.6 to 5.6m, Height: 5.0m)
    # 1.4m x 1.4m x 5.0m centered at (0.0, -2.5, 3.1)
    parts.append(build_box([1.4, 1.4, 5.0], [0.0, -2.5, 3.1], name="south_pillar"))

    # 4. Central Shear Web Wall connecting pillars (Z: 0.6 to 5.1m, Height: 4.5m)
    # 0.8m x 3.6m x 4.5m centered at (0.0, 0.0, 2.85)
    parts.append(build_box([0.8, 3.6, 4.5], [0.0, 0.0, 2.85], name="shear_web_wall"))

    # 5. East Abutment / Flank Wall (Z: 0.6 to 4.2m)
    # 2.8m x 1.2m x 3.6m centered at (3.2, 0.0, 2.4)
    parts.append(build_box([2.8, 1.2, 3.6], [3.2, 0.0, 2.4], name="east_flank_wall"))

    # 6. West Pier / Support Buttress (Z: 0.6 to 4.2m)
    # 2.8m x 1.2m x 3.6m centered at (-3.2, 0.0, 2.4)
    parts.append(build_box([2.8, 1.2, 3.6], [-3.2, 0.0, 2.4], name="west_flank_wall"))

    # 7. Overhead Cantilever Bridge Deck Superstructure (Z: 5.6 to 6.4m, Height: 0.8m)
    # 16.0m x 7.0m x 0.8m centered at (0.0, 0.0, 6.0)
    parts.append(build_box([16.0, 7.0, 0.8], [0.0, 0.0, 6.0], name="overhead_deck"))

    # 8. North Parapet Safety Railing (Z: 6.4 to 7.4m)
    parts.append(build_box([16.0, 0.25, 1.0], [0.0, 3.375, 6.9], name="north_parapet"))

    # 9. South Parapet Safety Railing (Z: 6.4 to 7.4m)
    parts.append(build_box([16.0, 0.25, 1.0], [0.0, -3.375, 6.9], name="south_parapet"))

    # 10. Takeoff Helipad Platform Pad (Z: 0.0 to 0.08m)
    # Cylindrical helipad disk radius 1.8m centered at (0.0, -6.5, 0.04)
    helipad = trimesh.creation.cylinder(radius=1.8, height=0.08)
    helipad.apply_translation([0.0, -6.5, 0.04])
    helipad.metadata['name'] = "takeoff_helipad"
    parts.append(helipad)

    # Combine all manifold sub-meshes into one unified structure
    combined = trimesh.util.concatenate(parts)
    # Color concrete grey with PBR feel
    combined.visual.face_colors = [165, 168, 172, 255]

    return combined

if __name__ == "__main__":
    structure = create_canonical_structure()

    out_dir_gazebo = "/app/simulation/gazebo/models/concrete_structure"
    out_dir_dash = "/app/dashboard/public/models"
    out_dir_infra = "/app/simulation/infrastructure/assets"
    os.makedirs(out_dir_gazebo, exist_ok=True)
    os.makedirs(out_dir_dash, exist_ok=True)
    os.makedirs(out_dir_infra, exist_ok=True)

    obj_path = os.path.join(out_dir_gazebo, "concrete_structure.obj")
    glb_path_gz = os.path.join(out_dir_gazebo, "concrete_structure.glb")
    glb_path_dash = os.path.join(out_dir_dash, "concrete_structure.glb")
    glb_path_infra = os.path.join(out_dir_infra, "concrete_structure.glb")
    obj_path_infra = os.path.join(out_dir_infra, "concrete_structure.obj")

    structure.export(obj_path)
    structure.export(glb_path_gz)
    structure.export(glb_path_dash)
    structure.export(glb_path_infra)
    structure.export(obj_path_infra)

    print(f"[Canonical Mesh Generator] Successfully exported:")
    print(f"  -> {obj_path} ({len(structure.vertices)} vertices, {len(structure.faces)} faces)")
    print(f"  -> {glb_path_gz}")
    print(f"  -> {glb_path_dash}")
    print(f"  -> Bounds: min={structure.bounds[0]}, max={structure.bounds[1]}")
