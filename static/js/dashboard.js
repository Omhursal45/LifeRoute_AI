/**
 * India map + real-time ambulance positions (poll) + smooth marker motion.
 * Geolocation: centers map on your position when allowed.
 */
(function () {
  const INDIA_CENTER = [20.5937, 78.9629];
  const HYDERABAD_DEFAULT = [17.385, 78.4867];
  let map;
  /** @type {Map<number, { marker: L.CircleMarker, anim?: number }>} */
  const ambulanceById = new Map();
  let hospitalLayer = L.layerGroup();
  let userMarker = null;
  let simTimer = null;
  let simAmbId = null;
  let simStep = 0;

  const POLL_MS = 2000;
  const SESSION_ANCHOR_KEY = 'lr_fleet_anchored';

  /** Local loop used by fleet simulation; rebuilt when demo is anchored to GPS. */
  let simPath = buildSimPath(HYDERABAD_DEFAULT[0], HYDERABAD_DEFAULT[1]);

  function buildSimPath(centerLat, centerLng) {
    const d = 0.006;
    return [
      [centerLat, centerLng],
      [centerLat + d * 0.25, centerLng + d * 0.45],
      [centerLat + d * 0.55, centerLng + d * 0.25],
      [centerLat + d * 0.85, centerLng + d * 0.55],
      [centerLat + d * 0.45, centerLng + d * 0.9],
      [centerLat + d * 0.15, centerLng + d * 0.65],
      [centerLat, centerLng],
    ];
  }

  /**
   * Move all demo hospitals & ambulances on the server near this GPS point.
   * @param {boolean} force - if true, always call API (e.g. user clicked My Location)
   */
  async function anchorDemoNearMe(lat, lng, force) {
    if (!force && sessionStorage.getItem(SESSION_ANCHOR_KEY)) {
      return { skipped: true };
    }
    const res = await LRAuth.fetchAuth('/api/emergency/demo/anchor-near-me/', {
      method: 'POST',
      body: { latitude: lat, longitude: lng },
    });
    if (!res.ok) {
      let msg = res.statusText;
      try {
        const err = await res.json();
        msg = err.detail || JSON.stringify(err);
      } catch (e) {
        /* ignore */
      }
      console.warn('anchor-near-me failed:', msg);
      return { ok: false, error: msg };
    }
    try {
      sessionStorage.setItem(SESSION_ANCHOR_KEY, '1');
    } catch (e) {
      /* ignore */
    }
    simPath = buildSimPath(lat, lng);
    await loadAmbulances();
    await loadHospitalsNear([lat, lng]);
    return { ok: true };
  }

  function ensureAuth() {
    if (!LRAuth.getAccess()) {
      window.location.href = '/login/?next=/dashboard/';
      return false;
    }
    return true;
  }

  function animateMarker(ambulanceId, marker, toLat, toLng, durationMs) {
    const from = marker.getLatLng();
    const start = performance.now();
    const entry = ambulanceById.get(ambulanceId);
    if (entry && entry.anim) cancelAnimationFrame(entry.anim);

    function step(now) {
      const t = Math.min(1, (now - start) / durationMs);
      const ease = t * (2 - t);
      const lat = from.lat + (toLat - from.lat) * ease;
      const lng = from.lng + (toLng - from.lng) * ease;
      marker.setLatLng([lat, lng]);
      const e = ambulanceById.get(ambulanceId);
      if (t < 1) {
        const fr = requestAnimationFrame(step);
        if (e) e.anim = fr;
      } else if (e) {
        e.anim = undefined;
      }
    }
    requestAnimationFrame(step);
  }

  let driverRouteLayer = null;

  async function loadMe() {
    const res = await LRAuth.fetchAuth('/api/auth/me/');
    if (!res.ok) return;
    const u = await res.json();
    const el = document.getElementById('badgeRole');
    if (el) el.textContent = u.role || '';
    try {
      sessionStorage.setItem('lr_me', JSON.stringify({ role: u.role, username: u.username }));
    } catch (e) {
      /* ignore */
    }
    initDriverNavigation(u.role);
  }

  async function initDriverNavigation(role) {
    const panel = document.getElementById('driverNavPanel');
    if (!panel) return;
    if (role !== 'driver' && role !== 'admin') return;
    panel.classList.remove('d-none');
    await populateDriverHospitalSelect();
    const ambRow = document.getElementById('driverAmbulanceRow');
    if (ambRow) {
      ambRow.classList.toggle('d-none', role !== 'admin');
      if (role === 'admin') await populateDriverAmbulanceSelect();
    }
  }

  async function populateDriverHospitalSelect() {
    const sel = document.getElementById('driverHospitalSelect');
    if (!sel) return;
    try {
      const res = await fetch('/api/hospitals/');
      const data = await res.json();
      const rows = Array.isArray(data) ? data : data.results || [];
      sel.innerHTML = '<option value="">— Select hospital —</option>';
      rows.forEach((h) => {
        const o = document.createElement('option');
        o.value = h.id;
        o.textContent = h.name;
        sel.appendChild(o);
      });
    } catch (e) {
      /* ignore */
    }
  }

  async function populateDriverAmbulanceSelect() {
    const sel = document.getElementById('driverAmbulanceSelect');
    if (!sel) return;
    const res = await fetch('/api/tracking/ambulances/');
    const data = await res.json();
    const rows = Array.isArray(data) ? data : data.results || [];
    sel.innerHTML = '<option value="">First active (default)</option>';
    rows.forEach((a) => {
      const o = document.createElement('option');
      o.value = a.id;
      o.textContent = `${a.vehicle_code} (#${a.id})`;
      sel.appendChild(o);
    });
  }

  function driverNavExtraBody() {
    const ambSel = document.getElementById('driverAmbulanceSelect');
    if (!ambSel || ambSel.closest('.d-none')) return {};
    const v = ambSel.value;
    if (!v) return {};
    return { ambulance_id: parseInt(v, 10) };
  }

  async function runDriverNavigate(body) {
    const res = await LRAuth.fetchAuth('/api/emergency/routing/driver-navigate/', {
      method: 'POST',
      body: { ...body, ...driverNavExtraBody() },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || JSON.stringify(data));
      return;
    }
    if (driverRouteLayer) {
      map.removeLayer(driverRouteLayer);
      driverRouteLayer = null;
    }
    if (data.geometry && data.geometry.type) {
      driverRouteLayer = L.geoJSON(data.geometry, {
        style: { color: '#0d6efd', weight: 6, opacity: 0.9 },
      }).addTo(map);
      try {
        map.fitBounds(driverRouteLayer.getBounds(), { padding: [48, 48], maxZoom: 15 });
      } catch (e) {
        /* ignore */
      }
    }
    const meta = document.getElementById('driverRouteMeta');
    if (meta) {
      const minPlain = Math.round(data.duration_sec / 60);
      const minAdj = Math.round(data.duration_adjusted_sec / 60);
      const alts = (data.alternatives || []).length;
      meta.innerHTML =
        `<strong>${data.distance_km} km</strong> · ~${minPlain} min drive (~${minAdj} min with traffic model) · ` +
        `<span class="text-muted">${alts} alternative(s) compared. ${data.selection_reason || ''}</span>`;
    }
  }

  function setupDriverNavButtons() {
    document.getElementById('btnDriverNavRoute')?.addEventListener('click', async () => {
      const hid = document.getElementById('driverHospitalSelect')?.value;
      if (!hid) {
        alert('Select a hospital from the list.');
        return;
      }
      await runDriverNavigate({ hospital_id: parseInt(hid, 10) });
    });

    let pickArmed = false;
    let pickHandler = null;
    const btnPick = document.getElementById('btnDriverPickMap');
    btnPick?.addEventListener('click', () => {
      if (pickArmed) {
        pickArmed = false;
        if (pickHandler) {
          map.off('click', pickHandler);
          pickHandler = null;
        }
        btnPick.classList.remove('btn-warning');
        btnPick.textContent = 'Pick point on map';
        map.getContainer().style.cursor = '';
        return;
      }
      pickArmed = true;
      btnPick.classList.add('btn-warning');
      btnPick.textContent = 'Click map… (cancel)';
      map.getContainer().style.cursor = 'crosshair';
      pickHandler = async (e) => {
        map.off('click', pickHandler);
        pickHandler = null;
        pickArmed = false;
        btnPick.classList.remove('btn-warning');
        btnPick.textContent = 'Pick point on map';
        map.getContainer().style.cursor = '';
        await runDriverNavigate({
          destination_latitude: e.latlng.lat,
          destination_longitude: e.latlng.lng,
        });
      };
      map.on('click', pickHandler);
    });
  }

  function updateAmbulanceList(rows) {
    const list = document.getElementById('listAmbulances');
    if (!list) return;
    list.innerHTML = '';
    rows.forEach((a) => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between';
      li.innerHTML = `<span><strong>${a.vehicle_code}</strong> (${a.driver_username || '—'})</span><span class="text-muted font-monospace">${a.current_latitude.toFixed(5)}, ${a.current_longitude.toFixed(5)}</span>`;
      list.appendChild(li);
    });
  }

  async function loadAmbulances() {
    const res = await fetch('/api/tracking/ambulances/');
    const data = await res.json();
    const rows = Array.isArray(data) ? data : data.results || [];
    updateAmbulanceList(rows);

    const seen = new Set();
    rows.forEach((a) => {
      seen.add(a.id);
      const lat = a.current_latitude;
      const lng = a.current_longitude;
      let entry = ambulanceById.get(a.id);
      if (!entry) {
        const marker = L.circleMarker([lat, lng], {
          radius: 12,
          color: '#b02a37',
          weight: 3,
          fillColor: '#ff6b6b',
          fillOpacity: 0.95,
        });
        marker.addTo(map);
        marker.bindPopup(`<b>${a.vehicle_code}</b><br/>Live ambulance`);
        ambulanceById.set(a.id, { marker: marker });
      } else {
        const cur = entry.marker.getLatLng();
        const moved = Math.abs(cur.lat - lat) > 1e-7 || Math.abs(cur.lng - lng) > 1e-7;
        if (moved) {
          animateMarker(a.id, entry.marker, lat, lng, 650);
        }
      }
    });

    ambulanceById.forEach((entry, id) => {
      if (!seen.has(id)) {
        if (entry.anim) cancelAnimationFrame(entry.anim);
        map.removeLayer(entry.marker);
        ambulanceById.delete(id);
      }
    });

    if (!simAmbId && rows[0]) simAmbId = rows[0].id;
  }

  async function loadHospitalsNear(center) {
    const [lat, lng] = center;
    const res = await fetch(
      `/api/hospitals/nearest/?lat=${lat}&lon=${lng}&limit=20&consider_ambulances=1`,
    );
    const data = await res.json();
    const list = document.getElementById('listHospitals');
    if (!list) return;
    list.innerHTML = '';
    hospitalLayer.clearLayers();
    (data.results || []).forEach((row) => {
      const h = row.hospital;
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between';
      const ambKm =
        row.distance_km_from_nearest_ambulance != null
          ? `${row.distance_km_from_nearest_ambulance} km`
          : '—';
      li.innerHTML = `<span>${h.name}</span><span class="text-muted text-end"><span class="d-block fw-medium">${row.distance_km} km</span><span class="small text-secondary">You ${row.distance_km_from_you} km · Amb ${ambKm}</span></span>`;
      list.appendChild(li);
      L.marker([h.latitude, h.longitude], { title: h.name })
        .addTo(hospitalLayer)
        .bindPopup(`<b>${h.name}</b><br/>Beds: ${h.beds_available}`);
    });
  }

  let userGpsWatch = null;
  let userGpsCentered = false;

  function ensureUserMarker(lat, lng) {
    if (!map) return;
    if (userMarker) {
      userMarker.setLatLng([lat, lng]);
    } else {
      userMarker = L.circleMarker([lat, lng], {
        radius: 9,
        color: '#0d6efd',
        weight: 2,
        fillColor: '#9ec5fe',
        fillOpacity: 0.95,
      }).addTo(map);
      userMarker.bindPopup('Your live location (GPS)');
    }
  }

  function setUserLocation(lat, lng, pan) {
    ensureUserMarker(lat, lng);
    if (pan && map) {
      map.setView([lat, lng], 14);
      loadHospitalsNear([lat, lng]);
    }
  }

  function goMyLocation() {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by this browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        await anchorDemoNearMe(lat, lng, true);
        setUserLocation(lat, lng, true);
        const el = document.getElementById('liveStatus');
        if (el) el.textContent = 'Live · Near you';
      },
      () => {
        alert('Could not read your location. Allow access in the browser or pan the map manually.');
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );
  }

  function startLiveGpsWatch() {
    if (!navigator.geolocation) return;
    userGpsWatch = navigator.geolocation.watchPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        ensureUserMarker(lat, lng);
        if (!userGpsCentered) {
          userGpsCentered = true;
          void anchorDemoNearMe(lat, lng, false).then(async (r) => {
            map.setView([lat, lng], 14);
            if (r && r.skipped) {
              await loadAmbulances();
              await loadHospitalsNear([lat, lng]);
            }
            const el = document.getElementById('liveStatus');
            if (el) {
              el.textContent =
                r && r.ok === false
                  ? 'Live · GPS (anchor failed — tap My Location)'
                  : 'Live · Near you';
            }
          });
        }
        const el = document.getElementById('liveStatus');
        if (el && userGpsCentered) el.textContent = 'Live · Near you';
      },
      () => {
        if (!userGpsCentered) {
          map.setView(INDIA_CENTER, 5);
          const el = document.getElementById('liveStatus');
          if (el) el.textContent = 'Live · India (enable GPS)';
        }
      },
      { enableHighAccuracy: true, maximumAge: 1500, timeout: 20000 },
    );
  }

  async function getSimulateRole() {
    let me = {};
    try {
      me = JSON.parse(sessionStorage.getItem('lr_me') || '{}');
    } catch (e) {
      /* ignore */
    }
    if (!me.role) {
      const res = await LRAuth.fetchAuth('/api/auth/me/');
      if (res.ok) {
        const u = await res.json();
        me = { role: u.role, username: u.username };
        try {
          sessionStorage.setItem('lr_me', JSON.stringify(me));
        } catch (err) {
          /* ignore */
        }
      }
    }
    return me.role || '';
  }

  function setSimulateButton(active) {
    const btn = document.getElementById('btnSimulate');
    if (!btn) return;
    const startL = btn.dataset.startLabel || 'Simulate Fleet';
    const stopL = btn.dataset.stopLabel || 'Stop fleet';
    if (active) {
      btn.classList.remove('btn-primary');
      btn.classList.add('btn-danger');
      btn.innerHTML = '\u23f9 ' + stopL;
    } else {
      btn.classList.remove('btn-danger');
      btn.classList.add('btn-primary');
      btn.innerHTML = '🚑 ' + startL;
    }
  }

  async function startSimulate() {
    if (!ensureAuth()) return;

    if (simTimer) {
      clearInterval(simTimer);
      simTimer = null;
      setSimulateButton(false);
      return;
    }

    const role = await getSimulateRole();
    if (role !== 'driver' && role !== 'admin') {
      alert('Log in as a driver or admin to simulate fleet movement.');
      return;
    }

    const listRes = await fetch('/api/tracking/ambulances/');
    const listData = await listRes.json();
    const allRows = Array.isArray(listData) ? listData : listData.results || [];

    let me = {};
    try {
      me = JSON.parse(sessionStorage.getItem('lr_me') || '{}');
    } catch (e) {
      /* ignore */
    }

    const targets =
      role === 'admin'
        ? allRows
        : allRows.filter((a) => a.driver_username === me.username);

    if (!targets.length) {
      alert(
        role === 'admin'
          ? 'No ambulances in the system. Run: python manage.py seed_demo'
          : 'No ambulance is assigned to your driver account.',
      );
      return;
    }

    simStep = 0;
    simAmbId = targets[0].id;
    setSimulateButton(true);

    simTimer = setInterval(async () => {
      let hadError = false;
      let errDetail = '';
      for (let i = 0; i < targets.length; i++) {
        const amb = targets[i];
        const idx = (simStep + i * 2) % simPath.length;
        const [la, lo] = simPath[idx];
        const res = await LRAuth.fetchAuth(`/api/tracking/ambulances/${amb.id}/location/`, {
          method: 'PATCH',
          body: { latitude: la, longitude: lo },
        });
        if (!res.ok) {
          hadError = true;
          try {
            const err = await res.json();
            errDetail = err.detail || JSON.stringify(err);
          } catch (e) {
            errDetail = res.statusText;
          }
          break;
        }
      }
      simStep += 1;
      await loadAmbulances();
      if (hadError) {
        clearInterval(simTimer);
        simTimer = null;
        setSimulateButton(false);
        alert('Fleet simulation stopped: ' + (errDetail || 'request failed'));
      }
    }, 2500);
  }

  window.addEventListener('DOMContentLoaded', async () => {
    if (!ensureAuth()) return;
    await loadMe();

    map = L.map('mapDashboard').setView(HYDERABAD_DEFAULT, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Hyderabad',
    }).addTo(map);
    hospitalLayer.addTo(map);

    await loadAmbulances();
    await loadHospitalsNear(HYDERABAD_DEFAULT);

    map.on('moveend', () => {
      const c = map.getCenter();
      loadHospitalsNear([c.lat, c.lng]);
    });

    document.getElementById('btnSimulate')?.addEventListener('click', startSimulate);
    document.getElementById('btnMyLocation')?.addEventListener('click', goMyLocation);
    setupDriverNavButtons();

    setInterval(loadAmbulances, POLL_MS);

    if (navigator.geolocation) {
      startLiveGpsWatch();
    } else {
      map.setView(INDIA_CENTER, 5);
    }
  });
})();
