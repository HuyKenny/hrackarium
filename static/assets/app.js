/* hrackarium.cz — search, listing filters, gallery, consent + GTM/GA4 click events. No dependencies, no tracking without consent. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var cache = {};
  function getJSON(u) {
    if (!cache[u]) cache[u] = fetch(u).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
    return cache[u];
  }
  function kc(n) { return Math.round(n).toLocaleString("cs-CZ").replace(/\s/g, " ") + " Kč"; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fold(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }
  function words(q) { return fold(q).split(/[^a-z0-9]+/).filter(function (w) { return w.length > 1; }); }
  function shopsIn(n) { return n === 1 ? "v 1 obchodě" : (n < 5 ? "ve " : "v ") + n + " obchodech"; }

  /* ---------- broken shop images -> our placeholder ---------- */
  function fixImg(im) { if (im.tagName === "IMG" && !im.dataset.f && im.src.indexOf(location.host) < 0) { im.dataset.f = "1"; im.src = "/img/ui/placeholder.svg"; } }
  document.addEventListener("error", function (e) { fixImg(e.target); }, true);
  $$("img").forEach(function (im) { if (im.complete && !im.naturalWidth && im.getAttribute("loading") !== "lazy") fixImg(im); });

  /* ---------- product search over the 2-letter buckets ---------- */
  function searchProducts(q, limit) {
    var ws = words(q);
    if (!ws.length) return Promise.resolve([]);
    var key = ws.slice().sort(function (a, b) { return b.length - a.length; })[0].slice(0, 2);
    return getJSON("/data/s/" + key + ".json").then(function (rows) {
      var out = [];
      for (var i = 0; i < rows.length && out.length < limit; i++) {
        var n = fold(rows[i][0]), ok = true;
        for (var j = 0; j < ws.length; j++) if (n.indexOf(ws[j]) < 0) { ok = false; break; }
        if (ok) out.push(rows[i]);
      }
      return out;
    }).catch(function () { return []; });
  }

  var sInput = $("#q"), sBox = $("#sugg");
  if (sInput) {
    var sug = null, sel = -1, hits = [], tmr;
    var loadSug = function () { if (!sug) getJSON("/data/sug.json").then(function (d) { sug = d.map(function (x) { return [fold(x[0]), x]; }); }); };
    var run = function () {
      var q = sInput.value.trim();
      if (q.length < 2) { sBox.style.display = "none"; return; }
      var ws = words(q), cats = [];
      if (sug) for (var i = 0; i < sug.length && cats.length < 5; i++) {
        var ok = ws.length > 0;
        for (var j = 0; j < ws.length; j++) if (sug[i][0].indexOf(ws[j]) < 0) { ok = false; break; }
        if (ok) cats.push({ t: sug[i][1][0], u: sug[i][1][1], s: sug[i][1][2] });
      }
      searchProducts(q, 7).then(function (rows) {
        hits = cats.concat(rows.map(function (r) { return { t: r[0], u: "/produkt/" + r[1] + "/", s: (r[3] > 1 ? "od " : "") + kc(r[2]), img: r[4] }; }));
        hits.push({ t: "Hledat „" + q + "“ ve všech hračkách", u: "/hledat/?q=" + encodeURIComponent(q), s: "" });
        sel = -1;
        sBox.innerHTML = hits.map(function (h, i) {
          return '<a href="' + h.u + '" role="option">' + (h.img ? '<img src="' + esc(h.img) + '" alt="" loading="lazy">' : "") + "<span>" + esc(h.t) + "</span><small>" + esc(h.s) + "</small></a>";
        }).join("");
        sBox.style.display = "block";
      });
    };
    sInput.addEventListener("focus", loadSug);
    sInput.addEventListener("input", function () { loadSug(); clearTimeout(tmr); tmr = setTimeout(run, 120); });
    sInput.addEventListener("keydown", function (e) {
      var links = $$("a", sBox);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); sel = Math.max(0, Math.min(links.length - 1, sel + (e.key === "ArrowDown" ? 1 : -1)));
        links.forEach(function (a, i) { a.classList.toggle("on", i === sel); });
      } else if (e.key === "Enter" && sel >= 0 && hits[sel]) { e.preventDefault(); location.href = hits[sel].u; }
      else if (e.key === "Escape") sBox.style.display = "none";
    });
    document.addEventListener("click", function (e) { if (!e.target.closest(".search")) sBox.style.display = "none"; });
  }

  /* ---------- /hledat/ page ---------- */
  var sres = $("#sres");
  if (sres) {
    var q = new URLSearchParams(location.search).get("q") || "";
    if (sInput) sInput.value = q;
    if (q) searchProducts(q, 96).then(function (rows) {
      $("#sq").textContent = rows.length ? "Výsledky pro „" + q + "“" + (rows.length >= 96 ? " (prvních 96)" : ": " + rows.length) : "Pro „" + q + "“ jsme nic nenašli. Zkuste kratší slovo nebo značku.";
      sres.innerHTML = rows.map(function (r) { return card([r[0], r[1], r[4], r[2], r[3], -1, -1, "", 0, []], []); }).join("");
    });
  }

  /* ---------- listing filters ---------- */
  function card(it, brands) {
    var age = it[6] >= 0 ? '<span class="sticker">' + (it[6] < 12 ? (it[6] ? it[6] + "+ m" : "0+") : Math.floor(it[6] / 12) + "+") + "</span>" : "";
    var sale = it[8] >= 10 ? '<span class="flag">−' + it[8] + " %</span>" : "";
    var brand = it[5] >= 0 && brands[it[5]] ? '<span class="pc__brand">' + esc(brands[it[5]]) + "</span>" : "";
    var href = "/produkt/" + it[1] + "/";
    return '<li class="pc"><a class="pc__img" href="' + href + '" tabindex="-1" aria-hidden="true"><img src="' + esc(it[2] || "/img/ui/placeholder.svg") + '" alt="" loading="lazy" width="220" height="220">' + sale + age + "</a>" +
      '<div class="pc__b">' + brand + '<h3><a href="' + href + '">' + esc(it[0]) + '</a></h3><div class="pc__f"><span class="ptag"><i></i>' + (it[4] > 1 ? "<small>od</small>" : "") + kc(it[3]) + "</span>" +
      '<span class="pc__n">' + shopsIn(it[4]) + "</span></div></div></li>";
  }
  var list = $("#plist"), form = $("#filters");
  if (list && form) {
    var data = null, shown = 36, sortSel = $("#sort"), count = $("#count"), pager = $(".pager"), reset = $(".freset", form);
    var active = function () {
      var f = { age: [], brand: [], shop: [], multi: false, sale: false, pmin: 0, pmax: 0 };
      $$("input[type=checkbox]:checked", form).forEach(function (c) { if (Array.isArray(f[c.name])) f[c.name].push(c.value); else f[c.name] = true; });
      f.pmin = +form.pmin.value || 0; f.pmax = +form.pmax.value || 0;
      return f;
    };
    var isDefault = function (f) { return !f.age.length && !f.brand.length && !f.shop.length && !f.multi && !f.sale && !f.pmin && !f.pmax && sortSel.value === (list.dataset.order || "pop"); };
    var apply = function () {
      var f = active();
      if (isDefault(f) && !data) return;
      (data ? Promise.resolve(data) : getJSON(list.dataset.json)).then(function (d) {
        data = d;
        var items = d.i.filter(function (it) {
          if (f.multi && it[4] < 2) return false;
          if (f.sale && it[8] < 10) return false;
          if (f.pmin && it[3] < f.pmin) return false;
          if (f.pmax && it[3] > f.pmax) return false;
          if (f.brand.length && f.brand.indexOf(String(it[5])) < 0) return false;
          if (f.shop.length && !it[9].some(function (s) { return f.shop.indexOf(s) >= 0; })) return false;
          if (f.age.length && !f.age.some(function (r) { var a = r.split("-"); return it[6] >= +a[0] && it[6] <= +a[1]; })) return false;
          return true;
        });
        var s = sortSel.value;
        if (s === "price") items.sort(function (a, b) { return a[3] - b[3]; });
        else if (s === "pricedesc") items.sort(function (a, b) { return b[3] - a[3]; });
        else if (s === "sale") items.sort(function (a, b) { return b[8] - a[8]; });
        count.textContent = items.length;
        var def = isDefault(f);
        if (pager) pager.style.display = def ? "" : "none";
        reset.hidden = def;
        if (def) { location.reload(); return; }
        list.innerHTML = items.length ? items.slice(0, shown).map(function (it) { return card(it, d.b); }).join("") :
          '<li class="empty"><img src="/img/ui/404.webp" alt="" width="260" height="192"><p>Takovou kombinaci nemáme. Zkuste uvolnit filtry.</p></li>';
        var more = $("#lmore");
        if (items.length > shown) {
          if (!more) { more = document.createElement("p"); more.id = "lmore"; more.style.textAlign = "center"; more.innerHTML = '<button class="btn btn--g" type="button">Načíst další</button>'; list.after(more); }
          more.firstChild.onclick = function () { shown += 36; apply(); };
        } else if (more) more.remove();
      });
    };
    form.addEventListener("change", function () { shown = 36; apply(); });
    sortSel && sortSel.addEventListener("change", function () { shown = 36; apply(); });
    $$(".fquick button", form).forEach(function (b) {
      b.addEventListener("click", function () { form.pmax.value = b.classList.contains("on") ? "" : b.dataset.pmax; $$(".fquick button", form).forEach(function (x) { x.classList.toggle("on", x === b && form.pmax.value); }); apply(); });
    });
    reset.addEventListener("click", function () { form.reset(); sortSel.value = list.dataset.order || "pop"; location.reload(); });
    var fs = $(".fsearch", form);
    fs && fs.addEventListener("input", function () { var w = fold(fs.value); $$(".flinks label", form).forEach(function (l) { l.style.display = fold(l.textContent).indexOf(w) >= 0 ? "" : "none"; }); });
    var tg = $(".ftoggle"), close = $(".fclose", form);
    tg && tg.addEventListener("click", function () { form.classList.add("open"); document.body.style.overflow = "hidden"; });
    close && close.addEventListener("click", function () { form.classList.remove("open"); document.body.style.overflow = ""; });
  }

  /* ---------- product page ---------- */
  var gm = $("#gmain");
  $$(".thumbs button").forEach(function (b) {
    b.addEventListener("click", function () { gm.src = b.dataset.src; $$(".thumbs button").forEach(function (x) { x.classList.toggle("on", x === b); }); });
  });
  $$("[data-more]").forEach(function (b) {
    var el = document.getElementById(b.dataset.more);
    if (el && el.scrollHeight <= el.clientHeight + 10) { el.classList.remove("clamp"); b.remove(); return; }
    b.addEventListener("click", function () { el.classList.remove("clamp"); b.remove(); });
  });

  /* ---------- consent: Consent Mode v2 (GTM itself is in the page head, see render.py; here only the update) ---------- */
  var ga = document.querySelector('meta[name="ga4"]'), cbar = $("#consent"), granted = false;
  window.dataLayer = window.dataLayer || [];
  function setConsent(yes) {
    if (!ga) return;
    granted = yes;
    if (window.gtag) window.gtag("consent", "update", { analytics_storage: yes ? "granted" : "denied" });
  }
  var c = store("hrk-consent");
  if (c === "yes") granted = true; else if (!c && ga && cbar) cbar.hidden = false;
  $$("[data-consent]").forEach(function (b) {
    b.addEventListener("click", function () { store("hrk-consent", b.dataset.consent); cbar.hidden = true; setConsent(b.dataset.consent === "yes"); });
  });
  var co = $("#consent-open");
  co && co.addEventListener("click", function (e) { e.preventDefault(); if (cbar) cbar.hidden = false; });
  document.addEventListener("click", function (e) {
    var a = e.target.closest("a[data-go]");
    if (a && ga) {
      var d = { shop: a.dataset.go, from_path: location.pathname, transport_type: "beacon" };
      if (ga.content.indexOf("GTM-") === 0) { d.event = "click_shop"; window.dataLayer.push(d); }
      else if (window.gtag) window.gtag("event", "click_shop", d);
    }
  });
})();
