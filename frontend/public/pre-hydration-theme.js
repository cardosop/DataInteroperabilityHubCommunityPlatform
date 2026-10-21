(function () {
  try {
    var stored = localStorage.getItem('meshant.theme');
    var pref = stored === 'light' || stored === 'dark' ? stored : 'system';
    var systemDark =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches;
    var resolved = pref === 'system' ? (systemDark ? 'dark' : 'light') : pref;
    document.documentElement.setAttribute('data-theme', resolved);
  } catch (_) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
