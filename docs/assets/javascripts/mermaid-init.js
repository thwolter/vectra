/* Initialize Mermaid for MkDocs Material */
if (window.mermaid) {
  window.mermaid.initialize({ startOnLoad: true, securityLevel: 'strict' });
}

(function () {
  function renderMermaid() {
    if (!window.mermaid) return;
    try {
      window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
      // Render all diagrams on the current page
      window.mermaid.init(undefined, document.querySelectorAll(".mermaid"));
    } catch (e) {
      console.error("Mermaid init error:", e);
    }
  }

  if (document.readyState !== "loading") renderMermaid();
  else document.addEventListener("DOMContentLoaded", renderMermaid);

  // Re-run on each MkDocs Material page switch
  if (window.document$) {
    window.document$.subscribe(renderMermaid);
  }
})();
