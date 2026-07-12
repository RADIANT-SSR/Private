// scene.jsx — the SVG-based 3D schematic scene.
// Renders ground, target, sensor, vectors, angle annotations, and reacts to
// click events to surface labeled angles.

const { useState, useRef, useEffect, useMemo } = React;
const { v, scale, add, sub, normalize, dirFromAzZen, makeCamera, computeAngles, arcBetween, length, dot, cross } = window.Geom;
const { buildTarget, buildSensor } = window.Shapes;

const PALETTES = {
  dark: {
    bg: '#0b0d12',
    grid: '#1f2530',
    gridMajor: '#2a3242',
    ink: '#e8ecf2',
    inkDim: '#8892a3',
    zenith: '#cfd6e1',
    sun: '#f5b942',
    sensor: '#6ad1ff',
    proj: '#f5b942',
    phi: '#e667c8',
    alt: '#a3aebd',
    hot: '#ffffff',
  },
  light: {
    bg: '#f5f3ec',
    grid: '#d8d4c5',
    gridMajor: '#9a958a',
    ink: '#161616',
    inkDim: '#6b6457',
    zenith: '#3a3a3a',
    sun: '#c97a17',     // deeper amber for contrast on cream
    sensor: '#0d6e9c',  // deeper cyan/teal
    proj: '#c97a17',
    phi: '#a8358c',     // deeper magenta
    alt: '#5a5346',
    hot: '#000000',
  },
};

// ─────────────────────────────────────────────────────────────────────────────
function Scene({
  width = 720, height = 540,
  yaw, pitch,
  sunAz, sunZen,
  senAz, senZen, senAlt,
  target, tgtRealAlt, // { shape, dims, altitude } + display altitude in km
  sensorKind, groundKind,
  theme = 'dark',
  selected, setSelected,
}) {
  const C = PALETTES[theme] || PALETTES.dark;
  const cx = width / 2, cy = height * 0.78;
  // Auto-fit: the schematic spans ~5 units across; pick scale to fill the canvas.
  const SCENE_SCALE = Math.max(80, Math.min(width / 7.5, height / 5.6));

  const cam = makeCamera(yaw, pitch, SCENE_SCALE, cx, cy);

  const sunDir = dirFromAzZen(sunAz, sunZen);
  const senDir = dirFromAzZen(senAz, senZen);
  const angles = computeAngles(sunDir, senDir);

  // Target at origin (XY=0, Z=altitude). World units: ~1 = abstract scene unit.
  const tgt = buildTarget(target.shape, target.dims, target.altitude);
  const tLabel = tgt.label;

  // Apply Roll/Pitch/Yaw to the target body (3D shapes only). Intrinsic ZYX
  // Tait–Bryan: yaw about world Z, then pitch about new Y, then roll about new X.
  // Rotation pivot = target's geometric center along Z (between base and label).
  const rotatedTgt = (() => {
    if (!target.is3D || (target.roll === 0 && target.pitch === 0 && target.yaw === 0)) {
      return tgt;
    }
    const cR = Math.cos(target.roll  * Math.PI/180), sR = Math.sin(target.roll  * Math.PI/180);
    const cP = Math.cos(target.pitch * Math.PI/180), sP = Math.sin(target.pitch * Math.PI/180);
    const cY = Math.cos(target.yaw   * Math.PI/180), sY = Math.sin(target.yaw   * Math.PI/180);
    // M = Rz(yaw) * Ry(pitch) * Rx(roll). Rows used to multiply column vector.
    const m00 = cY*cP, m01 = cY*sP*sR - sY*cR, m02 = cY*sP*cR + sY*sR;
    const m10 = sY*cP, m11 = sY*sP*sR + cY*cR, m12 = sY*sP*cR - cY*sR;
    const m20 = -sP,   m21 = cP*sR,            m22 = cP*cR;
    const pivotZ = (target.altitude + tLabel.z) * 0.5;
    const rot = (p) => {
      const x = p.x, y = p.y, z = p.z - pivotZ;
      return v(m00*x + m01*y + m02*z, m10*x + m11*y + m12*z, m20*x + m21*y + m22*z + pivotZ);
    };
    return {
      ...tgt,
      edges: tgt.edges.map(e => {
        // edges are stored as either [a, b] tuples (most shapes) or {a, b} objects.
        const a = Array.isArray(e) ? e[0] : e.a;
        const b = Array.isArray(e) ? e[1] : e.b;
        return Array.isArray(e) ? [rot(a), rot(b)] : { a: rot(a), b: rot(b) };
      }),
    };
  })();

  // Sensor position at finite distance (schematic, not to scale):
  // Place along sensor direction at radius = senAlt-mapped value
  const sensorDist = 3.5;
  const sensorPos = scale(senDir, sensorDist);
  // Bring sensor "down" to suggest altitude rather than infinite distance
  // (we draw a vertical altitude tick from its sub-point)

  // Sun is far away — a marker at radius 4.5 along sunDir
  const sunDist = 4.5;
  const sunPos = scale(sunDir, sunDist);

  // Ground illumination point: where the sensor's boresight, extended past
  // the target, intersects the ground plane (z=0). This is the ground patch
  // the sensor is actually looking at — and therefore the point that must be
  // illuminated by the sun for there to be signal. Both the sun→ground line
  // and the sensor's continued line-of-sight terminate at this shared point.
  const targetWorld = v(0, 0, target.altitude);
  let groundPt = v(0, 0, 0);
  if (target.altitude > 0) {
    const dz = sensorPos.z - targetWorld.z; // = sensorPos.z - h
    if (Math.abs(dz) > 1e-6) {
      const t = sensorPos.z / dz;
      groundPt = v(
        sensorPos.x + t * (targetWorld.x - sensorPos.x),
        sensorPos.y + t * (targetWorld.y - sensorPos.y),
        0
      );
    }
  }

  // ── Ground grid ─────────────────────────────────────────────────────────────
  const groundEdges = [];
  if (groundKind === 'flat') {
    const N = 8, step = 0.8;
    for (let i = -N; i <= N; i++) {
      groundEdges.push([v(-N * step, i * step, 0), v(N * step, i * step, 0)]);
      groundEdges.push([v(i * step, -N * step, 0), v(i * step, N * step, 0)]);
    }
  } else {
    // Curved Earth section: arcs in two perpendicular planes
    const R = 14; // big radius (schematic curvature)
    const ang = 0.45; // half-angle covered
    const N = 32;
    // East-West arc
    for (let i = 0; i < N; i++) {
      const t1 = -ang + (i / N) * 2 * ang, t2 = -ang + ((i + 1) / N) * 2 * ang;
      groundEdges.push([
        v(R * Math.sin(t1), 0, R * Math.cos(t1) - R),
        v(R * Math.sin(t2), 0, R * Math.cos(t2) - R),
      ]);
    }
    // North-South arc
    for (let i = 0; i < N; i++) {
      const t1 = -ang + (i / N) * 2 * ang, t2 = -ang + ((i + 1) / N) * 2 * ang;
      groundEdges.push([
        v(0, R * Math.sin(t1), R * Math.cos(t1) - R),
        v(0, R * Math.sin(t2), R * Math.cos(t2) - R),
      ]);
    }
    // Faint cross-grid
    for (let k = -3; k <= 3; k++) if (k !== 0) {
      for (let i = 0; i < N; i++) {
        const t1 = -ang + (i / N) * 2 * ang, t2 = -ang + ((i + 1) / N) * 2 * ang;
        groundEdges.push([
          v(k * 0.8, R * Math.sin(t1) * 0.55, (R * Math.cos(t1) - R) * 0.55),
          v(k * 0.8, R * Math.sin(t2) * 0.55, (R * Math.cos(t2) - R) * 0.55),
        ]);
      }
    }
  }

  // Projected-area card removed at user request — radiometric A_proj will live
  // in a different panel (likely the right-side Numerics readout) when needed.

  // Sensor body removed — sensor is now drawn as a simple marker (see Sun marker
  // for the visual idiom). Keeps the scene focused on scenario geometry.

  // ── Cartesian axes anchored at the target's ground sub-point (0,0,0).
  //   +Z (zenith) runs from the ground origin straight up past the target's top
  //   (where the sun/sensor vectors terminate and where elevation arcs anchor).
  const zenithLine = [v(0, 0, 0), v(0, 0, tgt.label.z + 2.2)];

  // ── Project everything ─────────────────────────────────────────────────────
  const P = (p) => cam(p);

  const projectEdges = (edges) => edges.map(([a, b]) => ({ a: P(a), b: P(b) }));

  // Helper: SVG line element
  const Line = ({ a, b, stroke, sw = 1, dash, opacity = 1, onClick, hover, role, id }) => (
    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
      stroke={stroke} strokeWidth={sw} strokeDasharray={dash}
      strokeLinecap="round" opacity={opacity}
      onClick={onClick}
      style={onClick ? { cursor: 'default' } : null}
      data-role={role} data-id={id} />
  );

  // Vector with arrowhead
  const Vector = ({ from, to, stroke, sw = 2, dash, glow = false, onClick, isSelected, label, labelOffset = 8 }) => {
    const a = P(from), b = P(to);
    const dx = b.x - a.x, dy = b.y - a.y;
    const L = Math.hypot(dx, dy) || 1;
    const ux = dx / L, uy = dy / L;
    const nx = -uy, ny = ux;
    const head = 9;
    const tip = b;
    const base = { x: b.x - ux * head, y: b.y - uy * head };
    const left = { x: base.x + nx * head * 0.45, y: base.y + ny * head * 0.45 };
    const right = { x: base.x - nx * head * 0.45, y: base.y - ny * head * 0.45 };
    const filter = glow || isSelected ? `drop-shadow(0 0 6px ${stroke})` : null;
    return (
      <g style={{ filter, cursor: onClick ? 'default' : null }} onClick={onClick}>
        {/* hit area */}
        {onClick && (
          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke="transparent" strokeWidth={14} />
        )}
        <line x1={a.x} y1={a.y} x2={b.x} y2={b.y}
          stroke={stroke} strokeWidth={isSelected ? sw + 0.8 : sw}
          strokeDasharray={dash} strokeLinecap="round" />
        <polygon points={`${tip.x},${tip.y} ${left.x},${left.y} ${right.x},${right.y}`}
          fill={stroke} />
      </g>
    );
  };

  // Angle arc + label between two world-space directions, anchored at target
  const AngleArc = ({ dirA, dirB, radius, color, label, value, faded = false }) => {
    const pts = arcBetween(dirA, dirB, radius);
    // Anchor at the TOP of the target body — same point the sun/sensor vectors
    // terminate at. The Z axis runs through this point so the arc starts on it.
    const shifted = pts.map((p) => add(p, v(tLabel.x, tLabel.y, tLabel.z)));
    const proj = shifted.map(P);
    const d = proj.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    // Label at midpoint
    const midWorld = add(shifted[Math.floor(shifted.length / 2)], v(0, 0, 0));
    const mid = P(midWorld);
    return (
      <g opacity={faded ? 0.35 : 1}>
        <path d={d} fill="none" stroke={color} strokeWidth={0.9}
          strokeLinecap="round" strokeDasharray="3 3" opacity={0.85} />
        <g transform={`translate(${mid.x + 6}, ${mid.y - 4})`}>
          <rect x={-2} y={-10} width={labelWidth(label, value)} height={14} rx={3}
            fill={C.bg} stroke={color} strokeWidth={0.5} opacity={0.95} />
          <text x={2} y={0} fontFamily="JetBrains Mono, ui-monospace, monospace"
            fontSize={10} fill={color}>
            {label} {value.toFixed(1)}°
          </text>
        </g>
      </g>
    );
  };

  function labelWidth(lbl, val) {
    const s = `${lbl} ${val.toFixed(1)}°`;
    return Math.max(48, s.length * 6.6);
  }

  // Project ground projection edges so we can draw with z-order (ground first)
  const groundLines = projectEdges(groundEdges);
  const targetLines = projectEdges(rotatedTgt.edges);

  // Sort ground by depth (further first) for subtle gradient feel
  groundLines.sort((a, b) => Math.max(a.a.depth, a.b.depth) - Math.max(b.a.depth, b.b.depth));

  // Altitude tick line (target → ground sub-point) when target is airborne
  const altLine = target.altitude > 0
    ? { a: P(v(0, 0, 0)), b: P(v(0, 0, target.altitude)) } : null;
  // Sensor altitude tick (sub-sensor → sensor)
  const senSubPoint = v(sensorPos.x, sensorPos.y, 0);
  const senAltLine = { a: P(senSubPoint), b: P(sensorPos) };

  // Vectors terminate at the TOP of the target body so they visually land on it.
  const sunFrom = sunPos;
  const sunTo = v(tLabel.x, tLabel.y, tLabel.z);
  const senFrom = sensorPos;
  const senTo = v(tLabel.x, tLabel.y, tLabel.z);

  const showSel = (id) => selected === id;

  // Sun-to-ground reference line: from the sun, terminating at the ground
  // illumination point (where the sensor boresight intersects the earth).
  const sunGroundFrom = sunPos;
  const sunGroundTo = groundPt;
  // Sensor boresight continuation: from the target down to the same ground
  // illumination point, drawn faintly to make the shared termination obvious.
  const senExtFrom = targetWorld;
  const senExtTo = groundPt;

  return (
    <svg width={width} height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ background: C.bg, display: 'block', userSelect: 'none' }}
      onClick={(e) => { if (e.target === e.currentTarget) setSelected(null); }}>

      <defs>
        <radialGradient id="vignette" cx="50%" cy="55%" r="70%">
          <stop offset="60%" stopColor={C.bg} stopOpacity="0" />
          <stop offset="100%" stopColor={theme === 'light' ? '#000' : '#000'} stopOpacity={theme === 'light' ? 0.08 : 0.6} />
        </radialGradient>
        <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-30)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="#1a2030" strokeWidth="1" />
        </pattern>
      </defs>

      {/* Ground grid */}
      <g opacity={0.55}>
        {groundLines.map((l, i) => (
          <Line key={`g${i}`} a={l.a} b={l.b} stroke={C.grid} sw={0.6} />
        ))}
      </g>

      {/* Cartesian axes (X, Y, Z) at the target's ground sub-point.
          All three axes share the same line weight. */}
      <Vector from={v(0, 0, 0)} to={v(2.4, 0, 0)} stroke={C.gridMajor} sw={1.0} />
      <Line a={P(v(0, 0, 0))} b={P(v(-2.4, 0, 0))} stroke={C.gridMajor} sw={1.0} dash="2 4" opacity={0.5} />
      <Vector from={v(0, 0, 0)} to={v(0, 2.4, 0)} stroke={C.gridMajor} sw={1.0} />
      <Line a={P(v(0, 0, 0))} b={P(v(0, -2.4, 0))} stroke={C.gridMajor} sw={1.0} dash="2 4" opacity={0.5} />
      {(() => {
        const px = P(v(2.65, 0, 0));
        const py = P(v(0, 2.65, 0));
        return (
          <g fontFamily="JetBrains Mono, ui-monospace, monospace" fontSize={12}>
            <text x={px.x} y={px.y + 4} fill={C.inkDim} textAnchor="middle">X</text>
            <text x={py.x} y={py.y + 4} fill={C.inkDim} textAnchor="middle">Y</text>
          </g>
        );
      })()}
      {/* φ=0° reference tick removed — the φ arcs themselves indicate
          where azimuth measurement begins, and the bare tick was confusing
          users into thinking it was a small angle annotation. */}

      {/* Projected-area card removed. */}

      {/* Altitude tick (target -> ground) */}
      {altLine && (
        <Line a={altLine.a} b={altLine.b} stroke={C.alt}
          sw={showSel('target') ? 1.4 : 0.9}
          dash="2 3"
          opacity={showSel('target') ? 1 : 0.85} />
      )}
      {/* Sensor altitude tick */}
      <Line a={senAltLine.a} b={senAltLine.b} stroke={C.alt}
        sw={showSel('sensor') ? 1.4 : 0.9}
        dash="2 3"
        opacity={showSel('sensor') ? 1 : 0.65} />

      {/* Altitude readout callouts — visible when target / sensor selected */}
      {showSel('target') && altLine && (() => {
        const mx = (altLine.a.x + altLine.b.x) / 2;
        const my = (altLine.a.y + altLine.b.y) / 2;
        const txt = `h_t  ${tgtRealAlt.toFixed(2)} km`;
        const w = txt.length * 6.6 + 10;
        return (
          <g transform={`translate(${mx + 8}, ${my})`}>
            <rect x={0} y={-9} width={w} height={14} rx={3}
              fill={C.bg} stroke={C.alt} strokeWidth={0.5} opacity={0.95} />
            <text x={5} y={1} fontFamily="JetBrains Mono, ui-monospace, monospace"
              fontSize={10} fill={C.alt}>{txt}</text>
          </g>
        );
      })()}
      {showSel('sensor') && (() => {
        const mx = (senAltLine.a.x + senAltLine.b.x) / 2;
        const my = (senAltLine.a.y + senAltLine.b.y) / 2;
        const txt = `h_s  ${senAlt} km`;
        const w = txt.length * 6.6 + 10;
        return (
          <g transform={`translate(${mx + 8}, ${my})`}>
            <rect x={0} y={-9} width={w} height={14} rx={3}
              fill={C.bg} stroke={C.alt} strokeWidth={0.5} opacity={0.95} />
            <text x={5} y={1} fontFamily="JetBrains Mono, ui-monospace, monospace"
              fontSize={10} fill={C.alt}>{txt}</text>
          </g>
        );
      })()}

      {/* Sensor boresight continuation: target → ground illumination point.
          Clickable so the user can pull up the ground-frame view geometry
          (θᵥ_g, φᵥ_g) at the actual ground patch the sensor samples. */}
      {target.altitude > 0 && (
        <Vector from={senExtFrom} to={senExtTo} stroke={C.sensor}
          sw={showSel('losExt') ? 1.6 : 1} dash="2 3"
          opacity={showSel('losExt') ? 1 : 0.55}
          onClick={() => setSelected('losExt')} isSelected={showSel('losExt')} />
      )}
      {/* Sun → ground reference line (amber dashed). Terminates at the
          ground illumination point — where the sensor is actually looking. */}
      {target.altitude > 0 && (
        <Vector from={sunGroundFrom} to={sunGroundTo} stroke={C.proj} sw={1.4} dash="4 3"
          onClick={() => setSelected('shadow')} isSelected={showSel('shadow')} />
      )}
      {/* Ground illumination point marker */}
      {target.altitude > 0 && (() => {
        const gp = P(groundPt);
        return (
          <g>
            <circle cx={gp.x} cy={gp.y} r={3} fill="none" stroke={C.proj} strokeWidth={1} />
            <circle cx={gp.x} cy={gp.y} r={1.5} fill={C.proj} />
          </g>
        );
      })()}

      {/* +Z (Zenith) axis: solid line from ground origin up through the target.
          All angle origins (θₛ, θᵥ) attach to this axis. */}
      <Vector from={zenithLine[0]} to={zenithLine[1]} stroke={C.gridMajor} sw={1.0}
        onClick={() => setSelected('zenith')} isSelected={showSel('zenith')} />
      <Line a={P(v(0,0,0))} b={P(v(0,0,-1.4))} stroke={C.gridMajor} sw={1.0} dash="2 4" opacity={0.5} />
      {(() => {
        const p = P(zenithLine[1]);
        return <text x={p.x} y={p.y - 8} fill={C.inkDim} fontSize={12}
          fontFamily="JetBrains Mono, ui-monospace, monospace" textAnchor="middle">Z</text>;
      })()}

      {/* Target body */}
      <g style={{ cursor: 'pointer' }}
         onClick={(e) => { e.stopPropagation(); setSelected('target'); }}>
        {/* Hit-area: invisible padded rect around the bounding box of target lines */}
        {(() => {
          if (!targetLines.length) return null;
          const xs = targetLines.flatMap(l => [l.a.x, l.b.x]);
          const ys = targetLines.flatMap(l => [l.a.y, l.b.y]);
          const x0 = Math.min(...xs) - 8, x1 = Math.max(...xs) + 8;
          const y0 = Math.min(...ys) - 8, y1 = Math.max(...ys) + 8;
          return <rect x={x0} y={y0} width={x1-x0} height={y1-y0} fill="transparent" />;
        })()}
        {targetLines.map((l, i) => (
          <Line key={`t${i}`} a={l.a} b={l.b}
            stroke={showSel('target') ? C.sun : C.ink}
            sw={showSel('target') ? 1.6 : 1.1} />
        ))}
        {/* Point source: small reticle */}
        {tgt.isPoint && (() => {
          const p = P(v(0, 0, target.altitude));
          return (
            <g>
              <circle cx={p.x} cy={p.y} r={3} fill={C.ink} />
              <circle cx={p.x} cy={p.y} r={8} fill="none" stroke={C.ink} strokeWidth={0.7} />
              <circle cx={p.x} cy={p.y} r={14} fill="none" stroke={C.ink} strokeWidth={0.5} opacity={0.6} />
            </g>
          );
        })()}
      </g>

      {/* Body-frame coordinate system (Roll/Pitch/Yaw)
          Visible only when target is selected AND it's a 3D shape.
          Intrinsic ZYX Tait–Bryan: yaw about world Z, then pitch about new Y,
          then roll about new X. The triad is anchored at the target's geometric
          center (tLabel for label-anchor; close enough for schematic). */}
      {showSel('target') && target.is3D && (() => {
        const cR = Math.cos(target.roll  * Math.PI/180),  sR = Math.sin(target.roll  * Math.PI/180);
        const cP = Math.cos(target.pitch * Math.PI/180),  sP = Math.sin(target.pitch * Math.PI/180);
        const cY = Math.cos(target.yaw   * Math.PI/180),  sY = Math.sin(target.yaw   * Math.PI/180);
        // Rz(yaw) * Ry(pitch) * Rx(roll) — column vectors give body axes in world.
        const X = v(cY*cP,           sY*cP,         -sP);
        const Y = v(cY*sP*sR - sY*cR, sY*sP*sR + cY*cR, cP*sR);
        const Z = v(cY*sP*cR + sY*sR, sY*sP*cR - cY*sR, cP*cR);
        const center = v(tLabel.x, tLabel.y, target.altitude + (tLabel.z - target.altitude) * 0.5);
        const L = 0.85; // axis length in world units
        const axes = [
          { d: X, color: '#ff6b8a', name: 'X′', sub: `Roll ${target.roll.toFixed(0)}°` },
          { d: Y, color: '#7bd389', name: 'Y′', sub: `Pitch ${target.pitch.toFixed(0)}°` },
          { d: Z, color: '#a78bfa', name: 'Z′', sub: `Yaw ${target.yaw.toFixed(0)}°` },
        ];
        return (
          <g style={{ pointerEvents: 'none' }}>
            {/* Faint origin reticle */}
            {(() => { const p = P(center); return (
              <circle cx={p.x} cy={p.y} r={2.5} fill="#fff" opacity={0.9} />
            ); })()}
            {axes.map((ax, i) => {
              const tip = add(center, scale(ax.d, L));
              return (
                <Vector key={i} from={center} to={tip} stroke={ax.color} sw={1.8}
                  glow label={`${ax.name}  ${ax.sub}`} labelOffset={6} />
              );
            })}
          </g>
        );
      })()}

      {/* Sensor marker — minimal disc with tick rays, mirroring the sun's
          visual treatment but in cool sensor color. No mesh, no FOV cone. */}
      {(() => {
        const p = P(sensorPos);
        return (
          <g style={{ filter: `drop-shadow(0 0 6px ${C.sensor}88)` }}>
            <circle cx={p.x} cy={p.y} r={5} fill={C.sensor} />
            <circle cx={p.x} cy={p.y} r={9} fill="none" stroke={C.sensor} strokeWidth={0.7} opacity={0.65} />
            {/* Four cardinal ticks instead of six — keeps it visually distinct from sun */}
            {[0, 90, 180, 270].map((a, i) => {
              const r = a * Math.PI / 180;
              return (
                <line key={i}
                  x1={p.x + Math.cos(r) * 10} y1={p.y + Math.sin(r) * 10}
                  x2={p.x + Math.cos(r) * 14} y2={p.y + Math.sin(r) * 14}
                  stroke={C.sensor} strokeWidth={1} strokeLinecap="round" />
              );
            })}
            <text x={p.x + 18} y={p.y - 6} fill={C.sensor} fontSize={11}
              fontFamily="JetBrains Mono, ui-monospace, monospace">SENSOR</text>
          </g>
        );
      })()}

      {/* Sun marker */}
      {(() => {
        const p = P(sunPos);
        return (
          <g style={{ filter: `drop-shadow(0 0 8px ${C.sun})` }}>
            <circle cx={p.x} cy={p.y} r={6} fill={C.sun} />
            <circle cx={p.x} cy={p.y} r={11} fill="none" stroke={C.sun} strokeWidth={0.7} opacity={0.7} />
            {[0, 60, 120, 180, 240, 300].map((a, i) => {
              const r = a * Math.PI / 180;
              return (
                <line key={i}
                  x1={p.x + Math.cos(r) * 12} y1={p.y + Math.sin(r) * 12}
                  x2={p.x + Math.cos(r) * 17} y2={p.y + Math.sin(r) * 17}
                  stroke={C.sun} strokeWidth={1} strokeLinecap="round" />
              );
            })}
            <text x={p.x + 22} y={p.y - 8} fill={C.sun} fontSize={11}
              fontFamily="JetBrains Mono, ui-monospace, monospace">SUN</text>
          </g>
        );
      })()}

      {/* Sun → target ray */}
      <Vector from={sunFrom} to={sunTo} stroke={C.sun} sw={2} glow
        onClick={() => setSelected('sun')} isSelected={showSel('sun')} />

      {/* Sensor → target ray */}
      <Vector from={senFrom} to={senTo} stroke={C.sensor} sw={2} glow
        onClick={() => setSelected('sensor')} isSelected={showSel('sensor')} />

      {/* Angle annotations — visible based on `selected` */}
      {showSel('sun') && (() => {
        const subSun = v(sunPos.x, sunPos.y, 0);
        const rSun = Math.hypot(sunPos.x, sunPos.y);
        const tlW = v(tLabel.x, tLabel.y, tLabel.z);
        // Direction FROM target TO sun (not origin → sun) so the arc lands
        // exactly on the visible sun→target vector.
        const dirToSun = normalize(sub(sunPos, tlW));
        return (
          <>
            {/* θₛ: arc from +Z to sun direction (dashed annotation) */}
            <AngleArc dirA={v(0, 0, 1)} dirB={dirToSun} radius={1.0}
              color={C.sun} label="θₛ" value={angles.thetaS} />
            {/* Vertical drop from sun to its sub-point on ground (dashed) */}
            <Line a={P(sunPos)} b={P(subSun)} stroke={C.sun} sw={0.9} dash="3 3" opacity={0.65} />
            {/* Radial from origin to sub-sun (dashed) — this IS the φₛ leg */}
            <Line a={P(v(0,0,0))} b={P(subSun)} stroke={C.sun} sw={0.9} dash="3 3" opacity={0.65} />
            {/* φₛ arc on ground, dashed, radius matches the radial so it lands on it */}
            <AngleGround color={C.sun} from={0} to={angles.phiS}
              radius={Math.max(0.6, rSun * 0.5)} bg={C.bg}
              P={P} altitude={0} label="φₛ" value={angles.phiS} dashed />
          </>
        );
      })()}
      {showSel('sensor') && (() => {
        const subSen = v(sensorPos.x, sensorPos.y, 0);
        const rSen = Math.hypot(sensorPos.x, sensorPos.y);
        const tlW = v(tLabel.x, tLabel.y, tLabel.z);
        const dirToSen = normalize(sub(sensorPos, tlW));
        return (
          <>
            <AngleArc dirA={v(0, 0, 1)} dirB={dirToSen} radius={1.2}
              color={C.sensor} label="θᵥ" value={angles.thetaV} />
            <Line a={P(sensorPos)} b={P(subSen)} stroke={C.sensor} sw={0.9} dash="3 3" opacity={0.65} />
            <Line a={P(v(0,0,0))} b={P(subSen)} stroke={C.sensor} sw={0.9} dash="3 3" opacity={0.65} />
            <AngleGround color={C.sensor} from={0} to={angles.phiV}
              radius={Math.max(0.7, rSen * 0.6)} bg={C.bg}
              P={P} altitude={0} label="φᵥ" value={angles.phiV} dashed />
          </>
        );
      })()}
      {(showSel('phase') || showSel('phi')) && (() => {
        const subSun = v(sunPos.x, sunPos.y, 0);
        const subSen = v(sensorPos.x, sensorPos.y, 0);
        return (
          <>
            {/* Both radial legs (dashed), then the Δφ arc spanning between them */}
            <Line a={P(v(0,0,0))} b={P(subSun)} stroke={C.phi} sw={0.7} dash="2 3" opacity={0.55} />
            <Line a={P(v(0,0,0))} b={P(subSen)} stroke={C.phi} sw={0.7} dash="2 3" opacity={0.55} />
            <AngleGround color={C.phi}
              from={angles.phiS} to={angles.phiV} bg={C.bg}
              radius={2.0} P={P} altitude={0} label="Δφ" value={angles.dphi} dashed />
            {/* Phase angle g (3D, solid) */}
            <AngleArc dirA={normalize(sunDir)} dirB={normalize(senDir)} radius={0.85}
              color={C.phi} label="g" value={angles.phase} />
          </>
        );
      })()}

      {/* ── Ground-frame radiometric angles ────────────────────────────────
         When the user clicks the sun→ground vector ('shadow') or the sensor's
         continued LOS to the ground patch ('losExt'), draw a small secondary
         coordinate system at the ground illumination point G_i, with the
         angles re-anchored there. These are the angles RADIANT actually feeds
         into BRDF / surface-leaving radiance / atmospheric path radiance.
         The target-frame axes stay put — this just adds a faded mini-frame
         so the user can read the radiometric geometry at the surface. */}
      {(showSel('shadow') || showSel('losExt')) && target.altitude > 0 && (() => {
        const role = showSel('shadow') ? 'sun' : 'sen';
        const color = role === 'sun' ? C.sun : C.sensor;
        const dirToBody = role === 'sun'
          ? normalize(sub(sunPos, groundPt))      // upward to sun
          : normalize(sub(sensorPos, groundPt));  // upward to sensor
        const thetaDeg = role === 'sun' ? angles.thetaS : angles.thetaV;
        const phiDeg   = role === 'sun' ? angles.phiS   : angles.phiV;
        const angleLabel = role === 'sun' ? 'θₛ' : 'θᵥ';
        const phiLabel   = role === 'sun' ? 'φₛ' : 'φᵥ';
        const roleNote   = role === 'sun' ? 'incident · parallel rays' : 'emergent';
        const Z_LEN = 1.4;       // mini zenith axis length (smaller than main)
        const NORTH_LEN = 1.05;  // mini +Y' length
        const ARC_R = 0.7;
        const PHI_R = 0.9;

        // Mini Z' axis (dashed) + tiny "Z'" label
        const zTop = add(groundPt, v(0, 0, Z_LEN));
        // Mini +Y' (north) and +X' (east) ticks (very faded)
        const nTip = add(groundPt, v(0, NORTH_LEN, 0));
        const eTip = add(groundPt, v(NORTH_LEN * 0.85, 0, 0));

        // θ arc: from +Z' to direction toward sun/sensor, anchored at groundPt
        const arcPts = arcBetween(v(0, 0, 1), dirToBody, ARC_R)
          .map(p => add(p, groundPt));
        const arcD = arcPts.map(P).map((p, i) =>
          `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`
        ).join(' ');
        const arcMid = P(arcPts[Math.floor(arcPts.length / 2)]);

        // φ ground arc: from +Y' (north) to projected dir on ground, at groundPt
        const phiRad = phiDeg * Math.PI / 180;
        const N = 24;
        const phiArcPts = [];
        for (let i = 0; i <= N; i++) {
          const t = (i / N) * phiRad;
          phiArcPts.push(add(groundPt, v(PHI_R * Math.sin(t), PHI_R * Math.cos(t), 0)));
        }
        const phiArcD = phiArcPts.map(P).map((p, i) =>
          `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`
        ).join(' ');
        const phiMid = P(phiArcPts[Math.floor(phiArcPts.length / 2)]);

        // Direction-on-ground leg: from groundPt to projected dir endpoint
        const groundDir = v(dirToBody.x, dirToBody.y, 0);
        const groundDirLen = Math.hypot(groundDir.x, groundDir.y);
        const groundLeg = groundDirLen > 1e-4
          ? add(groundPt, v(PHI_R * groundDir.x / groundDirLen, PHI_R * groundDir.y / groundDirLen, 0))
          : groundPt;

        // Pixel-space helpers for label boxes
        const lbl = (txt, anchor) => {
          const w = txt.length * 6.6 + 10;
          return (
            <g transform={`translate(${anchor.x + 6}, ${anchor.y - 4})`}>
              <rect x={0} y={-9} width={w} height={14} rx={3}
                fill={C.bg} stroke={color} strokeWidth={0.5} opacity={0.95} />
              <text x={5} y={1} fontFamily="JetBrains Mono, ui-monospace, monospace"
                fontSize={10} fill={color}>{txt}</text>
            </g>
          );
        };

        return (
          <g>
            {/* Mini Z' axis at ground point */}
            <Line a={P(groundPt)} b={P(zTop)} stroke={color} sw={0.9} dash="3 3" opacity={0.85} />
            {(() => { const p = P(zTop); return (
              <text x={p.x} y={p.y - 5} fill={color} fontSize={9.5}
                fontFamily="JetBrains Mono, ui-monospace, monospace"
                textAnchor="middle">Z′</text>
            ); })()}

            {/* Mini +Y' (north) reference tick */}
            <Line a={P(groundPt)} b={P(nTip)} stroke={color} sw={0.6} dash="2 3" opacity={0.55} />
            {(() => { const p = P(nTip); return (
              <text x={p.x + 6} y={p.y + 3} fill={color} fontSize={9}
                fontFamily="JetBrains Mono, ui-monospace, monospace" opacity={0.85}>N</text>
            ); })()}

            {/* θ arc from Z' to direction-to-body */}
            <path d={arcD} fill="none" stroke={color} strokeWidth={0.9}
              strokeLinecap="round" strokeDasharray="3 3" opacity={0.9} />
            {lbl(`${angleLabel} ${thetaDeg.toFixed(1)}°`, arcMid)}

            {/* Ground-projected leg of dirToBody (so φ has a visible second arm) */}
            <Line a={P(groundPt)} b={P(groundLeg)} stroke={color} sw={0.7} dash="2 3" opacity={0.6} />

            {/* φ ground arc */}
            <path d={phiArcD} fill="none" stroke={color} strokeWidth={0.9}
              strokeLinecap="round" strokeDasharray="3 3" opacity={0.9} />
            {lbl(`${phiLabel} ${phiDeg.toFixed(1)}°`, phiMid)}

            {/* Role annotation near the ground point */}
            {(() => {
              const p = P(groundPt);
              return (
                <g transform={`translate(${p.x - 6}, ${p.y + 16})`}>
                  <text fontFamily="JetBrains Mono, ui-monospace, monospace"
                    fontSize={9} fill={color} opacity={0.85}>{roleNote}</text>
                </g>
              );
            })()}
          </g>
        );
      })()}
      <rect x={0} y={0} width={width} height={height} fill="url(#vignette)" pointerEvents="none" />

      {/* Origin marker (target label) */}
      {(() => {
        const p = P(v(tLabel.x, tLabel.y, tLabel.z));
        return (
          <g>
            <text x={p.x + 10} y={p.y + 4} fill={C.ink} fontSize={11}
              fontFamily="JetBrains Mono, ui-monospace, monospace">TARGET</text>
          </g>
        );
      })()}
    </svg>
  );
}

// Ground-plane azimuth arc (φ) — sweeps in the XY plane at z = target altitude
function AngleGround({ from, to, radius, color, label, value, P, altitude, dashed, bg = '#0b0d12' }) {
  const N = 36;
  const a0 = from * Math.PI / 180, a1 = to * Math.PI / 180;
  // Choose shorter sweep direction
  let delta = a1 - a0;
  while (delta > Math.PI) delta -= 2 * Math.PI;
  while (delta < -Math.PI) delta += 2 * Math.PI;
  const pts = [];
  for (let i = 0; i <= N; i++) {
    const t = a0 + delta * (i / N);
    pts.push(window.Geom.v(radius * Math.sin(t), radius * Math.cos(t), altitude));
  }
  const proj = pts.map(P);
  const d = proj.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const mid = proj[Math.floor(proj.length / 2)];
  const lblText = `${label} ${value.toFixed(1)}°`;
  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth={1.4} strokeLinecap="round"
        strokeDasharray={dashed ? "4 3" : null} />
      <g transform={`translate(${mid.x + 6}, ${mid.y + 12})`}>
        <rect x={-2} y={-10} width={Math.max(48, lblText.length * 6.6)} height={14}
          rx={3} fill={bg} stroke={color} strokeWidth={0.5} opacity={0.95} />
        <text x={2} y={0} fontFamily="JetBrains Mono, ui-monospace, monospace"
          fontSize={10} fill={color}>{lblText}</text>
      </g>
    </g>
  );
}

window.Scene = Scene;
