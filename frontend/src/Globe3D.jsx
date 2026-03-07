import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function Globe3D({ satellites, debris }) {
  const mountRef = useRef();
  const sceneRef = useRef();
  const frameRef = useRef();

  useEffect(() => {
    const mount = mountRef.current;
    const W = mount.clientWidth;
    const H = mount.clientHeight;

    // ── Renderer ────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    mount.appendChild(renderer.domElement);

    // ── Scene & Camera ───────────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#070a10");
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100000);
    camera.position.set(0, 0, 22000);

    // ── Starfield ────────────────────────────────────────────────────────────
    const starGeo = new THREE.BufferGeometry();
    const starVerts = [];
    for (let i = 0; i < 8000; i++) {
      const theta = Math.random() * 2 * Math.PI;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 80000 + Math.random() * 20000;
      starVerts.push(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
      );
    }
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(starVerts, 3));
    const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 60, sizeAttenuation: true });
    scene.add(new THREE.Points(starGeo, starMat));

    // ── Earth ────────────────────────────────────────────────────────────────
    const earthGeo = new THREE.SphereGeometry(6371, 64, 64);

    // Procedural Earth — blue ocean with green/brown land approximation
    const earthCanvas = document.createElement("canvas");
    earthCanvas.width = 1024; earthCanvas.height = 512;
    const ctx = earthCanvas.getContext("2d");

    // Ocean base
    const oceanGrad = ctx.createLinearGradient(0, 0, 0, 512);
    oceanGrad.addColorStop(0, "#0a1628");
    oceanGrad.addColorStop(0.5, "#0d2240");
    oceanGrad.addColorStop(1, "#0a1628");
    ctx.fillStyle = oceanGrad;
    ctx.fillRect(0, 0, 1024, 512);

    // Simplified continent blobs
    ctx.fillStyle = "#1a3a1a";
    const continents = [
      [120, 180, 140, 100], // North America
      [200, 220, 80, 120],  // South America
      [480, 160, 120, 140], // Europe/Africa
      [560, 200, 100, 120], // Africa lower
      [680, 150, 140, 100], // Asia
      [820, 280, 80, 60],   // Australia
    ];
    continents.forEach(([x, y, w, h]) => {
      ctx.beginPath();
      ctx.ellipse(x, y, w, h, 0, 0, Math.PI * 2);
      ctx.fill();
    });

    // Ice caps
    ctx.fillStyle = "#c8e0f0";
    ctx.fillRect(0, 0, 1024, 30);
    ctx.fillRect(0, 482, 1024, 30);

    // Grid lines
    ctx.strokeStyle = "rgba(100,160,255,0.08)";
    ctx.lineWidth = 1;
    for (let lon = 0; lon < 1024; lon += 1024 / 12) {
      ctx.beginPath(); ctx.moveTo(lon, 0); ctx.lineTo(lon, 512); ctx.stroke();
    }
    for (let lat = 0; lat < 512; lat += 512 / 6) {
      ctx.beginPath(); ctx.moveTo(0, lat); ctx.lineTo(1024, lat); ctx.stroke();
    }

    const earthTex = new THREE.CanvasTexture(earthCanvas);
    const earthMat = new THREE.MeshPhongMaterial({
      map: earthTex,
      specular: new THREE.Color(0x112244),
      shininess: 25,
    });
    const earth = new THREE.Mesh(earthGeo, earthMat);
    scene.add(earth);

    // Atmosphere glow
    const atmGeo = new THREE.SphereGeometry(6571, 64, 64);
    const atmMat = new THREE.MeshPhongMaterial({
      color: 0x4488ff,
      transparent: true,
      opacity: 0.08,
      side: THREE.FrontSide,
    });
    scene.add(new THREE.Mesh(atmGeo, atmMat));

    // ── Lighting ─────────────────────────────────────────────────────────────
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(50000, 20000, 30000);
    scene.add(sun);
    scene.add(new THREE.AmbientLight(0x223344, 0.6));

    // ── Orbital rings (decorative) ────────────────────────────────────────────
    const ringGeo = new THREE.TorusGeometry(7200, 4, 2, 120);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xf0a500, transparent: true, opacity: 0.06 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 2;
    scene.add(ring);

    // ── Satellite group ───────────────────────────────────────────────────────
    const satGroup = new THREE.Group();
    scene.add(satGroup);

    // ── Debris group ─────────────────────────────────────────────────────────
    const debGroup = new THREE.Group();
    scene.add(debGroup);

    // ── Ground stations ───────────────────────────────────────────────────────
    const gsData = [
      [13.03, 77.52], [78.23, 15.41], [35.43, -116.89],
      [-53.15, -70.92], [28.55, 77.19], [-77.85, 166.67],
    ];
    const latLonToXYZ = (lat, lon, r) => {
      const phi = (90 - lat) * Math.PI / 180;
      const theta = (lon + 180) * Math.PI / 180;
      return new THREE.Vector3(
        -r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta)
      );
    };
    gsData.forEach(([lat, lon]) => {
      const pos = latLonToXYZ(lat, lon, 6390);
      const gsGeo = new THREE.SphereGeometry(30, 8, 8);
      const gsMat = new THREE.MeshBasicMaterial({ color: 0x4fc3f7 });
      const gs = new THREE.Mesh(gsGeo, gsMat);
      gs.position.copy(pos);
      scene.add(gs);

      // Ping ring
      const pingGeo = new THREE.TorusGeometry(80, 8, 4, 24);
      const pingMat = new THREE.MeshBasicMaterial({ color: 0x4fc3f7, transparent: true, opacity: 0.3 });
      const ping = new THREE.Mesh(pingGeo, pingMat);
      ping.position.copy(pos);
      ping.lookAt(new THREE.Vector3(0, 0, 0));
      scene.add(ping);
    });

    // ── Mouse drag rotation ───────────────────────────────────────────────────
    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };
    let rotX = 0, rotY = 0;

    const onMouseDown = (e) => { isDragging = true; prevMouse = { x: e.clientX, y: e.clientY }; };
    const onMouseUp = () => { isDragging = false; };
    const onMouseMove = (e) => {
      if (!isDragging) return;
      rotY += (e.clientX - prevMouse.x) * 0.005;
      rotX += (e.clientY - prevMouse.y) * 0.005;
      rotX = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, rotX));
      prevMouse = { x: e.clientX, y: e.clientY };
    };
    const onWheel = (e) => {
      camera.position.z = Math.max(8000, Math.min(40000, camera.position.z + e.deltaY * 5));
    };

    mount.addEventListener("mousedown", onMouseDown);
    mount.addEventListener("mouseup", onMouseUp);
    mount.addEventListener("mousemove", onMouseMove);
    mount.addEventListener("wheel", onWheel);

    // ── Animate ───────────────────────────────────────────────────────────────
    let autoRotY = 0;

    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);

      if (!isDragging) autoRotY += 0.001;

      earth.rotation.y = autoRotY + rotY;
      earth.rotation.x = rotX;

      // Update satellites
      while (satGroup.children.length) satGroup.remove(satGroup.children[0]);
      if (satellites && satellites.length > 0) {
        satellites.forEach(sat => {
          // Convert ECI km to scene units (1:1 km)
          const pos = new THREE.Vector3(sat.x || 0, sat.z || 0, sat.y || 0);

          // Glow sprite
          const spriteMat = new THREE.SpriteMaterial({
            color: sat.status === "NOMINAL" ? 0x00ff87 :
                   sat.status === "EOL" ? 0xff3a3a : 0xffe066,
            transparent: true, opacity: 0.9,
          });
          const sprite = new THREE.Sprite(spriteMat);
          sprite.position.copy(pos);
          sprite.scale.set(200, 200, 1);
          satGroup.add(sprite);

          // Core dot
          const dotGeo = new THREE.SphereGeometry(40, 8, 8);
          const dotMat = new THREE.MeshBasicMaterial({
            color: sat.status === "NOMINAL" ? 0x00ff87 :
                   sat.status === "EOL" ? 0xff3a3a : 0xffe066
          });
          const dot = new THREE.Mesh(dotGeo, dotMat);
          dot.position.copy(pos);
          satGroup.add(dot);
        });
      }

      // Update debris
      while (debGroup.children.length) debGroup.remove(debGroup.children[0]);
      if (debris && debris.length > 0) {
        const debGeo = new THREE.BufferGeometry();
        const positions = [];
        debris.slice(0, 500).forEach(d => {
          if (d[3] && d[4] && d[5]) {
            positions.push(d[3], d[5], d[4]);
          }
        });
        if (positions.length > 0) {
          debGeo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
          const debMat = new THREE.PointsMaterial({ color: 0xff4444, size: 30, transparent: true, opacity: 0.6 });
          debGroup.add(new THREE.Points(debGeo, debMat));
        }
      }

      renderer.render(scene, camera);
    };
    animate();

    // ── Cleanup ───────────────────────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(frameRef.current);
      mount.removeEventListener("mousedown", onMouseDown);
      mount.removeEventListener("mouseup", onMouseUp);
      mount.removeEventListener("mousemove", onMouseMove);
      mount.removeEventListener("wheel", onWheel);
      mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [satellites, debris]);

  return (
    <div ref={mountRef} style={{ width: "100%", height: "100%", cursor: "grab" }} />
  );
}