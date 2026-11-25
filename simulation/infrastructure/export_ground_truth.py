#!/usr/bin/env python3
"""
INFYNEX Programmatic Ground Truth Parser & Exporter
Parses bridge_inspection.sdf directly to extract exact 3D defect coordinates,
surface IDs, physical dimensions (mm), and severity classifications.
Guarantees deterministic ground truth for AI evaluation and ray-casting verification.
"""

import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

DEFECT_METADATA = {
    "vertical_crack": {
        "category": "crack_vertical",
        "default_severity": "moderate",
        "dimensions_mm": {"width": 0.42, "length": 850.0, "depth": 18.0},
        "description": "Tension vertical crack in concrete facade"
    },
    "horizontal_crack": {
        "category": "crack_horizontal",
        "default_severity": "critical",
        "dimensions_mm": {"width": 0.65, "length": 950.0, "depth": 25.0},
        "description": "Seismic shear horizontal fracture with efflorescence"
    },
    "diagonal_crack": {
        "category": "crack_diagonal",
        "default_severity": "moderate",
        "dimensions_mm": {"width": 0.38, "length": 800.0, "depth": 15.0},
        "description": "45-degree diagonal shear stress crack"
    },
    "spalling": {
        "category": "spalling",
        "default_severity": "critical",
        "dimensions_mm": {"width": 450.0, "length": 700.0, "depth": 40.0},
        "description": "Concrete delamination spall with exposed rebar"
    },
    "discoloration": {
        "category": "discoloration",
        "default_severity": "minor",
        "dimensions_mm": {"width": 650.0, "length": 900.0, "depth": 2.0},
        "description": "Surface moisture leaching and efflorescence stain"
    }
}

def determine_surface(x: float, y: float, z: float, yaw: float) -> tuple[str, list[float]]:
    """Determines the asset face and outward normal vector based on 3D coordinates."""
    if z >= 5.2:
        return "overhead_cantilever_deck", [0.0, 0.0, -1.0]
    if y >= 2.0:
        return "north_pier_front_face", [0.0, 1.0, 0.0]
    elif y <= -2.0:
        return "south_pier_rear_face", [0.0, -1.0, 0.0]
    elif x >= 3.0:
        return "east_flank_wing_wall", [1.0, 0.0, 0.0]
    elif x <= -3.0:
        return "west_flank_support_buttress", [-1.0, 0.0, 0.0]
    else:
        return "central_shear_web_wall", [0.0, 1.0, 0.0]

def export_ground_truth(sdf_path: str, out_json_path: str):
    if not os.path.exists(sdf_path):
        print(f"Error: SDF world file not found at {sdf_path}")
        sys.exit(1)

    print(f"[Ground Truth Parser] Parsing SDF world: {sdf_path}")
    tree = ET.parse(sdf_path)
    root = tree.getroot()

    world = root.find("world")
    if world is None:
        print("Error: No <world> element found in SDF.")
        sys.exit(1)

    ground_truth = {
        "asset_id": "INFRA_BRIDGE_PIER_001",
        "asset_name": "Concrete Bridge Superstructure Asset A",
        "generated_from_sdf": os.path.abspath(sdf_path),
        "total_defects": 0,
        "defects": []
    }

    # Inspect all <include> elements for damage_decals
    for inc in world.findall("include"):
        name_elem = inc.find("name")
        uri_elem = inc.find("uri")
        pose_elem = inc.find("pose")

        if name_elem is None or uri_elem is None or pose_elem is None:
            continue

        name = name_elem.text.strip()
        uri = uri_elem.text.strip()
        pose_str = pose_elem.text.strip()

        if "damage_decals" not in uri:
            continue

        model_type = uri.split("/")[-1]
        pose_parts = [float(p) for p in pose_str.split()]
        x, y, z = pose_parts[0], pose_parts[1], pose_parts[2]
        roll = pose_parts[3] if len(pose_parts) > 3 else 0.0
        pitch = pose_parts[4] if len(pose_parts) > 4 else 0.0
        yaw = pose_parts[5] if len(pose_parts) > 5 else 0.0

        surface_name, normal_vec = determine_surface(x, y, z, yaw)
        meta = DEFECT_METADATA.get(model_type, {
            "category": model_type,
            "default_severity": "moderate",
            "dimensions_mm": {"width": 10.0, "length": 500.0, "depth": 10.0},
            "description": "Structural defect"
        })

        defect_record = {
            "damage_id": name,
            "type": meta["category"],
            "model_type": model_type,
            "severity": meta["default_severity"],
            "surface": surface_name,
            "position": {
                "x": round(x, 3),
                "y": round(y, 3),
                "z": round(z, 3)
            },
            "orientation": {
                "roll": round(roll, 4),
                "pitch": round(pitch, 4),
                "yaw": round(yaw, 4)
            },
            "surface_normal": normal_vec,
            "bounding_dimensions_mm": meta["dimensions_mm"],
            "description": meta["description"]
        }

        ground_truth["defects"].append(defect_record)

    ground_truth["total_defects"] = len(ground_truth["defects"])

    os.makedirs(os.path.dirname(out_json_path), exist_ok=True)
    with open(out_json_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"[Ground Truth Parser] Deterministically extracted {ground_truth['total_defects']} defects.")
    print(f"[Ground Truth Parser] Saved canonical ground truth to: {out_json_path}")
    return ground_truth

if __name__ == "__main__":
    base_dir = "/home/vcmr/Downloads/INFYNEX"
    sdf_file = os.path.join(base_dir, "simulation/gazebo/worlds/bridge_inspection.sdf")
    out_file = os.path.join(base_dir, "simulation/infrastructure/ground_truth.json")
    export_ground_truth(sdf_file, out_file)
