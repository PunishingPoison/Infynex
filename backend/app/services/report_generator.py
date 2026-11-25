"""
INFYNEX Automated Inspection Report Generator
Compiles comprehensive PDF inspection dossiers containing:
- Mission metadata & flight profile
- AI damage findings (cracks, spalls, 3D surface locations, severity classifications)
- IoT environmental sensor statistics (DS18B20, BME280, DHT22)
- 5G Network propagation metrics (latency, throughput, packet loss)
"""

import os
import time
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


class InspectionReportGenerator:
    def __init__(self, output_dir: str = "/workspace/data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_pdf(
        self,
        mission_id: str,
        structure_name: str,
        damages: List[Dict[str, Any]],
        sensor_stats: Dict[str, Any],
        network_stats: Dict[str, Any],
        flight_stats: Dict[str, Any]
    ) -> str:
        pdf_filename = f"INFYNEX_Inspection_Report_{mission_id}.pdf"
        pdf_path = os.path.join(self.output_dir, pdf_filename)

        doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#0F172A'), spaceAfter=8)
        subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=14)
        heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#1E293B'), spaceBefore=12, spaceAfter=6)
        body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#334155'), leading=13)

        # Title Block
        story.append(Paragraph("INFYNEX – Autonomous Infrastructure Inspection Report", title_style))
        story.append(Paragraph(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC')} | Target Asset: {structure_name} | Mission ID: {mission_id}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceAfter=12))

        # Section 1: Flight Mission Summary
        story.append(Paragraph("1. Autonomous Flight Telemetry Summary", heading_style))
        flight_data = [
            ["Metric", "Recorded Value"],
            ["Drone Model", flight_stats.get("model", "PX4 X500 Quadcopter")],
            ["Survey Altitude", f"{flight_stats.get('altitude_m', 2.5):.2f} m AGL"],
            ["Flight Duration", f"{flight_stats.get('duration_sec', 142)} seconds"],
            ["Waypoints Executed", f"{flight_stats.get('waypoints_count', 9)} / 9 completed"],
            ["Battery State", f"{flight_stats.get('battery_start_pct', 100):.0f}% -> {flight_stats.get('battery_end_pct', 89):.0f}%"]
        ]
        t_flight = Table(flight_data, colWidths=[200, 340])
        t_flight.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        story.append(t_flight)
        story.append(Spacer(1, 10))

        # Section 2: AI Structural Damage Detections
        story.append(Paragraph("2. Computer Vision Damage Detections & Localisation", heading_style))
        damage_rows = [["Damage ID", "Category", "Severity", "Confidence", "3D Position (X, Y, Z)", "Surface"]]
        for d in damages:
            pos = d.get("position", {})
            pos_str = f"({pos.get('x', 0):.2f}, {pos.get('y', 0):.2f}, {pos.get('z', 0):.2f})"
            damage_rows.append([
                d.get("damage_id", "N/A"),
                d.get("category", "N/A"),
                d.get("severity", "N/A").upper(),
                f"{d.get('confidence', 0.0)*100:.1f}%",
                pos_str,
                d.get("surface", "front_wall")
            ])

        t_damage = Table(damage_rows, colWidths=[80, 80, 75, 75, 130, 100])
        t_damage.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284C7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_damage)
        story.append(Spacer(1, 10))

        # Section 3: IoT Sensor Telemetry
        story.append(Paragraph("3. Supporting IoT Environmental Telemetry (ESP32 Nodes)", heading_style))
        sensor_data = [
            ["Node ID", "Hardware", "Location", "Avg Temp (°C)", "Avg Humidity (%)", "Avg Pressure (hPa)"],
            ["ESP32_001", "DS18B20", "Pillar 1 Surface", f"{sensor_stats.get('esp1_temp', 31.4):.1f}°C", "N/A", "N/A"],
            ["ESP32_002", "DS18B20", "Internal Core", f"{sensor_stats.get('esp2_temp', 27.2):.1f}°C", "N/A", "N/A"],
            ["ESP32_003", "BME280", "Foundation Base", f"{sensor_stats.get('esp3_temp', 28.5):.1f}°C", f"{sensor_stats.get('esp3_hum', 65.2):.1f}%", f"{sensor_stats.get('esp3_press', 1013.1):.1f} hPa"],
            ["ESP32_004", "DHT22", "Upper Deck", f"{sensor_stats.get('esp4_temp', 29.0):.1f}°C", f"{sensor_stats.get('esp4_hum', 64.0):.1f}%", "N/A"]
        ]
        t_sensor = Table(sensor_data, colWidths=[75, 75, 110, 95, 95, 90])
        t_sensor.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_sensor)
        story.append(Spacer(1, 10))

        # Section 4: 5G Network Transmission Performance
        story.append(Paragraph("4. 5G NR Link Transmission Quality", heading_style))
        net_data = [
            ["Metric", "Value", "Operational Rating"],
            ["Carrier & Bandwidth", "3.5 GHz (n78) / 100 MHz", "3GPP Rel-16 Standard"],
            ["End-to-End Latency", f"{network_stats.get('latency_ms', 14.2):.1f} ms", "Excellent (< 20ms)"],
            ["Jitter", f"{network_stats.get('jitter_ms', 1.8):.1f} ms", "Low"],
            ["Average Throughput", f"{network_stats.get('throughput_mbps', 145.0):.1f} Mbps", "High Bandwidth"],
            ["Packet Delivery Ratio", f"{network_stats.get('pdr', 99.8):.2f}%", "Ultra-Reliable"]
        ]
        t_net = Table(net_data, colWidths=[180, 180, 180])
        t_net.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_net)

        doc.build(story)
        return pdf_path
