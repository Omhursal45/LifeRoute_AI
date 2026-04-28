const LRAuth = {
  accessKey: 'lr_access',
  refreshKey: 'lr_refresh',

  getAccess() {
    return sessionStorage.getItem(this.accessKey);
  },
  getRefresh() {
    return sessionStorage.getItem(this.refreshKey);
  },
  setTokens(access, refresh) {
    sessionStorage.setItem(this.accessKey, access);
    if (refresh) sessionStorage.setItem(this.refreshKey, refresh);
  },
  clear() {
    sessionStorage.removeItem(this.accessKey);
    sessionStorage.removeItem(this.refreshKey);
  },

  async login(username, password) {
    const res = await fetch('/api/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.non_field_errors?.join(' ') || JSON.stringify(data);
      throw new Error(msg);
    }
    this.setTokens(data.access, data.refresh);
    try {
      const me = await fetch('/api/auth/me/', {
        headers: { Authorization: `Bearer ${data.access}` },
      });
      if (me.ok) {
        const u = await me.json();
        sessionStorage.setItem('lr_me', JSON.stringify({ role: u.role, username: u.username }));
      }
    } catch (e) {
    }
    return data;
  },

  async refreshAccess() {
    const r = this.getRefresh();
    if (!r) throw new Error('No refresh token');
    const res = await fetch('/api/auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: r }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      this.clear();
      throw new Error(data.detail || 'Session expired');
    }
    this.setTokens(data.access, this.getRefresh());
    return data.access;
  },

  async fetchAuth(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    let token = this.getAccess();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    let res = await fetch(url, { ...options, headers });
    if (res.status === 401 && this.getRefresh()) {
      try {
        await this.refreshAccess();
        headers.Authorization = `Bearer ${this.getAccess()}`;
        res = await fetch(url, { ...options, headers });
      } catch (_) {
      }
    }
    return res;
  },
};

document.addEventListener('DOMContentLoaded', () => {
  const loginLink = document.getElementById('navLogin');
  const joinLink = document.getElementById('navJoin');
  const adminItem = document.getElementById('navItemAdmin');

  if (loginLink && LRAuth.getAccess()) {
    loginLink.textContent = 'Logout';
    loginLink.href = '#';
    loginLink.addEventListener('click', (e) => {
      e.preventDefault();
      LRAuth.clear();
      sessionStorage.removeItem('lr_me');
      window.location.href = '/';
    });
    if (joinLink) joinLink.classList.add('d-none');

    LRAuth.fetchAuth('/api/auth/me/')
      .then((res) => (res.ok ? res.json() : null))
      .then((u) => {
        if (!u) return;
        sessionStorage.setItem(
          'lr_me',
          JSON.stringify({
            role: u.role,
            username: u.username,
            is_staff: !!u.is_staff,
            is_superuser: !!u.is_superuser,
          }),
        );
        if (adminItem && (u.is_staff || u.is_superuser)) {
          adminItem.classList.remove('d-none');
        }
      })
      .catch(() => {});
  }
});
