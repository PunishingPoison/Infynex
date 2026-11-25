#!/usr/bin/env python3
"""
INFYNEX Defect Severity Classifier
Converts ray depth distance d and pixel dimensions into physical millimeters:
  physical_width_mm = (pixel_width * ray_depth_m) / fx * 1000.0
Assigns structural severity rating: minor, moderate, critical.
"""

def classify_severity(class_name: str, pixel_bbox: list[int], ray_depth_m: float, fx: float = 762.72) -> dict:
    xmin, ymin, xmax, ymax = pixel_bbox
    pixel_w = abs(xmax - xmin)
    pixel_h = abs(ymax - ymin)

    # Compute physical width & height in millimeters using optical ray depth
    physical_w_mm = round((pixel_w * ray_depth_m / fx) * 10.0, 2)
    physical_h_mm = round((pixel_h * ray_depth_m / fx) * 1000.0, 1)

    if class_name == "spalling":
        # Spalling area in mm^2
        area_cm2 = round((physical_w_mm * (physical_h_mm / 10.0)) / 100.0, 1)
        severity = "critical" if area_cm2 > 150.0 else "moderate"
        metric_str = f"Spall Area: {area_cm2} cm²"
    else:
        # Crack width in mm
        crack_width_mm = round(min(physical_w_mm, 1.2), 2)
        if crack_width_mm >= 0.50:
            severity = "critical"
        elif crack_width_mm >= 0.30:
            severity = "moderate"
        else:
            severity = "minor"
        metric_str = f"Crack Width: {crack_width_mm} mm"

    return {
        "severity": severity,
        "physical_width_mm": physical_w_mm,
        "physical_height_mm": physical_h_mm,
        "metric_summary": metric_str,
        "ray_depth_m": round(ray_depth_m, 2)
    }
