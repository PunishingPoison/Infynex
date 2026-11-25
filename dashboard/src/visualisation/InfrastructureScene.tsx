import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface SceneProps {
  dronePos: { x: number; y: number; z: number };
  damages: Array<{ damage_id: string; category: string; severity: string; position: { x: number; y: number; z: number } }>;
  onSelectDamage?: (id: string) => void;
}

export const InfrastructureScene: React.FC<SceneProps> = ({ dronePos, damages, onSelectDamage }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const droneMeshRef = useRef<THREE.Group | null>(null);
  const rotorMeshesRef = useRef<THREE.Mesh[]>([]);
  const targetPosRef = useRef(dronePos);

  useEffect(() => {
    targetPosRef.current = dronePos;
  }, [dronePos]);

  useEffect(() => {
    if (!mountRef.current) return;

    const width = mountRef.current.clientWidth;
    const height = mountRef.current.clientHeight;

    // 1. Scene & Camera Setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x090D16);
    scene.fog = new THREE.FogExp2(0x090D16, 0.018);

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100);
    camera.position.set(-7.0, -11.0, 9.0);
    camera.up.set(0, 0, 1); // Z is Up
    camera.lookAt(4.2, 0, 3.0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mountRef.current.appendChild(renderer.domElement);

    // 2. Realistic Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xBAE6FD, 1.5);
    sunLight.position.set(-8, -12, 20);
    sunLight.castShadow = true;
    scene.add(sunLight);

    const fillLight = new THREE.DirectionalLight(0xF8FAFC, 0.6);
    fillLight.position.set(10, 12, 10);
    scene.add(fillLight);

    // 3. Ground Grid
    const gridHelper = new THREE.GridHelper(30, 30, 0x0284C7, 0x1E293B);
    gridHelper.rotation.x = Math.PI / 2;
    scene.add(gridHelper);

    // 4. Helipad Takeoff & Landing Zone
    const padGeo = new THREE.CylinderGeometry(1.3, 1.3, 0.04, 32);
    const padMat = new THREE.MeshStandardMaterial({ color: 0xF59E0B, roughness: 0.4, metalness: 0.2 });
    const pad = new THREE.Mesh(padGeo, padMat);
    pad.rotation.x = Math.PI / 2;
    pad.position.set(0, 0, 0.02);
    scene.add(pad);

    const ringGeo = new THREE.RingGeometry(0.85, 1.05, 32);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xFFFFFF, side: THREE.DoubleSide });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.set(0, 0, 0.042);
    scene.add(ring);

    // 5. Full 360-Degree Concrete Infrastructure Asset
    const structureGroup = new THREE.Group();
    const concreteMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      roughness: 0.88,
      metalness: 0.12
    });
    const darkConcreteMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      roughness: 0.92,
      metalness: 0.08
    });

    // Massive Reinforced Foundation Pad
    const foundGeo = new THREE.BoxGeometry(5.0, 7.0, 0.6);
    const foundMesh = new THREE.Mesh(foundGeo, darkConcreteMat);
    foundMesh.position.set(5.0, 0.0, 0.3);
    structureGroup.add(foundMesh);

    // North Pier (Front Left)
    const p1Geo = new THREE.BoxGeometry(1.2, 1.2, 4.5);
    const p1 = new THREE.Mesh(p1Geo, concreteMat);
    p1.position.set(4.5, -2.0, 2.75);
    structureGroup.add(p1);

    // South Pier (Front Right)
    const p2Geo = new THREE.BoxGeometry(1.2, 1.2, 4.5);
    const p2 = new THREE.Mesh(p2Geo, concreteMat);
    p2.position.set(4.5, 2.0, 2.75);
    structureGroup.add(p2);

    // Central Structural Web / Front Retaining Wall
    const wallGeo = new THREE.BoxGeometry(0.6, 3.2, 4.2);
    const wallMesh = new THREE.Mesh(wallGeo, concreteMat);
    wallMesh.position.set(4.8, 0.0, 2.7);
    structureGroup.add(wallMesh);

    // Rear Abutment Support (South Face)
    const rearGeo = new THREE.BoxGeometry(0.8, 4.5, 4.2);
    const rearMesh = new THREE.Mesh(rearGeo, darkConcreteMat);
    rearMesh.position.set(5.4, 0.0, 2.7);
    structureGroup.add(rearMesh);

    // Overhead Bridge Deck & Cantilever Girder Beam
    const deckGeo = new THREE.BoxGeometry(2.4, 6.8, 0.8);
    const deckMesh = new THREE.Mesh(deckGeo, concreteMat);
    deckMesh.position.set(4.8, 0.0, 5.2);
    structureGroup.add(deckMesh);

    // Parapet Safety Railings
    const railGeo = new THREE.BoxGeometry(0.15, 6.8, 0.5);
    const rail1 = new THREE.Mesh(railGeo, darkConcreteMat);
    rail1.position.set(3.7, 0.0, 5.8);
    structureGroup.add(rail1);

    const rail2 = new THREE.Mesh(railGeo, darkConcreteMat);
    rail2.position.set(5.9, 0.0, 5.8);
    structureGroup.add(rail2);

    scene.add(structureGroup);

    // 6. Drone 3D Representation
    const droneGroup = new THREE.Group();
    // Central Hub
    const hubGeo = new THREE.BoxGeometry(0.38, 0.38, 0.12);
    const hubMat = new THREE.MeshStandardMaterial({ color: 0x0EA5E9, metalness: 0.85, roughness: 0.2 });
    const hub = new THREE.Mesh(hubGeo, hubMat);
    droneGroup.add(hub);

    // Carbon Fiber Arms
    const armGeo = new THREE.CylinderGeometry(0.018, 0.018, 0.65);
    const armMat = new THREE.MeshStandardMaterial({ color: 0x1E293B, metalness: 0.8 });
    const arm1 = new THREE.Mesh(armGeo, armMat);
    arm1.rotation.z = Math.PI / 4;
    droneGroup.add(arm1);

    const arm2 = new THREE.Mesh(armGeo, armMat);
    arm2.rotation.z = -Math.PI / 4;
    droneGroup.add(arm2);

    // 4 Rotors
    const rotors: THREE.Mesh[] = [];
    const rotorGeo = new THREE.BoxGeometry(0.22, 0.024, 0.006);
    const rotorMat = new THREE.MeshBasicMaterial({ color: 0x38BDF8 });
    const armOffsets = [
      [-0.23, -0.23], [0.23, 0.23], [-0.23, 0.23], [0.23, -0.23]
    ];
    armOffsets.forEach(([ox, oy]) => {
      const r = new THREE.Mesh(rotorGeo, rotorMat);
      r.position.set(ox, oy, 0.08);
      droneGroup.add(r);
      rotors.push(r);
    });
    rotorMeshesRef.current = rotors;

    // Optical Camera Gimbal & Lens
    const camGeo = new THREE.BoxGeometry(0.12, 0.12, 0.08);
    const camMat = new THREE.MeshStandardMaterial({ color: 0x059669 });
    const cam = new THREE.Mesh(camGeo, camMat);
    cam.position.set(0.22, 0, -0.04);
    droneGroup.add(cam);

    const lensGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.04, 16);
    const lensMat = new THREE.MeshBasicMaterial({ color: 0x10B981 });
    const lens = new THREE.Mesh(lensGeo, lensMat);
    lens.rotation.z = Math.PI / 2;
    lens.position.set(0.28, 0, -0.04);
    droneGroup.add(lens);

    droneGroup.position.set(dronePos.x, dronePos.y, dronePos.z);
    scene.add(droneGroup);
    droneMeshRef.current = droneGroup;

    // 7. Multi-Quadrant 360-Degree Defect Markers
    const activeDefects = damages && damages.length > 0 ? damages.map(d => ({
      id: d.damage_id,
      cat: d.category,
      sev: d.severity,
      pos: [d.position.x, d.position.y, d.position.z],
      label: `${d.category.toUpperCase()} (${d.severity})`
    })) : [
      { id: "CRACK_001", cat: "crack", sev: "severe", pos: [4.74, -1.15, 2.54], label: "North Face: Vertical Crack" },
      { id: "SPALL_001", cat: "spalling", sev: "critical", pos: [4.74, 0.20, 3.20], label: "East Flank: Concrete Spalling" },
      { id: "CRACK_002", cat: "crack", sev: "severe", pos: [5.20, 0.05, 3.50], label: "South Face: Seismic Fracture" },
      { id: "CRACK_003", cat: "crack", sev: "moderate", pos: [4.50, -1.80, 3.00], label: "West Flank: Diagonal Shear" },
      { id: "SPALL_002", cat: "spalling", sev: "high", pos: [4.50, 1.20, 4.75], label: "Top Girder: Beam Delamination" }
    ];

    const damageGroup = new THREE.Group();
    const damageMarkers: THREE.Mesh[] = [];

    activeDefects.forEach((d) => {
      const isCritical = d.sev === 'critical';
      const markerGeo = new THREE.SphereGeometry(0.15, 16, 16);
      const markerMat = new THREE.MeshBasicMaterial({
        color: isCritical ? 0xEF4444 : 0xF59E0B
      });
      const marker = new THREE.Mesh(markerGeo, markerMat);
      marker.position.set(d.pos[0], d.pos[1], d.pos[2]);
      marker.userData = { id: d.id };
      damageGroup.add(marker);
      damageMarkers.push(marker);

      // Marker pointer needle
      const needleGeo = new THREE.CylinderGeometry(0.015, 0.015, 0.4);
      const needleMat = new THREE.MeshBasicMaterial({ color: 0xFFFFFF });
      const needle = new THREE.Mesh(needleGeo, needleMat);
      needle.position.set(d.pos[0] - 0.12, d.pos[1], d.pos[2]);
      needle.rotation.z = Math.PI / 2;
      damageGroup.add(needle);
    });
    scene.add(damageGroup);

    const handlePointerDown = (event: MouseEvent) => {
      if (!onSelectDamage) return;
      const rect = renderer.domElement.getBoundingClientRect();
      const mouse = new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1
      );
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(damageMarkers);
      if (intersects.length > 0) {
        const id = intersects[0].object.userData?.id;
        if (id) onSelectDamage(id);
      }
    };
    renderer.domElement.addEventListener('pointerdown', handlePointerDown);

    // 8. Flight Path Trail
    const trailGeo = new THREE.BufferGeometry();
    const trailPositions = new Float32Array(300 * 3);
    trailGeo.setAttribute('position', new THREE.BufferAttribute(trailPositions, 3));
    const trailMat = new THREE.LineBasicMaterial({ color: 0x38BDF8, transparent: true, opacity: 0.6 });
    const trailLine = new THREE.Line(trailGeo, trailMat);
    scene.add(trailLine);
    let trailIndex = 0;

    // 9. Animation Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();

      // Smooth drone motion interpolation
      if (droneMeshRef.current) {
        const target = targetPosRef.current;
        const dx = (target.x - droneMeshRef.current.position.x);
        const dy = (target.y - droneMeshRef.current.position.y);
        const dz = (target.z - droneMeshRef.current.position.z);

        droneMeshRef.current.position.x += dx * 0.12;
        droneMeshRef.current.position.y += dy * 0.12;
        droneMeshRef.current.position.z += dz * 0.12;

        // Dynamic Banking & Pitch into Flight Direction
        const speed = Math.sqrt(dx * dx + dy * dy);
        if (speed > 0.01) {
          const moveAngle = Math.atan2(dy, dx);
          droneMeshRef.current.rotation.z = THREE.MathUtils.lerp(droneMeshRef.current.rotation.z, moveAngle, 0.08);
          droneMeshRef.current.rotation.y = THREE.MathUtils.lerp(droneMeshRef.current.rotation.y, -Math.min(0.25, speed * 2), 0.1);
        } else {
          droneMeshRef.current.rotation.y = THREE.MathUtils.lerp(droneMeshRef.current.rotation.y, 0, 0.1);
        }

        // Spin Rotors when airborne
        if (droneMeshRef.current.position.z > 0.1) {
          rotors.forEach(r => {
            r.rotation.z += delta * 40.0;
          });
        }

        // Update Flight Trail
        if (trailIndex < 300) {
          trailPositions[trailIndex * 3] = droneMeshRef.current.position.x;
          trailPositions[trailIndex * 3 + 1] = droneMeshRef.current.position.y;
          trailPositions[trailIndex * 3 + 2] = droneMeshRef.current.position.z;
          trailGeo.attributes.position.needsUpdate = true;
          trailIndex = (trailIndex + 1) % 300;
        }
      }

      // Pulse Damage Defect Spheres
      damageMarkers.forEach((m, idx) => {
        const s = 1.0 + Math.sin(elapsed * 5.0 + idx * 1.5) * 0.28;
        m.scale.set(s, s, s);
      });

      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!mountRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      cancelAnimationFrame(animId);
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return <div ref={mountRef} className="w-full h-full relative" />;
};
