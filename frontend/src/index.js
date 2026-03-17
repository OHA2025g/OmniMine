import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

function removeEmergentBranding() {
  const badge = document.getElementById("emergent-badge");
  if (badge) badge.remove();

  // In case something injects it later (cached script / extension), keep removing.
  const observer = new MutationObserver(() => {
    const injected = document.getElementById("emergent-badge");
    if (injected) injected.remove();
  });

  // Body may not exist yet in some load orders
  const target = document.body || document.documentElement;
  observer.observe(target, { childList: true, subtree: true });
}

removeEmergentBranding();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
