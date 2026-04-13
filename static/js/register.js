(() => {
  function flattenError(data) {
    if (!data || typeof data !== 'object') return '';
    const vals = Object.values(data).flat();
    return vals.map((v) => (typeof v === 'string' ? v : JSON.stringify(v))).join(' ');
  }

  function showBox(box, kind, message) {
    box.className = `alert alert-${kind} d-flex align-items-center gap-2`;
    box.textContent = message;
    box.classList.remove('d-none');
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formReg');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const box = document.getElementById('alertReg');
      const btn = document.getElementById('btnRegSubmit');
      const btnText = document.getElementById('btnText');
      const btnLoader = document.getElementById('btnLoader');
      const password = document.getElementById('password').value;
      const passwordConfirm = document.getElementById('password2').value;

      if (password !== passwordConfirm) {
        showBox(box, 'warning', 'Passwords do not match.');
        return;
      }

      box.classList.add('d-none');
      btn.disabled = true;
      btnText.classList.add('d-none');
      btnLoader.classList.remove('d-none');

      const body = {
        username: document.getElementById('username').value.trim(),
        email: document.getElementById('email').value.trim(),
        phone: document.getElementById('phone').value.trim(),
        role: document.querySelector('input[name="role"]:checked').value,
        password: password,
        password_confirm: passwordConfirm,
      };

      try {
        const res = await fetch('/api/auth/register/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg = flattenError(data) || res.statusText || 'Signup failed';
          throw new Error(msg);
        }

        showBox(box, 'success', 'Account created successfully. Please sign in.');
        window.setTimeout(() => {
          const nextUrl = '/login/?username=' + encodeURIComponent(body.username);
          window.location.href = nextUrl;
        }, 900);
      } catch (err) {
        btn.disabled = false;
        btnText.classList.remove('d-none');
        btnLoader.classList.add('d-none');
        showBox(box, 'danger', err.message || 'Could not create account.');
      }
    });
  });
})();

