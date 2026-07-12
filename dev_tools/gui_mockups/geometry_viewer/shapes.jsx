// shapes.jsx — schematic line-art renderers for each target geometry.
// Each builds a list of 3D edges (pairs of points) which the scene projects.
// "Schematic" = wireframes only, no fills, no shading. Communicates "not to scale".

(function () {
  const { v } = window.Geom;

  // ── Edge primitives ────────────────────────────────────────────────────────
  function rect(cx, cy, cz, w, h) {
    const x0 = cx - w / 2, x1 = cx + w / 2;
    const y0 = cy - h / 2, y1 = cy + h / 2;
    return [
      [v(x0, y0, cz), v(x1, y0, cz)], [v(x1, y0, cz), v(x1, y1, cz)],
      [v(x1, y1, cz), v(x0, y1, cz)], [v(x0, y1, cz), v(x0, y0, cz)],
    ];
  }

  function box(cx, cy, cz, w, d, h) {
    const x0 = cx - w / 2, x1 = cx + w / 2;
    const y0 = cy - d / 2, y1 = cy + d / 2;
    const z0 = cz, z1 = cz + h;
    const c = [
      v(x0, y0, z0), v(x1, y0, z0), v(x1, y1, z0), v(x0, y1, z0),
      v(x0, y0, z1), v(x1, y0, z1), v(x1, y1, z1), v(x0, y1, z1),
    ];
    return [
      [c[0], c[1]], [c[1], c[2]], [c[2], c[3]], [c[3], c[0]],
      [c[4], c[5]], [c[5], c[6]], [c[6], c[7]], [c[7], c[4]],
      [c[0], c[4]], [c[1], c[5]], [c[2], c[6]], [c[3], c[7]],
    ];
  }

  function circle(cx, cy, cz, r, n = 32, axis = 'z') {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const t = (i / n) * Math.PI * 2;
      if (axis === 'z') pts.push(v(cx + r * Math.cos(t), cy + r * Math.sin(t), cz));
      else if (axis === 'y') pts.push(v(cx + r * Math.cos(t), cy, cz + r * Math.sin(t)));
      else pts.push(v(cx, cy + r * Math.cos(t), cz + r * Math.sin(t)));
    }
    const out = [];
    for (let i = 0; i < n; i++) out.push([pts[i], pts[(i + 1) % n]]);
    return out;
  }

  function sphere(cx, cy, cz, r) {
    // Three great circles for a clean schematic look.
    return [
      ...circle(cx, cy, cz, r, 32, 'z'),
      ...circle(cx, cy, cz, r, 32, 'y'),
      ...circle(cx, cy, cz, r, 32, 'x'),
    ];
  }

  function cylinder(cx, cy, cz, r, h, n = 24) {
    const top = [], bot = [];
    for (let i = 0; i < n; i++) {
      const t = (i / n) * Math.PI * 2;
      top.push(v(cx + r * Math.cos(t), cy + r * Math.sin(t), cz + h));
      bot.push(v(cx + r * Math.cos(t), cy + r * Math.sin(t), cz));
    }
    const e = [];
    for (let i = 0; i < n; i++) {
      e.push([top[i], top[(i + 1) % n]]);
      e.push([bot[i], bot[(i + 1) % n]]);
    }
    // four vertical "silhouette" lines at cardinal points
    for (let k = 0; k < 4; k++) {
      const idx = Math.round((k / 4) * n) % n;
      e.push([bot[idx], top[idx]]);
    }
    return e;
  }

  function cone(cx, cy, cz, r, h, n = 24) {
    const base = [];
    const apex = v(cx, cy, cz + h);
    for (let i = 0; i < n; i++) {
      const t = (i / n) * Math.PI * 2;
      base.push(v(cx + r * Math.cos(t), cy + r * Math.sin(t), cz));
    }
    const e = [];
    for (let i = 0; i < n; i++) e.push([base[i], base[(i + 1) % n]]);
    // four slant lines
    for (let k = 0; k < 4; k++) {
      const idx = Math.round((k / 4) * n) % n;
      e.push([base[idx], apex]);
    }
    return e;
  }

  function ellipsoid(cx, cy, cz, rx, ry, rz) {
    // Three ellipses on principal planes.
    const e = [];
    const n = 32;
    // XY (top)
    for (let i = 0; i < n; i++) {
      const t1 = (i / n) * Math.PI * 2, t2 = ((i + 1) / n) * Math.PI * 2;
      e.push([
        v(cx + rx * Math.cos(t1), cy + ry * Math.sin(t1), cz),
        v(cx + rx * Math.cos(t2), cy + ry * Math.sin(t2), cz),
      ]);
    }
    // XZ
    for (let i = 0; i < n; i++) {
      const t1 = (i / n) * Math.PI * 2, t2 = ((i + 1) / n) * Math.PI * 2;
      e.push([
        v(cx + rx * Math.cos(t1), cy, cz + rz * Math.sin(t1)),
        v(cx + rx * Math.cos(t2), cy, cz + rz * Math.sin(t2)),
      ]);
    }
    // YZ
    for (let i = 0; i < n; i++) {
      const t1 = (i / n) * Math.PI * 2, t2 = ((i + 1) / n) * Math.PI * 2;
      e.push([
        v(cx, cy + ry * Math.cos(t1), cz + rz * Math.sin(t1)),
        v(cx, cy + ry * Math.cos(t2), cz + rz * Math.sin(t2)),
      ]);
    }
    return e;
  }

  function plate(cx, cy, cz, w, d) {
    // A thin rectangle, drawn as outline + diagonals (clearly a panel)
    const x0 = cx - w / 2, x1 = cx + w / 2;
    const y0 = cy - d / 2, y1 = cy + d / 2;
    return [
      [v(x0, y0, cz), v(x1, y0, cz)], [v(x1, y0, cz), v(x1, y1, cz)],
      [v(x1, y1, cz), v(x0, y1, cz)], [v(x0, y1, cz), v(x0, y0, cz)],
    ];
  }

  function customMesh(cx, cy, cz, s) {
    // Stand-in: an octahedron, signaling "user-imported mesh"
    const a = s, b = s * 0.7;
    const top = v(cx, cy, cz + a);
    const bot = v(cx, cy, cz - 0); // sits on ground
    const ring = [
      v(cx + b, cy, cz + a / 2), v(cx, cy + b, cz + a / 2),
      v(cx - b, cy, cz + a / 2), v(cx, cy - b, cz + a / 2),
    ];
    const e = [];
    for (let i = 0; i < 4; i++) {
      e.push([ring[i], ring[(i + 1) % 4]]);
      e.push([ring[i], top]);
      e.push([ring[i], bot]);
    }
    return e;
  }

  // Returns { edges, footprintRadius } where footprintRadius is used for the
  // ground "shadow" / projected footprint when target is airborne.
  function buildTarget(shape, dims, altitude) {
    const cz = altitude;
    switch (shape) {
      case 'extended': {
        const w = dims.w ?? 4, d = dims.d ?? 3;
        return { edges: rect(0, 0, cz, w, d), footprint: Math.max(w, d) / 2, label: { x: 0, y: 0, z: cz } };
      }
      case 'plate': {
        const w = dims.w ?? 1.6, d = dims.d ?? 1.0;
        return { edges: plate(0, 0, cz, w, d), footprint: Math.max(w, d) / 2, label: { x: 0, y: 0, z: cz } };
      }
      case 'box': {
        const w = dims.w ?? 1.4, d = dims.d ?? 1.0, h = dims.h ?? 0.7;
        return { edges: box(0, 0, cz, w, d, h), footprint: Math.max(w, d) / 2, label: { x: 0, y: 0, z: cz + h } };
      }
      case 'sphere': {
        const r = dims.r ?? 0.6;
        return { edges: sphere(0, 0, cz + r, r), footprint: r, label: { x: 0, y: 0, z: cz + 2 * r } };
      }
      case 'cylinder': {
        const r = dims.r ?? 0.55, h = dims.h ?? 1.1;
        return { edges: cylinder(0, 0, cz, r, h), footprint: r, label: { x: 0, y: 0, z: cz + h } };
      }
      case 'cone': {
        const r = dims.r ?? 0.7, h = dims.h ?? 1.2;
        return { edges: cone(0, 0, cz, r, h), footprint: r, label: { x: 0, y: 0, z: cz + h } };
      }
      case 'circle': {
        const r = dims.r ?? 0.9;
        return { edges: circle(0, 0, cz, r), footprint: r, label: { x: 0, y: 0, z: cz } };
      }
      case 'ellipsoid': {
        const rx = dims.rx ?? 0.8, ry = dims.ry ?? 0.55, rz = dims.rz ?? 0.6;
        return { edges: ellipsoid(0, 0, cz + rz, rx, ry, rz), footprint: Math.max(rx, ry), label: { x: 0, y: 0, z: cz + 2 * rz } };
      }
      case 'point': {
        return { edges: [], footprint: 0.05, label: { x: 0, y: 0, z: cz }, isPoint: true };
      }
      case 'mesh':
      default: {
        const s = dims.s ?? 0.7;
        return { edges: customMesh(0, 0, cz, s), footprint: s * 0.8, label: { x: 0, y: 0, z: cz + s } };
      }
    }
  }

  // Sensor body geometries (3 representations)
  function buildSensor(kind, pos, size = 0.35) {
    const cx = pos.x, cy = pos.y, cz = pos.z;
    if (kind === 'marker') {
      // Crosshair-style marker (small lines through point)
      const s = size * 0.6;
      return [
        [v(cx - s, cy, cz), v(cx + s, cy, cz)],
        [v(cx, cy - s, cz), v(cx, cy + s, cz)],
        [v(cx, cy, cz - s), v(cx, cy, cz + s)],
      ];
    }
    if (kind === 'cube') return box(cx, cy, cz - size / 2, size, size, size);
    if (kind === 'satellite') {
      // Schematic satellite: bus (small box) + two solar-panel wings + nadir aperture cone.
      const bw = size * 0.55, bh = size * 0.55, bd = size * 0.45;
      const bus = box(cx - bw/2, cy - bh/2, cz - bd/2, bw, bh, bd);
      // Solar wings extend along ±X
      const wingSpanY = size * 0.28, wingSpanZ = size * 0.18;
      const wingInner = bw/2, wingOuter = bw/2 + size * 1.05;
      const wingY0 = cy - wingSpanY/2, wingY1 = cy + wingSpanY/2;
      const wingZ0 = cz - wingSpanZ/2, wingZ1 = cz + wingSpanZ/2;
      const wing = (xi, xo) => {
        const c000 = v(xi, wingY0, wingZ0), c100 = v(xo, wingY0, wingZ0);
        const c110 = v(xo, wingY1, wingZ0), c010 = v(xi, wingY1, wingZ0);
        const c001 = v(xi, wingY0, wingZ1), c101 = v(xo, wingY0, wingZ1);
        const c111 = v(xo, wingY1, wingZ1), c011 = v(xi, wingY1, wingZ1);
        // outline (rectangle on Z=mid for each face's perimeter — simplify to top + bottom + sides)
        const lines = [
          [c000, c100], [c100, c110], [c110, c010], [c010, c000],
          [c001, c101], [c101, c111], [c111, c011], [c011, c001],
          [c000, c001], [c100, c101], [c110, c111], [c010, c011],
        ];
        // panel cell divisions (3 along length)
        for (let k = 1; k < 3; k++) {
          const xk = xi + (xo - xi) * (k / 3);
          lines.push([v(xk, wingY0, wingZ0), v(xk, wingY1, wingZ0)]);
          lines.push([v(xk, wingY0, wingZ1), v(xk, wingY1, wingZ1)]);
        }
        return lines;
      };
      const wL = wing(cx - wingInner, cx - wingOuter);
      const wR = wing(cx + wingInner, cx + wingOuter);
      // Nadir aperture: short cone hanging below the bus, apex at sensor base
      const apertureR = size * 0.22;
      const apertureH = size * 0.28;
      const aperApex = v(cx, cy, cz - bd/2);
      const aperBase = v(cx, cy, cz - bd/2 - apertureH);
      const N = 16, ring = [];
      for (let i = 0; i < N; i++) {
        const t = (i / N) * Math.PI * 2;
        ring.push(v(cx + apertureR * Math.cos(t), cy + apertureR * Math.sin(t), cz - bd/2 - apertureH));
      }
      const aper = [];
      for (let i = 0; i < N; i++) aper.push([ring[i], ring[(i+1) % N]]);
      // 4 generator lines from apex down to ring
      for (let k = 0; k < 4; k++) {
        const idx = Math.round((k / 4) * N) % N;
        aper.push([aperApex, ring[idx]]);
      }
      return [...bus, ...wL, ...wR, ...aper];
    }
    if (kind === 'fov') {
      // small cube + downward FOV cone (apex at sensor, base on ground)
      const cube = box(cx, cy, cz - size / 4, size * 0.6, size * 0.6, size * 0.5);
      const apex = v(cx, cy, cz - size / 4);
      const baseR = cz * Math.tan(15 * Math.PI / 180); // 15° half-angle
      const baseZ = 0;
      const baseN = 24, base = [];
      for (let i = 0; i < baseN; i++) {
        const t = (i / baseN) * Math.PI * 2;
        base.push(v(cx + baseR * Math.cos(t), cy + baseR * Math.sin(t), baseZ));
      }
      const fov = [];
      for (let i = 0; i < baseN; i++) fov.push([base[i], base[(i + 1) % baseN]]);
      for (let k = 0; k < 4; k++) {
        const idx = Math.round((k / 4) * baseN) % baseN;
        fov.push([base[idx], apex]);
      }
      return [...cube, ...fov];
    }
    return [];
  }

  window.Shapes = { buildTarget, buildSensor };
})();
