// app.jsx — workspace chrome + side panels + scene mount.

const { useState: useSt, useEffect: useEf, useMemo: useMm, useRef: useRf } = React;
const Geom2 = window.Geom;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "sensorKind": "satellite",
  "groundKind": "flat",
  "showLegendInScene": true,
  "showWorkspaceChrome": true,
  "compactReadouts": false
}/*EDITMODE-END*/;

const TARGETS = [
  { id: 'extended', label: 'Extended scene', d3: false },
  { id: 'plate',    label: 'Flat plate',     d3: false },
  { id: 'box',      label: 'Box',            d3: true  },
  { id: 'sphere',   label: 'Sphere',         d3: true  },
  { id: 'cylinder', label: 'Cylinder',       d3: true  },
  { id: 'cone',     label: 'Cone',           d3: true  },
  { id: 'circle',   label: 'Circle (disk)',  d3: false },
  { id: 'ellipsoid',label: 'Ellipsoid',      d3: true  },
  { id: 'point',    label: 'Point source',   d3: false },
  { id: 'mesh',     label: 'Custom mesh',    d3: true  },
];
const is3D = (id) => TARGETS.find(t => t.id === id)?.d3;

const PRESETS = {
  iso:       { yaw: 35, pitch: 22 },
  top:       { yaw: 0,  pitch: 89 },
  side:      { yaw: 0,  pitch: 2 },
  principal: { yaw: 0,  pitch: 18 }, // sun and sensor share azimuth plane
};

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Scene state
  const [yaw, setYaw] = useSt(35);
  const [pitch, setPitch] = useSt(22);
  const [sunAz, setSunAz] = useSt(135);
  const [sunZen, setSunZen] = useSt(38);
  const [senAz, setSenAz] = useSt(50);
  const [senZen, setSenZen] = useSt(28);
  const [senAlt, setSenAlt] = useSt(705); // km
  const [tgtShape, setTgtShape] = useSt('sphere');
  const [tgtAlt, setTgtAlt] = useSt(1.2); // schematic units (representing altitude > 0)
  const [tgtRealAlt, setTgtRealAlt] = useSt(0.5); // km (display only)
  const [tgtDims, setTgtDims] = useSt({});
  const [tgtRoll, setTgtRoll]   = useSt(15);   // body-frame roll  (deg)
  const [tgtPitch, setTgtPitch] = useSt(-10);  // body-frame pitch (deg)
  const [tgtYaw, setTgtYaw]     = useSt(25);   // body-frame yaw   (deg)
  const [selected, setSelected] = useSt('sun');
  const [activeTab, setActiveTab] = useSt('Geometry');
  const [activeAccordion, setActiveAccordion] = useSt('sun');

  // Sync the right-panel accordion with whatever was clicked in the scene.
  useEf(() => {
    if (selected === 'sun')    setActiveAccordion('sun');
    if (selected === 'sensor') setActiveAccordion('sensor');
    if (selected === 'target') setActiveAccordion(is3D(tgtShape) ? 'orientation' : 'target');
  }, [selected, tgtShape]);

  // Drag-orbit
  const dragRef = useRf(null);
  function onMouseDown(e) {
    dragRef.current = { x: e.clientX, y: e.clientY, yaw, pitch };
  }
  function onMouseMove(e) {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.x;
    const dy = e.clientY - dragRef.current.y;
    setYaw((dragRef.current.yaw + dx * 0.4));
    setPitch(Math.max(2, Math.min(89, dragRef.current.pitch - dy * 0.3)));
  }
  function onMouseUp() { dragRef.current = null; }
  useEf(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  });

  const sunDir = Geom2.dirFromAzZen(sunAz, sunZen);
  const senDir = Geom2.dirFromAzZen(senAz, senZen);
  const angles = Geom2.computeAngles(sunDir, senDir);

  const target = { shape: tgtShape, dims: tgtDims, altitude: tgtAlt,
    roll: tgtRoll, pitch: tgtPitch, yaw: tgtYaw, is3D: is3D(tgtShape) };

  function applyPreset(p) {
    setYaw(PRESETS[p].yaw);
    setPitch(PRESETS[p].pitch);
  }

  return (
    <div className="rad-root" data-theme={t.theme}>
      {t.showWorkspaceChrome && <TopBar theme={t.theme} setTheme={(v) => setTweak('theme', v)} />}
      <div className="rad-shell">
        {t.showWorkspaceChrome && (
          <LeftDock activeTab={activeTab} setActiveTab={setActiveTab}
            tgtShape={tgtShape} setTgtShape={setTgtShape} />
        )}

        <div className="rad-center">
          {t.showWorkspaceChrome && <CenterTabs />}
          <div className="rad-canvas-wrap">
            <ViewportToolbar
              applyPreset={applyPreset}
              selected={selected} setSelected={setSelected}
            />
            <div className="rad-canvas" onMouseDown={onMouseDown}>
              <SceneMount
                yaw={yaw} pitch={pitch}
                sunAz={sunAz} sunZen={sunZen}
                senAz={senAz} senZen={senZen} senAlt={senAlt}
                target={target} tgtRealAlt={tgtRealAlt}
                sensorKind={t.sensorKind}
                groundKind={t.groundKind}
                theme={t.theme}
                selected={selected} setSelected={setSelected}
              />
              {t.showLegendInScene && (
                <Legend selected={selected} setSelected={setSelected} />
              )}
              <ScaleNote />
              <OrbitHint />
            </div>
            {t.showWorkspaceChrome && <BottomStatus angles={angles} senAlt={senAlt} tgtRealAlt={tgtRealAlt} />}
          </div>
        </div>

        <RightPanel
          angles={angles}
          sunAz={sunAz} setSunAz={setSunAz} sunZen={sunZen} setSunZen={setSunZen}
          senAz={senAz} setSenAz={setSenAz} senZen={senZen} setSenZen={setSenZen}
          senAlt={senAlt} setSenAlt={setSenAlt}
          tgtShape={tgtShape} setTgtShape={setTgtShape}
          tgtAlt={tgtAlt} setTgtAlt={setTgtAlt}
          tgtRealAlt={tgtRealAlt} setTgtRealAlt={setTgtRealAlt}
          tgtRoll={tgtRoll} setTgtRoll={setTgtRoll}
          tgtPitch={tgtPitch} setTgtPitch={setTgtPitch}
          tgtYaw={tgtYaw} setTgtYaw={setTgtYaw}
          selected={selected} setSelected={setSelected}
          activeAccordion={activeAccordion} setActiveAccordion={setActiveAccordion}
          compact={t.compactReadouts}
        />
      </div>

      <TweaksPanel>
        <TweakSection label="Theme" />
        <TweakRadio label="Theme" value={t.theme}
          options={[
            { value: 'dark',  label: 'Dark' },
            { value: 'light', label: 'Light' },
          ]}
          onChange={(v) => setTweak('theme', v)} />
        <TweakSection label="Schematic" />
        <TweakSelect label="Sensor body" value={t.sensorKind}
          options={[
            { value: 'satellite', label: 'Satellite (recommended)' },
            { value: 'cube',      label: 'Cube' },
            { value: 'fov',       label: 'Cube + FOV cone' },
            { value: 'marker',    label: 'Crosshair marker' },
          ]}
          onChange={(v) => setTweak('sensorKind', v)} />
        <TweakRadio label="Ground" value={t.groundKind}
          options={[
            { value: 'flat',   label: 'Flat' },
            { value: 'curved', label: 'Curved' },
          ]}
          onChange={(v) => setTweak('groundKind', v)} />
        <TweakSection label="Layout" />
        <TweakToggle label="Workspace chrome" value={t.showWorkspaceChrome}
          onChange={(v) => setTweak('showWorkspaceChrome', v)} />
        <TweakToggle label="In-scene legend" value={t.showLegendInScene}
          onChange={(v) => setTweak('showLegendInScene', v)} />
        <TweakToggle label="Compact readouts" value={t.compactReadouts}
          onChange={(v) => setTweak('compactReadouts', v)} />
      </TweaksPanel>
    </div>
  );
}

// ── Workspace chrome ────────────────────────────────────────────────────────
function TopBar({ theme, setTheme }) {
  return (
    <div className="rad-topbar">
      <div className="rad-brand">
        <div className="rad-logo"></div>
        <span className="rad-brand-name">RADIANT</span>
        <span className="rad-brand-sub">Spatial · Spectral · Radiometric</span>
      </div>
      <div className="rad-menu">
        {['File', 'Scenario', 'Sensor', 'Atmosphere', 'Run', 'View', 'Help'].map((m) => (
          <span key={m} className="rad-menu-item">{m}</span>
        ))}
      </div>
      <div className="rad-theme-seg" role="group" aria-label="Theme">
        <button className={`rad-theme-btn ${theme === 'dark' ? 'active' : ''}`}
          onClick={() => setTheme('dark')} aria-label="Dark theme">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M11.5 9.5A4.5 4.5 0 0 1 6.5 4.5c0-.65.14-1.27.39-1.83A5.5 5.5 0 1 0 13.33 9.11c-.56.25-1.18.39-1.83.39Z"
              fill="currentColor"/>
          </svg>
          <span>Dark</span>
        </button>
        <button className={`rad-theme-btn ${theme === 'light' ? 'active' : ''}`}
          onClick={() => setTheme('light')} aria-label="Light theme">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="3" fill="currentColor"/>
            {[0,45,90,135,180,225,270,315].map(a => {
              const r = a * Math.PI / 180;
              const x1 = 8 + Math.cos(r) * 5, y1 = 8 + Math.sin(r) * 5;
              const x2 = 8 + Math.cos(r) * 7, y2 = 8 + Math.sin(r) * 7;
              return <line key={a} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>;
            })}
          </svg>
          <span>Light</span>
        </button>
      </div>
      <div className="rad-statuspill">
        <span className="rad-led"></span>
        <span>Scenario: TWILIGHT_OCN_01</span>
      </div>
    </div>
  );
}

function LeftDock({ activeTab, setActiveTab, tgtShape, setTgtShape }) {
  const [open, setOpen] = useSt({ Scene: true, Targets: true, Sensors: false, Atm: false });
  const items = [
    { id: 'Scene', label: 'Scene', children: [
      { label: 'Sun', icon: '☉', active: false },
      { label: 'Ground', icon: '▣', active: false },
      { label: 'Atmosphere', icon: '◌', active: false },
    ]},
    { id: 'Targets', label: 'Targets', children: TARGETS.map(t => ({
      label: t.label, icon: '◇', active: tgtShape === t.id, id: t.id,
    }))},
    { id: 'Sensors', label: 'Sensors', children: [
      { label: 'OBS-1 · MWIR pushbroom', icon: '◈', active: true },
    ]},
    { id: 'Atm', label: 'Atmosphere', children: [
      { label: 'MODTRAN6 · MidLat Summer', icon: '~', active: true },
    ]},
  ];
  return (
    <div className="rad-left">
      <div className="rad-dock-tabs">
        <span className="rad-dt rad-dt-active">Scenario Tree</span>
        <span className="rad-dt">Library</span>
        <span className="rad-dt">Runs</span>
      </div>
      <div className="rad-tree">
        {items.map((sec) => (
          <div key={sec.id} className="rad-tree-sec">
            <div className="rad-tree-sec-h" onClick={() => setOpen({ ...open, [sec.id]: !open[sec.id] })}>
              <span className={`rad-tri ${open[sec.id] ? 'open' : ''}`}>▸</span>
              <span>{sec.label}</span>
            </div>
            {open[sec.id] && (
              <div className="rad-tree-list">
                {sec.children.map((c, i) => (
                  <div key={i}
                    className={`rad-tree-item ${c.active ? 'active' : ''}`}
                    onClick={() => c.id && setTgtShape(c.id)}>
                    <span className="rad-tree-icon">{c.icon}</span>
                    <span>{c.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CenterTabs() {
  return (
    <div className="rad-tabs">
      {[
        { l: 'Scenario',  active: false },
        { l: 'Geometry',  active: true },
        { l: 'Spectral',  active: false },
        { l: 'Output',    active: false },
        { l: 'Reports',   active: false },
      ].map((t, i) => (
        <div key={i} className={`rad-tab ${t.active ? 'active' : ''}`}>
          {t.l}
        </div>
      ))}
    </div>
  );
}

function ViewportToolbar({ applyPreset, selected, setSelected }) {
  return (
    <div className="rad-vtoolbar">
      <div className="rad-vtools">
        <span className="rad-vtools-label">VIEW</span>
        {['iso','top','side','principal'].map(p => (
          <button key={p} className="rad-btn" onClick={() => applyPreset(p)}>
            {p === 'iso' ? 'Iso' : p === 'top' ? 'Top' : p === 'side' ? 'Side' : 'Principal Plane'}
          </button>
        ))}
      </div>
      <div className="rad-vtools">
        <span className="rad-vtools-label">SHOW ANGLES</span>
        {[
          { id: 'sun',    l: 'Solar (θₛ, φₛ)',   c: '#f5b942' },
          { id: 'sensor', l: 'View (θᵥ, φᵥ)',     c: '#6ad1ff' },
          { id: 'phase',  l: 'Phase / Δφ',        c: '#e667c8' },
        ].map(o => (
          <button key={o.id}
            className={`rad-btn rad-chip ${selected === o.id ? 'active' : ''}`}
            style={selected === o.id ? { borderColor: o.c, color: o.c } : null}
            onClick={() => setSelected(selected === o.id ? null : o.id)}>
            <span className="rad-dot" style={{ background: o.c }}></span>
            {o.l}
          </button>
        ))}
      </div>
    </div>
  );
}

function SceneMount(props) {
  const wrap = useRf(null);
  const [size, setSize] = useSt({ w: 720, h: 520 });
  useEf(() => {
    if (!wrap.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const r = entry.contentRect;
      setSize({ w: Math.floor(r.width), h: Math.floor(r.height) });
    });
    ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={wrap} className="rad-scene-mount">
      <window.Scene {...props} width={size.w} height={size.h} />
    </div>
  );
}

function Legend({ selected, setSelected }) {
  const items = [
    { id: 'sun',    label: 'SUN → TARGET',     c: '#f5b942', dash: false },
    { id: 'sensor', label: 'SENSOR → TARGET',  c: '#6ad1ff', dash: false },
    { id: 'shadow', label: 'SUN → GROUND',     c: '#f5b942', dash: true  },
    { id: 'zenith', label: 'ZENITH AXIS',      c: '#cfd6e1', dash: false },
  ];
  return (
    <div className="rad-legend">
      <div className="rad-legend-h">VECTORS</div>
      {items.map(it => (
        <div key={it.id}
          className={`rad-legend-row ${selected === it.id ? 'active' : ''}`}
          onClick={() => setSelected(selected === it.id ? null : it.id)}>
          <svg width="22" height="6">
            <line x1="0" y1="3" x2="22" y2="3"
              stroke={it.c} strokeWidth="2"
              strokeDasharray={it.dash ? '3 2' : null}
              strokeLinecap="round" />
          </svg>
          <span>{it.label}</span>
        </div>
      ))}
    </div>
  );
}

function ScaleNote() {
  return (
    <div className="rad-scalenote">
      <span className="rad-cross">+</span> SCHEMATIC · NOT TO SCALE
    </div>
  );
}

function OrbitHint() {
  return (
    <div className="rad-orbit-hint">
      <span>⌥</span> drag to orbit · scroll to zoom · click any vector for angles
    </div>
  );
}

function BottomStatus({ angles, senAlt, tgtRealAlt }) {
  const cells = [
    ['CAMERA', 'ORTHO · ISO'],
    ['UNITS', 'deg · km'],
    ['SUN', `θₛ ${angles.thetaS.toFixed(1)}°  φₛ ${angles.phiS.toFixed(1)}°`],
    ['VIEW', `θᵥ ${angles.thetaV.toFixed(1)}°  φᵥ ${angles.phiV.toFixed(1)}°`],
    ['Δφ', `${angles.dphi.toFixed(1)}°`],
    ['PHASE', `${angles.phase.toFixed(1)}°`],
    ['SENSOR ALT', `${senAlt} km`],
    ['TARGET ALT', `${tgtRealAlt} km`],
  ];
  return (
    <div className="rad-status">
      {cells.map((c, i) => (
        <span key={i} className="rad-status-cell">
          <em>{c[0]}</em><b>{c[1]}</b>
        </span>
      ))}
      <span className="rad-status-spacer"></span>
      <span className="rad-status-cell"><em>READY</em><b>—</b></span>
    </div>
  );
}

// ── Right panel ─────────────────────────────────────────────────────────────
function RightPanel(props) {
  const {
    angles, sunAz, setSunAz, sunZen, setSunZen,
    senAz, setSenAz, senZen, setSenZen, senAlt, setSenAlt,
    tgtShape, setTgtShape, tgtAlt, setTgtAlt, tgtRealAlt, setTgtRealAlt,
    tgtRoll, setTgtRoll, tgtPitch, setTgtPitch, tgtYaw, setTgtYaw,
    selected, setSelected,
    activeAccordion, setActiveAccordion, compact,
  } = props;

  const Acc = ({ id, label, color, children }) => {
    const open = activeAccordion === id;
    return (
      <div className={`rad-acc ${open ? 'open' : ''}`}>
        <div className="rad-acc-h" onClick={() => setActiveAccordion(open ? null : id)}>
          <span className="rad-acc-dot" style={{ background: color }}></span>
          <span>{label}</span>
          <span className="rad-acc-chev">{open ? '–' : '+'}</span>
        </div>
        {open && <div className="rad-acc-body">{children}</div>}
      </div>
    );
  };

  const Field = ({ label, value, unit = '°', step = 1, onChange }) => (
    <div className="rad-field">
      <label>{label}</label>
      <div className="rad-numwrap">
        <input className="rad-num" type="number" value={value}
          step={step}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)} />
        <span className="rad-unit">{unit}</span>
      </div>
    </div>
  );

  return (
    <div className="rad-right">
      <div className="rad-r-head">
        <span>VIEWING GEOMETRY</span>
        <span className="rad-live"><span className="rad-blip"></span>LIVE</span>
      </div>

      <div className={`rad-readouts ${compact ? 'compact' : ''}`}>
        <Readout label="θₛ" sub="Solar zenith"   value={angles.thetaS} color="#f5b942" />
        <Readout label="φₛ" sub="Solar azimuth"  value={angles.phiS}   color="#f5b942" />
        <Readout label="θᵥ" sub="View zenith"    value={angles.thetaV} color="#6ad1ff" />
        <Readout label="φᵥ" sub="View azimuth"   value={angles.phiV}   color="#6ad1ff" />
        <Readout label="Δφ" sub="Relative az."   value={angles.dphi}   color="#e667c8" />
        <Readout label="g"  sub="Phase angle"    value={angles.phase}  color="#e667c8" />
      </div>

      <div className="rad-r-section">EDITORS</div>

      <Acc id="sun" label="Sun position" color="#f5b942">
        <div className="rad-mode-row">
          <span className="rad-pill rad-pill-active">Direct</span>
          <span className="rad-pill">Date · Time · Lat/Lon</span>
        </div>
        <Field label="Solar zenith θₛ"  value={Math.round(sunZen)} onChange={setSunZen} />
        <Field label="Solar azimuth φₛ" value={Math.round(sunAz)}  onChange={setSunAz} />
        <div className="rad-hint">2026-04-12 14:32:08 UTC · 36.8°N 121.6°W</div>
      </Acc>

      <Acc id="sensor" label="Sensor position" color="#6ad1ff">
        <div className="rad-mode-row">
          <span className="rad-pill rad-pill-active">Az / El</span>
          <span className="rad-pill">ECI / TLE</span>
        </div>
        <Field label="View zenith θᵥ"  value={Math.round(senZen)} onChange={setSenZen} />
        <Field label="View azimuth φᵥ" value={Math.round(senAz)}  onChange={setSenAz} />
        <Field label="Sensor altitude" value={senAlt} unit="km" step={5} onChange={setSenAlt} />
      </Acc>

      <Acc id="target" label="Target" color="#e8ecf2">
        <div className="rad-shape-grid">
          {TARGETS.map(t => (
            <button key={t.id}
              className={`rad-shape ${tgtShape === t.id ? 'active' : ''}`}
              onClick={() => setTgtShape(t.id)}>
              <span className="rad-shape-glyph">{shapeGlyph(t.id)}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </div>
        <Field label="Target altitude" value={tgtRealAlt} unit="km" step={0.1}
          onChange={(v) => { setTgtRealAlt(v); setTgtAlt(v > 0 ? Math.max(0.6, Math.min(2.4, v * 1.2)) : 0); }} />
      </Acc>

      {is3D(tgtShape) && (
        <Acc id="orientation" label="Target orientation (RPY)" color="#a78bfa">
          <div className="rad-mode-row">
            <span className="rad-pill rad-pill-active">Body frame</span>
            <span className="rad-hint" style={{ border: 'none', padding: 0, marginLeft: 'auto' }}>
              click target to view
            </span>
          </div>
          <Field label="Roll (φ)"  value={tgtRoll}  step={1} onChange={setTgtRoll} />
          <Field label="Pitch (θ)" value={tgtPitch} step={1} onChange={setTgtPitch} />
          <Field label="Yaw (ψ)"   value={tgtYaw}   step={1} onChange={setTgtYaw} />
          <div className="rad-rpy-readout">
            <span className="rad-rpy-cell" style={{ '--rc': '#ff6b8a' }}>
              <em>X′</em><b>Roll {tgtRoll.toFixed(1)}°</b>
            </span>
            <span className="rad-rpy-cell" style={{ '--rc': '#7bd389' }}>
              <em>Y′</em><b>Pitch {tgtPitch.toFixed(1)}°</b>
            </span>
            <span className="rad-rpy-cell" style={{ '--rc': '#a78bfa' }}>
              <em>Z′</em><b>Yaw {tgtYaw.toFixed(1)}°</b>
            </span>
          </div>
        </Acc>
      )}
    </div>
  );
}

function Readout({ label, sub, value, color }) {
  return (
    <div className="rad-readout" style={{ '--rc': color }}>
      <span className="rad-ro-lbl" style={{ color }}>{label}</span>
      <span className="rad-ro-sub">{sub}</span>
      <span className="rad-ro-val">{value.toFixed(2)}<i>°</i></span>
    </div>
  );
}

function shapeGlyph(id) {
  const m = {
    extended: '▭', plate: '▱', box: '◰', sphere: '○', cylinder: '⌭',
    cone: '△', circle: '◯', ellipsoid: '⬭', point: '·', mesh: '✦',
  };
  return m[id] || '◇';
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
