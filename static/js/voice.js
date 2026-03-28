
(function () {
  document.getElementById('btnVoice')?.addEventListener('click', () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition not supported in this browser.');
      return;
    }
    const rec = new SpeechRecognition();
    rec.lang = document.documentElement.lang || 'en-US';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (ev) => {
      const text = ev.results[0][0].transcript;
      const ta = document.getElementById('symptoms');
      if (ta) {
        ta.value = (ta.value ? `${ta.value.trim()} ` : '') + text;
      }
    };
    rec.onerror = () => alert('Voice capture error');
    rec.start();
  });
})();
