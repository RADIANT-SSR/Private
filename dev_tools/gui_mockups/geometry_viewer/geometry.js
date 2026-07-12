// geometry.js — vector math + 3D→2D projection for the schematic scene.
// All angles in degrees in the public API. Internally we work in radians.
// Coordinate frame: +X = East, +Y = North, +Z = Up (zenith).
// Camera: orthographic; we just rotate world points by yaw (about Z) and
// pitch (about X), then drop Z. Schematic = no perspective.

(function () {
  const D2R = Math.PI / 180;
  const R2D = 180 / Math.PI;

  function v(x, y, z) { return { x, y, z }; }
  function add(a, b) { return v(a.x + b.x, a.y + b.y, a.z + b.z); }
  function sub(a, b) { return v(a.x - b.x, a.y - b.y, a.z - b.z); }
  function scale(a, s) { return v(a.x * s, a.y * s, a.z * s); }
  function dot(a, b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
  function cross(a, b) {
    return v(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
  }
  function length(a) { return Math.hypot(a.x, a.y, a.z); }
  function normalize(a) {
    const L = length(a) || 1;
    return v(a.x / L, a.y / L, a.z / L);
  }

  // Build a unit direction vector from azimuth (deg, clockwise from +Y/North)
  // and zenith angle (deg, from +Z). This matches remote-sensing convention.
  function dirFromAzZen(azDeg, zenDeg) {
    const az = azDeg * D2R, ze = zenDeg * D2R;
    return v(Math.sin(ze) * Math.sin(az), Math.sin(ze) * Math.cos(az), Math.cos(ze));
  }

  // Camera: yaw (deg, around Z, 0 = looking toward -Y / from south) and
  // pitch (deg, tilt from horizontal; 90 = top-down, 0 = horizon).
  // Returns a function p(world) → {x, y, depth} screen coords (depth for sorting).
  function makeCamera(yawDeg, pitchDeg, scalePx, cx, cy) {
    const yaw = yawDeg * D2R, pitch = pitchDeg * D2R;
    const cy_ = Math.cos(yaw),  sy = Math.sin(yaw);
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    return function project(p) {
      // Yaw around Z
      const x1 =  cy_ * p.x + sy * p.y;
      const y1 = -sy  * p.x + cy_ * p.y;
      const z1 =  p.z;
      // Pitch around X (tilt scene forward toward viewer)
      const x2 = x1;
      const y2 = cp * y1 - sp * z1;
      const z2 = sp * y1 + cp * z1;
      return { x: cx + x2 * scalePx, y: cy - z2 * scalePx, depth: y2 };
    };
  }

  // Compute angles (deg) given sun & sensor unit vectors and target altitude.
  function computeAngles(sunDir, sensorDir) {
    // Solar zenith θs, azimuth φs (from north, cw)
    const thetaS = Math.acos(Math.max(-1, Math.min(1, sunDir.z))) * R2D;
    const phiS = (Math.atan2(sunDir.x, sunDir.y) * R2D + 360) % 360;
    // View zenith θv, azimuth φv
    const thetaV = Math.acos(Math.max(-1, Math.min(1, sensorDir.z))) * R2D;
    const phiV = (Math.atan2(sensorDir.x, sensorDir.y) * R2D + 360) % 360;
    // Relative azimuth (sensor relative to sun, [0,180])
    let dphi = Math.abs(phiV - phiS); if (dphi > 180) dphi = 360 - dphi;
    // Phase angle g = arccos(cos θs cos θv + sin θs sin θv cos Δφ)
    const cs = Math.cos(thetaS * D2R), cv = Math.cos(thetaV * D2R);
    const ss = Math.sin(thetaS * D2R), sv = Math.sin(thetaV * D2R);
    const phase = Math.acos(Math.max(-1, Math.min(1, cs * cv + ss * sv * Math.cos(dphi * D2R)))) * R2D;
    // Scattering angle = 180 - phase
    const scatter = 180 - phase;
    return { thetaS, phiS, thetaV, phiV, dphi, phase, scatter };
  }

  // Build a circular arc in 3D between two unit vectors centered at origin,
  // sampled at N points. Used for angle annotations.
  function arcBetween(dirA, dirB, radius, n = 24) {
    const a = normalize(dirA), b = normalize(dirB);
    const cosT = Math.max(-1, Math.min(1, dot(a, b)));
    const theta = Math.acos(cosT);
    const sinT = Math.sin(theta) || 1;
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const s1 = Math.sin((1 - t) * theta) / sinT;
      const s2 = Math.sin(t * theta) / sinT;
      pts.push(scale(add(scale(a, s1), scale(b, s2)), radius));
    }
    return pts;
  }

  window.Geom = {
    v, add, sub, scale, dot, cross, length, normalize,
    dirFromAzZen, makeCamera, computeAngles, arcBetween,
    D2R, R2D,
  };
})();
