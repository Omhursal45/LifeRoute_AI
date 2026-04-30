(() => {
  const HOLD_MS = 3000;
  let sosMap = null;
  let routeLayer = null;
  let markerPatient = null;
  let markerAmb = null;
  let markerHospital = null;
  let holdTimer = null;
  let holdStartedAt = 0;
  let holdProgressTimer = null;

  function setMsg(kind, text) {
    const box = document.getElementById('sosMessage');
    if (!box) {
      // Global fallback when home widgets are not present.
      window.alert(text);
      return;
    }
    box.className = `alert alert-${kind} mt-3`;
    box.textContent = text;
    box.classList.remove('d-none');
  }

  function ensureMap(center) {
    if (sosMap) return;
    const el = document.getElementById('sosMap');
    if (!el) return;
    sosMap = L.map(el).setView(center, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap',
    }).addTo(sosMap);
  }

  function drawSOS(data) {
    const wrap = document.getElementById('sosMapWrap');
    const meta = document.getElementById('sosMeta');
    if (!wrap || !meta) return;

    const p = data.patient_location;
    const a = data.assigned_ambulance;
    const h = data.nearest_hospital;

    wrap.classList.remove('d-none');
    ensureMap([p.latitude, p.longitude]);
    if (!sosMap) return;

    if (routeLayer) sosMap.removeLayer(routeLayer);
    if (markerPatient) sosMap.removeLayer(markerPatient);
    if (markerAmb) sosMap.removeLayer(markerAmb);
    if (markerHospital) sosMap.removeLayer(markerHospital);

    markerPatient = L.circleMarker([p.latitude, p.longitude], {
      radius: 10,
      color: '#0d6efd',
      fillColor: '#9ec5fe',
      fillOpacity: 0.95,
      weight: 2,
    })
      .addTo(sosMap)
      .bindPopup('You (SOS)');

    markerAmb = L.circleMarker([a.latitude, a.longitude], {
      radius: 12,
      color: '#b02a37',
      fillColor: '#ff6b6b',
      fillOpacity: 0.95,
      weight: 3,
    })
      .addTo(sosMap)
      .bindPopup(`Ambulance ${a.vehicle_code}`);

    if (h && h.latitude && h.longitude) {
      markerHospital = L.marker([h.latitude, h.longitude]).addTo(sosMap).bindPopup(`Hospital: ${h.name}`);
    }

    const geom = data.route_to_patient && data.route_to_patient.geometry;
    if (geom && geom.type) {
      routeLayer = L.geoJSON(geom, {
        style: { color: '#0d6efd', weight: 5, opacity: 0.85, dashArray: '10 6' },
      }).addTo(sosMap);
    }

    const parts = [];
    if (a.distance_km != null) parts.push(`Nearest ambulance: ${a.distance_km} km`);
    if (data.route_to_patient && data.route_to_patient.distance_km != null) {
      parts.push(`Route distance: ${data.route_to_patient.distance_km} km`);
    }
    if (data.route_to_patient && data.route_to_patient.eta_seconds != null) {
      parts.push(`ETA: ${Math.round(data.route_to_patient.eta_seconds / 60)} min`);
    }
    if (h && h.name) parts.push(`Nearest hospital: ${h.name}`);
    meta.textContent = parts.join(' | ');

    const fg = L.featureGroup([markerPatient, markerAmb, markerHospital, routeLayer].filter(Boolean));
    try {
      sosMap.fitBounds(fg.getBounds(), { padding: [40, 40], maxZoom: 14 });
    } catch (_) {}
  }

  async function triggerSOS() {
    if (!LRAuth.getAccess()) {
      window.location.href = '/login/?next=/';
      return;
    }
    const btn = document.getElementById('btnSOSOneTap');
    if (btn) btn.disabled = true;

    if (!navigator.geolocation) {
      setMsg('danger', 'Geolocation not supported in this browser.');
      if (btn) btn.disabled = false;
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6));
        const lng = Number(pos.coords.longitude.toFixed(6));
        try {
          const res = await LRAuth.fetchAuth('/api/emergency/sos/one-tap/', {
            method: 'POST',
            body: { latitude: lat, longitude: lng },
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            const msg = data.detail || 'SOS request failed.';
            setMsg(res.status === 409 ? 'warning' : 'danger', msg);
            return;
          }
          setMsg('success', 'SOS sent. Nearest ambulance assigned instantly.');
          drawSOS(data);
        } catch (e) {
          setMsg('danger', 'Network error while sending SOS.');
        } finally {
          if (btn) btn.disabled = false;
        }
      },
      (err) => {
        if (err.code === 1) {
          setMsg('warning', 'Location permission denied. Please allow GPS for one-tap SOS.');
        } else {
          setMsg('danger', 'Could not detect your location. Try again.');
        }
        if (btn) btn.disabled = false;
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    );
  }

  function resetHoldButton(btn) {
    if (!btn) return;
    btn.classList.remove('btn-warning');
    btn.classList.add('btn-danger');
    btn.style.backgroundImage = '';
    btn.style.backgroundSize = '';
    btn.style.backgroundRepeat = '';
    btn.style.backgroundPosition = '';
    btn.innerHTML = '<i class="bi bi-broadcast-pin"></i> SOS';
  }

  function startHold(btn) {
    if (!btn || holdTimer) return;
    holdStartedAt = Date.now();
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-warning');

    holdProgressTimer = setInterval(() => {
      const elapsed = Date.now() - holdStartedAt;
      const leftMs = Math.max(0, HOLD_MS - elapsed);
      const pct = Math.min(100, Math.floor((elapsed / HOLD_MS) * 100));
      btn.style.backgroundImage = `linear-gradient(90deg, rgba(25,135,84,0.45) ${pct}%, transparent ${pct}%)`;
      btn.style.backgroundSize = '100% 100%';
      btn.style.backgroundRepeat = 'no-repeat';
      btn.style.backgroundPosition = 'left center';
      btn.innerHTML = `<i class="bi bi-stopwatch"></i> Hold ${Math.ceil(leftMs / 1000)}s`;
    }, 100);

    holdTimer = setTimeout(async () => {
      clearTimeout(holdTimer);
      holdTimer = null;
      if (holdProgressTimer) {
        clearInterval(holdProgressTimer);
        holdProgressTimer = null;
      }
      resetHoldButton(btn);
      await triggerSOS();
    }, HOLD_MS);
  }

  function cancelHold(btn) {
    if (holdTimer) {
      clearTimeout(holdTimer);
      holdTimer = null;
    }
    if (holdProgressTimer) {
      clearInterval(holdProgressTimer);
      holdProgressTimer = null;
    }
    resetHoldButton(btn);
  }

  function bindHoldToSOSButton(btn) {
    if (!btn) return;
    // Mouse
    btn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      startHold(btn);
    });
    btn.addEventListener('mouseup', () => cancelHold(btn));
    btn.addEventListener('mouseleave', () => cancelHold(btn));
    // Touch
    btn.addEventListener(
      'touchstart',
      (e) => {
        e.preventDefault();
        startHold(btn);
      },
      { passive: false },
    );
    btn.addEventListener('touchend', () => cancelHold(btn));
    btn.addEventListener('touchcancel', () => cancelHold(btn));
    // Prevent instant click
    btn.addEventListener('click', (e) => e.preventDefault());
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindHoldToSOSButton(document.getElementById('btnSOSOneTap'));
    bindHoldToSOSButton(document.getElementById('btnSOSGlobal'));
  });
})();

