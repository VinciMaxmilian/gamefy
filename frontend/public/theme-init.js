// Runs before first paint (external file so the CSP can stay `script-src 'self'`).
// Keep in sync with src/lib/theme.tsx.
(function () {
  var mode = "dark"; // dark is the default
  try { mode = localStorage.getItem("gf_theme") || "dark"; } catch (e) {}
  var dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  var el = document.documentElement;
  el.setAttribute("data-theme", dark ? "dark" : "light");
  var m = document.querySelector('meta[name="theme-color"]');
  if (m) m.setAttribute("content", dark ? "#000000" : "#f5f5f7");
})();
