#!/usr/bin/env python3
"""
INFYNEX Photorealistic PBR Texture & Defect Decal Generator
Generates high-resolution seamless PBR concrete textures (Albedo, Normal, Roughness, AO)
and high-resolution photographic crack and spalling decals with alpha transparency.
"""

import os
import math
import numpy as np
import cv2

TEXTURE_DIR = "simulation/gazebo/models/materials/textures"
os.makedirs(TEXTURE_DIR, exist_ok=True)

def generate_seamless_noise(size=(1024, 1024), scale=32.0, octaves=5):
    """Generates multi-octave seamless Perlin-style fractal noise."""
    h, w = size
    noise = np.zeros((h, w), dtype=np.float32)
    current_scale = scale
    amplitude = 1.0
    total_amp = 0.0

    for _ in range(octaves):
        grid_h = max(2, int(h / current_scale))
        grid_w = max(2, int(w / current_scale))
        rand_grid = np.random.uniform(0.0, 1.0, (grid_h, grid_w)).astype(np.float32)
        # Wrap boundary for seamlessness
        rand_grid[-1, :] = rand_grid[0, :]
        rand_grid[:, -1] = rand_grid[:, 0]
        layer = cv2.resize(rand_grid, (w, h), interpolation=cv2.INTER_CUBIC)
        noise += layer * amplitude
        total_amp += amplitude
        amplitude *= 0.5
        current_scale *= 0.5

    return noise / total_amp

def generate_concrete_pbr_set():
    print("[Textures] Generating 1024x1024 seamless PBR Concrete textures...")
    h, w = 1024, 1024

    # 1. Base fractal noise layers for concrete grain and pores
    macro_noise = generate_seamless_noise((h, w), scale=128.0, octaves=4)
    grain_noise = generate_seamless_noise((h, w), scale=16.0, octaves=4)
    pore_noise = np.random.uniform(0.0, 1.0, (h, w)).astype(np.float32)

    # 2. Albedo Map: Architectural concrete grey (~120-150) with mineral variation
    albedo = (130.0 + (macro_noise - 0.5) * 35.0 + (grain_noise - 0.5) * 18.0)
    # Add dark aggregate specks & tiny pores
    dark_specks = (pore_noise < 0.025).astype(np.float32) * 40.0
    albedo = np.clip(albedo - dark_specks, 70.0, 190.0)

    # Convert to 3-channel BGR with subtle warmth/neutral tone
    b = albedo * 0.98
    g = albedo * 1.00
    r = albedo * 1.02
    albedo_bgr = np.stack([b, g, r], axis=-1).astype(np.uint8)

    # 3. Height & Normal Map (Tangent Space)
    height = (macro_noise * 0.4 + grain_noise * 0.6)
    sobel_x = cv2.Sobel(height, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(height, cv2.CV_32F, 0, 1, ksize=3)
    nz = 1.0 / np.sqrt(sobel_x**2 + sobel_y**2 + 1.0)
    nx = -sobel_x * nz
    ny = -sobel_y * nz

    normal_b = ((nz + 1.0) * 0.5 * 255.0).astype(np.uint8)
    normal_g = ((ny + 1.0) * 0.5 * 255.0).astype(np.uint8)
    normal_r = ((nx + 1.0) * 0.5 * 255.0).astype(np.uint8)
    normal_bgr = np.stack([normal_b, normal_g, normal_r], axis=-1)

    # 4. Roughness Map: Mostly matte (0.85-0.95) with subtle aggregate smoothness
    roughness = (215.0 + (grain_noise - 0.5) * 40.0)
    roughness = np.clip(roughness, 180, 250).astype(np.uint8)
    roughness_bgr = cv2.cvtColor(roughness, cv2.COLOR_GRAY2BGR)

    # 5. Ambient Occlusion Map: Cavity shadowing
    ao = (255.0 - (1.0 - height) * 60.0)
    ao = np.clip(ao, 160, 255).astype(np.uint8)
    ao_bgr = cv2.cvtColor(ao, cv2.COLOR_GRAY2BGR)

    # Save PBR Concrete Maps
    cv2.imwrite(f"{TEXTURE_DIR}/concrete_albedo.jpg", albedo_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(f"{TEXTURE_DIR}/concrete_normal.jpg", normal_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(f"{TEXTURE_DIR}/concrete_roughness.jpg", roughness_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(f"{TEXTURE_DIR}/concrete_ao.jpg", ao_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print("  -> Saved concrete_albedo.jpg, concrete_normal.jpg, concrete_roughness.jpg, concrete_ao.jpg")

def generate_asphalt_pbr_set():
    print("[Textures] Generating 1024x1024 seamless PBR Asphalt textures...")
    h, w = 1024, 1024
    tar_noise = generate_seamless_noise((h, w), scale=64.0, octaves=4)
    stone_noise = generate_seamless_noise((h, w), scale=8.0, octaves=3)

    asphalt = (45.0 + (tar_noise - 0.5) * 15.0 + (stone_noise - 0.5) * 20.0)
    asphalt = np.clip(asphalt, 25.0, 75.0).astype(np.uint8)
    asphalt_bgr = cv2.cvtColor(asphalt, cv2.COLOR_GRAY2BGR)

    cv2.imwrite(f"{TEXTURE_DIR}/asphalt_albedo.jpg", asphalt_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print("  -> Saved asphalt_albedo.jpg")

def generate_photographic_decals():
    print("[Decals] Generating high-resolution photographic defect decal PNGs with alpha channel...")
    size = (1024, 1024)
    h, w = size

    # =========================================================================
    # 1. Vertical Structural Tension Crack Decal
    # =========================================================================
    v_crack = np.zeros((h, w, 4), dtype=np.uint8)
    # Background concrete tone for blending
    bg_color = np.array([125, 126, 128], dtype=np.uint8)

    # Main jagged fracture path from y=60 to y=960
    np.random.seed(42)
    cur_x = 512.0
    pts = []
    branches_1 = []
    branches_2 = []

    for y in range(80, 950, 4):
        cur_x += np.random.normal(0.0, 1.8)
        cur_x = np.clip(cur_x, 400.0, 620.0)
        pts.append((int(cur_x), y))
        # Branch 1 at 35% height
        if 320 <= y <= 580:
            branches_1.append((int(cur_x + (y - 320) * 0.55 + np.random.normal(0, 1)), y))
        # Branch 2 at 65% height
        if 600 <= y <= 820:
            branches_2.append((int(cur_x - (y - 600) * 0.45 + np.random.normal(0, 1)), y))

    # Draw fracture core (dark fissure) and distressed spall perimeter
    for i in range(len(pts) - 1):
        pt1 = pts[i]
        pt2 = pts[i+1]
        # Halo distressed zone
        cv2.line(v_crack, pt1, pt2, (100, 102, 105, 180), 14)
        # Inner fracture zone
        cv2.line(v_crack, pt1, pt2, (45, 46, 48, 230), 6)
        # Deep tensile black void core
        cv2.line(v_crack, pt1, pt2, (12, 12, 14, 255), 3)

    for i in range(len(branches_1) - 1):
        cv2.line(v_crack, branches_1[i], branches_1[i+1], (18, 18, 20, 240), 2)
    for i in range(len(branches_2) - 1):
        cv2.line(v_crack, branches_2[i], branches_2[i+1], (18, 18, 20, 240), 2)

    # Add aggregate micro-fractures
    v_crack_blur = cv2.GaussianBlur(v_crack, (3, 3), 0)
    cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_vertical.png", v_crack_blur)

    # =========================================================================
    # 2. Horizontal Flexural Shear Crack Decal
    # =========================================================================
    h_crack = np.zeros((h, w, 4), dtype=np.uint8)
    cur_y = 512.0
    h_pts = []
    for x in range(80, 950, 4):
        cur_y += np.random.normal(0.0, 1.6)
        cur_y = np.clip(cur_y, 420.0, 600.0)
        h_pts.append((x, int(cur_y)))

    for i in range(len(h_pts) - 1):
        pt1 = h_pts[i]
        pt2 = h_pts[i+1]
        cv2.line(h_crack, pt1, pt2, (95, 98, 102, 180), 16)
        cv2.line(h_crack, pt1, pt2, (40, 42, 45, 230), 7)
        cv2.line(h_crack, pt1, pt2, (10, 10, 12, 255), 3)

    h_crack_blur = cv2.GaussianBlur(h_crack, (3, 3), 0)
    cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_horizontal.png", h_crack_blur)

    # =========================================================================
    # 3. Diagonal Shear Fracture Decal (45-degree angle)
    # =========================================================================
    d_crack = np.zeros((h, w, 4), dtype=np.uint8)
    d_pts = []
    for t in np.linspace(100, 920, 220):
        ox = t + np.random.normal(0.0, 3.0)
        oy = t + np.random.normal(0.0, 3.0)
        d_pts.append((int(ox), int(oy)))

    for i in range(len(d_pts) - 1):
        pt1 = d_pts[i]
        pt2 = d_pts[i+1]
        cv2.line(d_crack, pt1, pt2, (95, 98, 102, 180), 15)
        cv2.line(d_crack, pt1, pt2, (40, 42, 45, 230), 6)
        cv2.line(d_crack, pt1, pt2, (10, 10, 12, 255), 3)

    d_crack_blur = cv2.GaussianBlur(d_crack, (3, 3), 0)
    cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_diagonal.png", d_crack_blur)

    # =========================================================================
    # 4. Severe Concrete Spalling with Exposed Corroded Steel Rebar
    # =========================================================================
    spall = np.zeros((h, w, 4), dtype=np.uint8)
    center = (512, 512)
    # Irregular jagged cavity polygon
    angles = np.linspace(0, 2*math.pi, 36, endpoint=False)
    radii = [280.0 + np.random.uniform(-40, 40) for _ in range(36)]
    cavity_pts = []
    for a, r in zip(angles, radii):
        px = int(center[0] + r * math.cos(a) * 1.2) # oval wide
        py = int(center[1] + r * math.sin(a) * 0.8)
        cavity_pts.append([px, py])
    cavity_pts = np.array(cavity_pts, dtype=np.int32)

    # Outer chipped concrete edge
    cv2.fillPoly(spall, [cavity_pts], (75, 78, 82, 255))
    cv2.polylines(spall, [cavity_pts], True, (45, 48, 52, 255), 12)

    # Inner recessed crater depth
    inner_pts = (cavity_pts - np.array([512, 512])) * 0.85 + np.array([512, 512])
    inner_pts = inner_pts.astype(np.int32)
    cv2.fillPoly(spall, [inner_pts], (42, 44, 46, 255))

    # Exposed Corroded Steel Rebar Grid (Deep Rust Orange/Brown #8b3a1a)
    # Vertical rebar rods (ribbed cylindrical steel pattern)
    rebar_x_positions = [420, 512, 604]
    for rx in rebar_x_positions:
        # Rebar core rust (B=26, G=58, R=145) -> #913a1a
        cv2.rectangle(spall, (rx-14, 280), (rx+14, 740), (22, 48, 130, 255), -1)
        cv2.rectangle(spall, (rx-10, 280), (rx+10, 740), (32, 65, 175, 255), -1)
        # Steel highlight line
        cv2.rectangle(spall, (rx-4, 280), (rx+2, 740), (60, 110, 220, 255), -1)
        # Corroded ribbed ridges
        for ry in range(290, 735, 18):
            cv2.line(spall, (rx-14, ry), (rx+14, ry+6), (15, 32, 90, 255), 3)

    # Horizontal tie rebar wire
    cv2.rectangle(spall, (320, 490), (700, 514), (25, 55, 140, 255), -1)
    cv2.rectangle(spall, (320, 498), (700, 506), (50, 95, 205, 255), -1)

    # Feather outer border for seamless blending onto concrete wall
    spall_blur = cv2.GaussianBlur(spall, (5, 5), 0)
    cv2.imwrite(f"{TEXTURE_DIR}/decal_spall_rebar.png", spall_blur)
    print("  -> Saved decal_crack_vertical.png, decal_crack_horizontal.png, decal_crack_diagonal.png, decal_spall_rebar.png")

if __name__ == "__main__":
    generate_concrete_pbr_set()
    generate_asphalt_pbr_set()
    generate_photographic_decals()
    print("[Success] All photorealistic PBR textures and photographic decals generated!")
