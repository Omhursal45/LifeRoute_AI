(function () {
  var root = document.documentElement;
  var key = 'lr_theme';

  function apply(stored) {
    var mode = stored;
    if (!mode) {
      mode = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    root.setAttribute('data-bs-theme', mode);
    var btn = document.getElementById('btnThemeToggle');
    if (btn) {
      btn.textContent = mode === 'dark' ? 'Light' : 'Dark';
    }
  }

  apply(localStorage.getItem(key));

  var toggle = document.getElementById('btnThemeToggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
      localStorage.setItem(key, next);
      apply(next);
    });
  }
})();
