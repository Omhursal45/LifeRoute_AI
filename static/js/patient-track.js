
(function () {
  const HYDERABAD = [17.385, 78.4867];
  let map;
  let patientMarker = null;
  let ambMarker = null;
  let routeLayer = null;
  let lastRouteKm = null;
  let pollTimer = null;
  let lastLat = null;
  let lastLng = null;
  let gpsStarted = false;

  function showAlert(msg, kind) {
    const el = document.getElementById('patientTrackAlert');
    if (!el) return;
    el.className = 'alert alert-' + (kind || 'info');
    el.textContent = msg;
    el.classList.remove('d-none');
  }

  function hideAlert() {
    const el = document.getElementById('patientTrackAlert');
    if (el) el.classList.add('d-none');
  }

  function setBadge(text, cls) {
    const b = document.getElementById('trackStatusBadge');
    if (!b) return;
    b.textContent = text;
    b.className = 'badge ' + (cls || 'bg-secondary');
  }

  async function ensurePatient() {
    if (!LRAuth.getAccess()) {
      window.location.href = '/login/?next=/track/';
      return false;
    }
    const res = await LRAuth.fetchAuth('/api/auth/me/');
    if (!res.ok) {
      window.location.href = '/login/?next=/track/';
      return false;
    }
    const u = await res.json();
    if (u.role !== 'patient') {
      showAlert(
        'This page is for patients only. Log in as patient1 (patient) to see live tracking.',
        'warning',
      );
      setBadge('Not a patient', 'bg-warning text-dark');
      return false;
    }
    return true;
  }

  function ensurePatientMarker(lat, lng) {
    if (!map) return;
    if (patientMarker) {
      patientMarker.setLatLng([lat, lng]);
    } else {
      patientMarker = L.circleMarker([lat, lng], {
        radius: 11,
        color: '#0d6efd',
        weight: 3,
        fillColor: '#9ec5fe',
        fillOpacity: 0.95,
      }).addTo(map);
      patientMarker.bindPopup('You (live GPS)');
    }
  }

  function drawAmbulanceAndRoute(data) {
    if (!map) return;
    const a = data.ambulance;
    if (ambMarker) {
      map.removeLayer(ambMarker);
      ambMarker = null;
    }
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }

    ambMarker = L.circleMarker([a.latitude, a.longitude], {
      radius: 13,
      color: '#b02a37',
      weight: 3,
      fillColor: '#ff6b6b',
      fillOpacity: 0.95,
    }).addTo(map);
    ambMarker.bindPopup(a.vehicle_code || 'Ambulance');

    if (data.route_geometry && data.route_geometry.type) {
      routeLayer = L.geoJSON(data.route_geometry, {
        style: { color: '#0d6efd', weight: 5, opacity: 0.88, dashArray: '10 6' },
      }).addTo(map);
    }

    const group = L.featureGroup([patientMarker, ambMarker].filter(Boolean));
    if (routeLayer) group.addLayer(routeLayer);
    try {
      map.fitBounds(group.getBounds(), { padding: [50, 50], maxZoom: 15 });
    } catch (e) {
    }
  }

  function updateStats(data) {
    const rk = document.getElementById('statRouteKm');
    const lk = document.getElementById('statLineKm');
    const eta = document.getElementById('statEta');
    const closing = document.getElementById('statClosing');

    if (data.distance_route_km != null) {
      rk.textContent = data.distance_route_km + ' km';
      if (lastRouteKm != null && data.distance_route_km < lastRouteKm - 0.01) {
        const closed = (lastRouteKm - data.distance_route_km).toFixed(2);
        closing.textContent = '~' + closed + ' km closer than previous update';
      } else {
        closing.textContent = 'Distance remaining along roads (OSRM)';
      }
      lastRouteKm = data.distance_route_km;
    } else {
      rk.textContent = '—';
      closing.textContent =
        data.routing_available === false ? 'Use HTTPS/localhost for best routing' : 'Waiting for route…';
    }

    lk.textContent =
      data.distance_straight_line_km != null ? data.distance_straight_line_km + ' km' : '—';

    if (data.eta_seconds != null) {
      eta.textContent = Math.round(data.eta_seconds / 60) + ' min';
    } else {
      eta.textContent = '—';
    }
  }

  async function pollTracking() {
    if (lastLat == null || lastLng == null) return;
    const url =
      '/api/emergency/patient/live-tracking/?patient_lat=' +
      encodeURIComponent(lastLat) +
      '&patient_lng=' +
      encodeURIComponent(lastLng);
    const res = await LRAuth.fetchAuth(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setBadge('Error', 'bg-danger');
      showAlert(data.detail || 'Tracking failed', 'danger');
      return;
    }

    hideAlert();

    if (!data.has_active_request) {
      setBadge('No request', 'bg-secondary');
      showAlert(data.message || 'Create an emergency request first.', 'warning');
      return;
    }

    if (!data.has_ambulance) {
      setBadge(data.status || 'Waiting', 'bg-warning text-dark');
      showAlert(data.message || 'Waiting for ambulance assignment.', 'info');
      return;
    }

    setBadge(
      data.status === 'en_route' ? 'En route' : String(data.status || 'Active').replace('_', ' '),
      'bg-success',
    );
    drawAmbulanceAndRoute(data);
    updateStats(data);
  }

  function startGps() {
    if (!navigator.geolocation) {
      showAlert('Geolocation is not available in this browser.', 'danger');
      map.setView(HYDERABAD, 12);
      return;
    }

    navigator.geolocation.watchPosition(
      (pos) => {
        lastLat = pos.coords.latitude;
        lastLng = pos.coords.longitude;
        ensurePatientMarker(lastLat, lastLng);
        if (!gpsStarted) {
          gpsStarted = true;
          map.setView([lastLat, lastLng], 14);
          void pollTracking();
        }
      },
      () => {
        showAlert('Allow location access to see your position and distance to the ambulance.', 'warning');
        map.setView(HYDERABAD, 12);
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 15000 },
    );

    pollTimer = setInterval(() => void pollTracking(), 3500);
  }

  window.addEventListener('DOMContentLoaded', async () => {
    const ok = await ensurePatient();
    if (!ok) return;

    map = L.map('mapPatientTrack').setView(HYDERABAD, 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap',
    }).addTo(map);

    startGps();
  });
})();
