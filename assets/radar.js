// =========================================================================
// Radar SVG injection + détection du thème système au premier chargement.
// Le SVG est injecté en JS car dash.html ne fournit pas de wrappers pour
// les balises SVG natives dans cette version de Dash.
// =========================================================================

(function () {
  const RADAR_SVG = `
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
      <circle class="scan-ring" cx="100" cy="100" r="90" />
      <circle class="scan-ring" cx="100" cy="100" r="62" />
      <circle class="scan-ring" cx="100" cy="100" r="34" />
      <g class="scan-sweep">
        <path d="M 100 100 L 100 10 A 90 90 0 0 1 163 37 Z"
              fill="url(#sweepGradient)" opacity="0.55" />
      </g>
      <defs>
        <linearGradient id="sweepGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="var(--accent-copper)" stop-opacity="0.9" />
          <stop offset="100%" stop-color="var(--accent-copper)" stop-opacity="0" />
        </linearGradient>
      </defs>
      <circle class="scan-dot" cx="100" cy="100" r="4" />
    </svg>
  `;

  function injectRadar() {
    const mount = document.getElementById("radar-svg-mount");
    if (mount && !mount.dataset.injected) {
      mount.innerHTML = RADAR_SVG;
      mount.dataset.injected = "true";
    }
  }

  function applyInitialTheme() {
    const html = document.documentElement;
    if (!html.getAttribute("data-theme")) {
      const prefersDark = window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;
      html.setAttribute("data-theme", prefersDark ? "dark" : "dark");
      // NB: on démarre toujours en mode sombre par défaut (identité du produit),
      // l'utilisateur peut basculer en clair via le bouton de la topbar.
    }
  }

  applyInitialTheme();

  // Ré-injecte le radar chaque fois que le DOM est mis à jour par Dash
  // (l'écran de scan peut être remonté plusieurs fois pendant le polling).
  const observer = new MutationObserver(injectRadar);
  observer.observe(document.body, { childList: true, subtree: true });

  document.addEventListener("DOMContentLoaded", injectRadar);
  injectRadar();
})();