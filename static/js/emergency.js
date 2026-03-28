(function () {
  document.getElementById('btnGeo')?.addEventListener('click', () => {
    if (!navigator.geolocation) {
      alert('Geolocation not supported');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        document.getElementById('lat').value = pos.coords.latitude.toFixed(6);
        document.getElementById('lon').value = pos.coords.longitude.toFixed(6);
      },
      () => alert('Could not read location'),
    );
  });

  document.getElementById('formEmergency')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const box = document.getElementById('alertEm');
    const out = document.getElementById('resultBox');
    box.classList.add('d-none');
    if (!LRAuth.getAccess()) {
      window.location.href = '/login/?next=/emergency/';
      return;
    }
    const body = {
      latitude: parseFloat(document.getElementById('lat').value),
      longitude: parseFloat(document.getElementById('lon').value),
      location_description: document.getElementById('locDesc').value,
      symptoms: document.getElementById('symptoms').value,
    };
    const us = document.getElementById('userSev').value;
    const payload = { ...body };
    if (us) payload.user_severity = parseInt(us, 10);

    const res = await LRAuth.fetchAuth('/api/emergency/requests/', {
      method: 'POST',
      body: payload,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      box.className = 'alert alert-danger';
      box.textContent = JSON.stringify(data);
      box.classList.remove('d-none');
      return;
    }
    box.className = 'alert alert-success';
    box.textContent = 'Request created. Check suggested hospital and route metrics below.';
    box.classList.remove('d-none');
    out.classList.remove('d-none');
    out.textContent = JSON.stringify(data, null, 2);
  });
})();
