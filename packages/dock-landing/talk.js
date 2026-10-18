/* One button: start a browser voice call with Dock (Guava WebRTC orb). Fallback: tel: on phones, number on desktop. */
(function () {
  var btn = document.getElementById("talk");
  var note = document.getElementById("talk-note");
  if (!btn) return;
  function widget() { return document.querySelector("[data-guava-widget]"); }
  function setup() {
    var w = widget();
    if (!w) return null;
    var box = w.parentElement;
    if (box && !box.dataset.dockMoved) {
      box.dataset.dockMoved = "1";
      box.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:2147483647;display:none;";
      var idle = w.querySelector(".gw-caption-idle");
      if (idle) idle.textContent = "Dock";
      new MutationObserver(function () {
        var st = w.getAttribute("data-guava-state") || "idle";
        var live = st !== "idle" && st !== "error";
        btn.textContent = live ? "End call" : "Talk to an agent";
        btn.setAttribute("aria-pressed", live ? "true" : "false");
        if (st === "error") note.textContent = "Couldn't connect from this browser. Call (240) 212-5485 instead.";
        else if (live) note.textContent = "You're talking to Dock. Try: \u201cIt\u2019s LL-88421, this is Dan at Northwind Orchards.\u201d";
      }).observe(w, { attributes: true, attributeFilter: ["data-guava-state"] });
    }
    return w;
  }
  window.addEventListener("load", setup);
  btn.addEventListener("click", function () {
    var w = setup();
    if (!w) {
      if (/Android|iPhone|iPad|Mobile/i.test(navigator.userAgent)) { window.location.href = "tel:+12402125485"; return; }
      note.textContent = "Browser calling didn't load. Call (240) 212-5485 from your phone.";
      return;
    }
    w.parentElement.style.display = "block";
    w.click();
  });
})();
