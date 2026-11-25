#!/usr/bin/env python3
"""
INFYNEX High-Fidelity Photorealistic Damage Decal Generator
Generates concrete-backed defect textures that blend seamlessly onto PBR concrete walls.
"""
import os
import math
import numpy as np
import cv2

TEXTURE_DIR = "simulation/gazebo/models/materials/textures"
os.makedirs(TEXTURE_DIR, exist_ok=True)

# Load base concrete albedo if exists, otherwise generate
base_path = f"{TEXTURE_DIR}/concrete_albedo.jpg"
if os.path.exists(base_path):
    base_concrete = cv2.imread(base_path)
    if base_concrete.shape[:2] != (1024, 1024):
        base_concrete = cv2.resize(base_concrete, (1024, 1024))
else:
    base_concrete = np.full((1024, 1024, 3), 130, dtype=np.uint8)

h, w = 1024, 1024

# =========================================================================
# 1. Vertical Structural Tension Crack
# =========================================================================
v_img = base_concrete.copy()
np.random.seed(101)
cur_x = 512.0
pts = []
for y in range(60, 960, 4):
    cur_x += np.random.normal(0.0, 1.8)
    cur_x = np.clip(cur_x, 420.0, 604.0)
    pts.append((int(cur_x), y))

# Draw distressed fracture halo & dark inner fissure
for i in range(len(pts) - 1):
    p1, p2 = pts[i], pts[i+1]
    # Weathered moisture staining along crack
    cv2.line(v_img, p1, p2, (85, 88, 90), 22)
    # Concrete fracture edge micro-spalling
    cv2.line(v_img, p1, p2, (50, 52, 54), 10)
    # Inner dark void fissure
    cv2.line(v_img, p1, p2, (10, 12, 14), 4)

# Side branch
for i in range(len(pts)//3, len(pts)//2):
    p1 = pts[i]
    p2 = (p1[0] + (i - len(pts)//3)*2, p1[1] + 3)
    cv2.line(v_img, p1, p2, (20, 22, 24), 2)

v_img = cv2.GaussianBlur(v_img, (3, 3), 0)
cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_vertical.jpg", v_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_vertical.png", v_img)
print("Saved decal_crack_vertical.jpg")

# =========================================================================
# 2. Horizontal Flexural Shear Crack
# =========================================================================
h_img = base_concrete.copy()
cur_y = 512.0
h_pts = []
for x in range(60, 960, 4):
    cur_y += np.random.normal(0.0, 1.5)
    cur_y = np.clip(cur_y, 440.0, 584.0)
    h_pts.append((x, int(cur_y)))

for i in range(len(h_pts) - 1):
    p1, p2 = h_pts[i], h_pts[i+1]
    cv2.line(h_img, p1, p2, (85, 88, 90), 24)
    cv2.line(h_img, p1, p2, (50, 52, 54), 12)
    cv2.line(h_img, p1, p2, (10, 12, 14), 4)

h_img = cv2.GaussianBlur(h_img, (3, 3), 0)
cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_horizontal.jpg", h_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_horizontal.png", h_img)
print("Saved decal_crack_horizontal.jpg")

# =========================================================================
# 3. Diagonal Shear Fracture (45-degree)
# =========================================================================
d_img = base_concrete.copy()
d_pts = []
for t in np.linspace(80, 940, 240):
    ox = t + np.random.normal(0.0, 2.5)
    oy = t + np.random.normal(0.0, 2.5)
    d_pts.append((int(ox), int(oy)))

for i in range(len(d_pts) - 1):
    p1, p2 = d_pts[i], d_pts[i+1]
    cv2.line(d_img, p1, p2, (85, 88, 90), 22)
    cv2.line(d_img, p1, p2, (48, 50, 52), 10)
    cv2.line(d_img, p1, p2, (10, 12, 14), 4)

d_img = cv2.GaussianBlur(d_img, (3, 3), 0)
cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_diagonal.jpg", d_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
cv2.imwrite(f"{TEXTURE_DIR}/decal_crack_diagonal.png", d_img)
print("Saved decal_crack_diagonal.jpg")

# =========================================================================
# 4. Severe Concrete Spalling with Exposed Corroded Steel Rebar
# =========================================================================
s_img = base_concrete.copy()
center = (512, 512)
angles = np.linspace(0, 2*math.pi, 48, endpoint=False)
radii = [310.0 + np.random.uniform(-35, 35) for _ in range(48)]
cavity_pts = []
for a, r in zip(angles, radii):
    px = int(center[0] + r * math.cos(a) * 1.15)
    py = int(center[1] + r * math.sin(a) * 0.82)
    cavity_pts.append([px, py])
cavity_pts = np.array(cavity_pts, dtype=np.int32)

# Chipped outer spall edge
cv2.fillPoly(s_img, [cavity_pts], (75, 78, 80))
cv2.polylines(s_img, [cavity_pts], True, (45, 48, 50), 14)

# Deep inner cavity
inner_pts = ((cavity_pts - np.array([512, 512])) * 0.82 + np.array([512, 512])).astype(np.int32)
cv2.fillPoly(s_img, [inner_pts], (38, 40, 42))

# Corroded Steel Rebar Grid (#8b3a1a rust orange/brown)
rebar_x_positions = [400, 512, 624]
for rx in rebar_x_positions:
    # Outer rust band
    cv2.rectangle(s_img, (rx-16, 260), (rx+16, 760), (18, 42, 125), -1)
    # Bright rust core
    cv2.rectangle(s_img, (rx-10, 260), (rx+10, 760), (28, 62, 175), -1)
    # Metallic highlight
    cv2.rectangle(s_img, (rx-3, 260), (rx+3, 760), (55, 105, 215), -1)
    # Rebar ribbed deforms
    for ry in range(275, 750, 16):
        cv2.line(s_img, (rx-16, ry), (rx+16, ry+6), (12, 28, 85), 3)

# Horizontal rebar cross-tie
cv2.rectangle(s_img, (290, 490), (730, 520), (20, 48, 135), -1)
cv2.rectangle(s_img, (290, 498), (730, 512), (32, 70, 190), -1)

s_img = cv2.GaussianBlur(s_img, (3, 3), 0)
cv2.imwrite(f"{TEXTURE_DIR}/decal_spall_rebar.jpg", s_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
cv2.imwrite(f"{TEXTURE_DIR}/decal_spall_rebar.png", s_img)
print("Saved decal_spall_rebar.jpg")

print("All realistic decals generated successfully!")
