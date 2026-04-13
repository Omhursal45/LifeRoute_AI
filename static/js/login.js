(() => {
  function showBox(box, kind, message) {
    box.className = `alert alert-${kind} d-flex align-items-center gap-2`;
    box.textContent = message;
    box.classList.remove('d-none');
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formLogin');
    if (!form) return;
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');

    try {
      const params = new URLSearchParams(window.location.search);
      const u = params.get('username');
      if (u && usernameInput) {
        usernameInput.value = u;
        if (passwordInput) passwordInput.focus();
      }
    } catch (e) {
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const box = document.getElementById('alertLogin');
      const btn = document.getElementById('btnLoginSubmit');
      const btnText = document.getElementById('btnText');
      const btnLoader = document.getElementById('btnLoader');
      const username = usernameInput.value.trim();
      const password = passwordInput.value;

      box.classList.add('d-none');
      btn.disabled = true;
      btnText.classList.add('d-none');
      btnLoader.classList.remove('d-none');

      try {
        await LRAuth.login(username, password);
        showBox(box, 'success', 'Authenticated. Redirecting...');
        window.setTimeout(() => {
          window.location.href = '/dashboard/';
        }, 600);
      } catch (err) {
        btn.disabled = false;
        btnText.classList.remove('d-none');
        btnLoader.classList.add('d-none');
        showBox(box, 'danger', err.message || 'Invalid username or password');
      }
    });
  });
})();

