(function () {
  window.addEventListener('DOMContentLoaded', async () => {
    const box = document.getElementById('alertAd');
    if (!LRAuth.getAccess()) {
      window.location.href = '/login/?next=/admin-panel/';
      return;
    }
    const res = await LRAuth.fetchAuth('/api/emergency/analytics/');
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      box.className = 'alert alert-warning';
      box.textContent = data.detail || JSON.stringify(data);
      box.classList.remove('d-none');
      return;
    }
    document.getElementById('statTotal').textContent = data.total_requests;
    document.getElementById('statSev').textContent = data.average_severity;
    document.getElementById('statByStatus').textContent = JSON.stringify(data.by_status, null, 2);
  });
})();
