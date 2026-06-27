// ── Przypisanie zdarzeń DOM oraz start aplikacji ──

"use strict";

// Zdarzenia przycisków nawigacji między rodzajami
document.getElementById("seg-gender").addEventListener("click", function (e) {
  var b = e.target.closest("button");
  if (!b) return;
  [].forEach.call(this.querySelectorAll("button"), function (x) { x.setAttribute("aria-pressed", "false"); });
  b.setAttribute("aria-pressed", "true");
  state.g = b.getAttribute("data-g");
  updateHeader();
  render();
});

// Renderowanie z opóźnieniem (debounce) do unikania zacięć podczas interakcji (np. przeciąganie suwaków)
var renderTimer;
function renderDebounced(ms) {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(function () {
    render();
  }, ms || 100);
}

// Zdarzenia synchronizujące suwaki długości imienia
function syncLength() {
  var mn = +lengthMin.value, mx = +lengthMax.value;
  if (mn > mx) {
    if (this === lengthMin) { mx = mn; lengthMax.value = mx; } else { mn = mx; lengthMin.value = mn; }
  }
  state.min = mn; state.max = mx;
  lengthValue.textContent = (mn === mx ? mn + " liter" : mn + "–" + mx + " liter");
  renderDebounced(120);
}
lengthMin.addEventListener("input", syncLength);
lengthMax.addEventListener("input", syncLength);

// Zdarzenia synchronizujące filtry wystąpień w rejestrze
function syncUsageCount() {
  var mn = usageMin.value ? +usageMin.value : 0, mx = usageMax.value ? +usageMax.value : 0;
  state.minUse = mn; state.maxUse = mx;
  usageValue.textContent = mn && mx ? mn + "–" + formatNumber(mx) : mn ? "od " + formatNumber(mn) : mx ? "do " + formatNumber(mx) : "dowolnie";
  renderDebounced(150);
}
usageMin.addEventListener("change", syncUsageCount);
usageMin.addEventListener("input", syncUsageCount);
usageMax.addEventListener("change", syncUsageCount);
usageMax.addEventListener("input", syncUsageCount);

// Zdarzenia zmiany pochodzenia
originSelect.addEventListener("change", function () {
  state.origin = this.value;
  render();
});

// Wyszukiwarka z opóźnieniem (debounce)
var searchTimer;
searchInput.addEventListener("input", function () {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(function () {
    state.q = searchInput.value;
    render();
  }, 140);
});

// Zdarzenia dla przycisku włączającego tryb Regex
regexToggle.addEventListener("click", function () {
  state.regex = !state.regex;
  regexToggle.setAttribute("aria-pressed", state.regex ? "true" : "false");
  searchInput.placeholder = state.regex ? "np. ^A, a$, [aeiou]{2}…" : "np. Ala, Zof, mar…";
  render();
});

// Przełącznik ulubionych
favToggle.addEventListener("click", function () {
  state.fav = !state.fav;
  favToggle.setAttribute("aria-pressed", state.fav ? "true" : "false");
  var starSpan = favToggle.querySelector(".fav-star");
  if (starSpan) {
    starSpan.textContent = state.fav ? "★" : "☆";
  }
  render();
});

// Modal pomocy regex
regexHelpButton.addEventListener("click", function (e) {
  e.stopPropagation();
  regexHelp.classList.toggle("open");
});
document.addEventListener("click", function (e) {
  if (!regexHelp.contains(e.target) && e.target !== regexHelpButton) regexHelp.classList.remove("open");
});

// Obsługa klawiatury dla dostępności nagłówków tabeli
function isActionKey(e) { return e.key === "Enter" || e.key === " " || e.key === "Spacebar"; }
headerRow.addEventListener("keydown", function (e) {
  if (!isActionKey(e)) return;
  var th = e.target.closest("th[data-key]"); if (!th) return;
  e.preventDefault(); th.click();
});

// Obsługa klawiatury dla wierszy tabeli (rozwijanie szczegółów na "Enter")
tableBody.addEventListener("keydown", function (e) {
  if (!isActionKey(e)) return;
  if (e.target.closest("a")) return;
  var tr = e.target.closest("tr.main"); if (!tr) return;
  e.preventDefault(); tr.click();
});

// Sortowanie przy kliknięciu w poszczególne kolumny
headerRow.addEventListener("click", function (e) {
  var th = e.target.closest("th[data-key]"); if (!th) return;
  var k = th.getAttribute("data-key");
  if (state.sort === k) state.dir *= -1;
  else { state.sort = k; state.dir = (k === "imie" || k === "pochodzenie") ? 1 : -1; }
  randomOffset = 0;
  render();
});

// Rozwijanie panelu detali przy kliknięciu na rekord
tableBody.addEventListener("click", function (e) {
  var x = e.target.closest("a.xref");
  if (x) { e.preventDefault(); goToName(x.getAttribute("data-imie")); return; }
  
  var favBtn = e.target.closest(".fav-btn");
  if (favBtn) {
    e.preventDefault();
    e.stopPropagation();
    var nm = favBtn.getAttribute("data-fav-imie");
    toggleFavorite(nm);
    render();
    return;
  }
  
  var tr = e.target.closest("tr.main"); if (!tr) return;
  var i = tr.getAttribute("data-i");
  var det = tableBody.querySelector('tr.detail[data-d="' + i + '"]');
  var open = tr.getAttribute("aria-expanded") === "true";
  
  tr.setAttribute("aria-expanded", open ? "false" : "true");
  if (det) {
    var inner = det.querySelector(".detail-inner");
    if (open) {
      inner.setAttribute("aria-hidden", "true");
      det.classList.remove("open");
    } else {
      inner.removeAttribute("aria-hidden");
      det.classList.add("open");
      if (det.querySelector('[data-opis-imie]')) {
        var nm = tr.getAttribute("data-imie");
        ensureDescription(nm, function () { fillDescription(det, nm); });
      }
      setTimeout(function () {
        var pad = det.querySelector(".detail-pad");
        if (pad) { pad.setAttribute("tabindex", "-1"); pad.focus(); }
        
        // Upewnij się, że cały rozwinięty panel szczegółów jest widoczny na ekranie
        var rect = det.getBoundingClientRect();
        var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        if (rect.bottom > viewportHeight) {
          var scrollOffset = rect.bottom - viewportHeight + 24; // 24px marginesu na dole
          window.scrollBy({ top: scrollOffset, behavior: "smooth" });
        }
      }, 300);
    }
  }
});

// Dymki na grafice SVG (wykres występowania imienia)
var trendTooltip = document.createElement("div");
trendTooltip.className = "trend-tip";
trendTooltip.style.display = "none";
document.body.appendChild(trendTooltip);
var trendCursor = null;

function hideTrendTooltip() {
  trendTooltip.style.display = "none";
  if (trendCursor) { trendCursor.style.display = "none"; trendCursor = null; }
}

function placeTrendTooltip(e) {
  var below = e.clientY < 80;
  trendTooltip.style.left = e.clientX + "px";
  trendTooltip.style.top = (e.clientY + (below ? 16 : -10)) + "px";
  trendTooltip.style.transform = below ? "translate(-50%,0)" : "translate(-50%,-100%)";
}

tableBody.addEventListener("mousemove", function (e) {
  var svg = e.target.closest(".trend-svg");
  if (!svg) {
    return;
  }
  
  var rect = svg.getBoundingClientRect();
  var mouseX = e.clientX - rect.left;
  var svgX = (mouseX / rect.width) * 560; // Skalowanie do viewBox width (560)
  
  var hits = svg.querySelectorAll(".trend-hit");
  if (!hits.length) return;
  
  // Znajdź najbliższy punkt na osi X
  var closestHit = null;
  var minDistance = Infinity;
  for (var j = 0; j < hits.length; j++) {
    var hit = hits[j];
    var cx = parseFloat(hit.getAttribute("cx"));
    var dist = Math.abs(cx - svgX);
    if (dist < minDistance) {
      minDistance = dist;
      closestHit = hit;
    }
  }
  
  if (closestHit) {
    var cx = parseFloat(closestHit.getAttribute("cx"));
    var cy = parseFloat(closestHit.getAttribute("cy"));
    var year = closestHit.getAttribute("data-y");
    var val = closestHit.getAttribute("data-v");
    
    trendTooltip.innerHTML = '<b>' + val + '</b><span>' + year + '</span>';
    trendTooltip.style.display = "";
    placeTrendTooltip(e);
    
    var cursor = svg.querySelector(".trend-cursor");
    if (cursor) {
      cursor.setAttribute("cx", cx.toFixed(1));
      cursor.setAttribute("cy", cy.toFixed(1));
      cursor.style.display = "";
      trendCursor = cursor;
    }
    
    var vLine = svg.querySelector(".trend-v-line");
    if (vLine) {
      vLine.setAttribute("x1", cx.toFixed(1));
      vLine.setAttribute("x2", cx.toFixed(1));
      vLine.style.display = "";
    }
  }
});

tableBody.addEventListener("mouseout", function (e) {
  var svg = e.target.closest(".trend-svg");
  if (!svg) return;
  
  var related = e.relatedTarget;
  if (related && related.closest && related.closest(".trend-svg") === svg) {
    return; // Nadal w obrębie tego samego SVG
  }
  
  hideTrendTooltip();
  var cursor = svg.querySelector(".trend-cursor");
  if (cursor) cursor.style.display = "none";
  var vLine = svg.querySelector(".trend-v-line");
  if (vLine) vLine.style.display = "none";
});

// Zdarzenia układu paginacji i losowania imienia
randomButton.addEventListener("click", function () {
  var all = getSortedFiltered();
  if (!all.length) return;
  var randomIndex = Math.floor(Math.random() * all.length);
  randomHighlight = all[randomIndex];
  
  render(false, true);
  
  setTimeout(function () {
    var rows = tableBody.querySelectorAll('tr.main');
    var tr = rows[0];
    if (tr) {
      tr.scrollIntoView({ behavior: "smooth", block: "center" });
      if (tr.getAttribute("aria-expanded") !== "true") tr.click();
    }
  }, 40);
});

// Nawigacja "Do góry"
addEventListener("scroll", function () { backToTopButton.style.display = scrollY > 500 ? "block" : "none"; });
backToTopButton.addEventListener("click", function () { scrollTo({ top: 0, behavior: "smooth" }); });

// Pomoc i ściąga funkcji (Help Card)
if (helpCardToggle && helpCardContent) {
  helpCardToggle.addEventListener("click", function() {
    var open = helpCardContent.classList.toggle("open");
    helpCardToggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (helpCardArrow) {
      helpCardArrow.style.transform = open ? "rotate(180deg)" : "rotate(0deg)";
    }
  });
}

// ── Inicjalizacja Infinite Scroll ──
if ('IntersectionObserver' in window) {
  var observer = new IntersectionObserver(function(entries) {
    if (entries[0].isIntersecting) {
      var allLength = currentFilteredLength;
      if (currentLimit < allLength) {
        currentLimit += PER_PAGE;
        render(true); // renderuj z nowym limitem
      }
    }
  }, { rootMargin: "200px" });
  observer.observe(loadingTrigger);
}

// ── Inicjalizacja Aplikacji ──
(function init() {
  loadState();

  var genderButton = document.getElementById("seg-gender").querySelector('[data-g="' + state.g + '"]');
  if (genderButton) {
    [].forEach.call(document.getElementById("seg-gender").querySelectorAll("button"), function (x) { x.setAttribute("aria-pressed", "false"); });
    genderButton.setAttribute("aria-pressed", "true");
  }

  lengthMin.value = state.min;
  lengthMax.value = state.max;
  lengthValue.textContent = (state.min === state.max ? state.min + " liter" : state.min + "–" + state.max + " liter");

  usageMin.value = state.minUse || "";
  usageMax.value = state.maxUse || "";
  usageValue.textContent = state.minUse && state.maxUse ? state.minUse + "–" + formatNumber(state.maxUse) : state.minUse ? "od " + formatNumber(state.minUse) : state.maxUse ? "do " + formatNumber(state.maxUse) : "dowolnie";

  if (state.q) searchInput.value = state.q;
  if (state.regex) { regexToggle.setAttribute("aria-pressed", "true"); searchInput.placeholder = "np. ^A, a$, [aeiou]{2}…"; }
  if (state.fav) { 
    favToggle.setAttribute("aria-pressed", "true"); 
    var starSpan = favToggle.querySelector(".fav-star");
    if (starSpan) starSpan.textContent = "★";
  }

  updateHeader();
  render();
})();
