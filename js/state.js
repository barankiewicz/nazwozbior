// ── Zarządzanie stanem i nawigacją URL ──

"use strict";

// Bieżący indeks strony paginacji
var currentPage = 0;

// Czy wyświetlać wszystkie wyniki jednocześnie (bez paginacji)
var showAll = false;

// Offset wygenerowany przy losowaniu imienia
var randomOffset = 0;

// Główny obiekt stanu filtrów, wyszukiwania i sortowania
var state = {
  g: "z",                  // wybrany rodzaj imienia (m, z, uni, nb, all)
  min: 2,                  // minimalna długość
  max: 35,                 // maksymalna długość
  minUse: 0,               // minimalna liczba wystąpień
  maxUse: 0,               // maksymalna liczba wystąpień
  origin: "all",           // pochodzenie imienia
  q: "",                   // fraza wyszukiwania
  sort: "wystapienia_pierwsze", // kolumna sortowania
  dir: -1,                 // kierunek sortowania (-1 malejąco, 1 rosnąco)
  regex: false,            // czy wyszukiwać za pomocą wyrażeń regularnych (regex)
  fav: false               // czy pokazywać tylko ulubione
};

// Zbiór ulubionych imion (przechowywany w localStorage)
var favorites = new Set();
try {
  var storedFavs = JSON.parse(localStorage.getItem("nazwozbior-favs") || "[]");
  storedFavs.forEach(function(f) { favorites.add(f); });
} catch (e) {
  console.error("Błąd odczytu ulubionych z localStorage", e);
}

// Przełącza status ulubionego dla danego imienia
function toggleFavorite(name) {
  var lower = name.toLowerCase();
  if (favorites.has(lower)) {
    favorites.delete(lower);
  } else {
    favorites.add(lower);
  }
  try {
    localStorage.setItem("nazwozbior-favs", JSON.stringify(Array.from(favorites)));
  } catch (e) {}
}

// Odczyt stanu z parametrów URL (Query String)
function loadState() {
  var p = new URLSearchParams(location.search);
  if (p.has("gender")) {
    var v = p.get("gender");
    if (v === "m" || v === "z" || v === "all" || v === "uni" || (v === "nb" && nonbinaryNames.length)) {
      state.g = v;
    }
  }
  if (p.has("min")) {
    var n = +p.get("min");
    if (n >= 1 && n <= 20) state.min = n;
  }
  if (p.has("max")) {
    var n = +p.get("max");
    if (n >= 1 && n <= 35) state.max = n;
  }
  if (p.has("minu")) {
    var n = +p.get("minu");
    if (n >= 0) state.minUse = n;
  }
  if (p.has("maxu")) {
    var n = +p.get("maxu");
    if (n >= 0) state.maxUse = n;
  }
  if (p.has("origin")) state.origin = p.get("origin");
  if (p.has("q")) state.q = p.get("q");
  if (p.has("sort")) state.sort = p.get("sort");
  if (p.has("dir")) {
    var d = +p.get("dir");
    if (d === 1 || d === -1) state.dir = d;
  }
  if (p.has("regex")) state.regex = p.get("regex") === "1";
  if (p.has("fav")) state.fav = p.get("fav") === "1";
}

// Zapis aktualnego stanu filtrów do URL (Query String) bez przeładowania strony
function saveState() {
  var p = new URLSearchParams();
  if (state.g !== "z") p.set("gender", state.g);
  if (state.min !== 2) p.set("min", state.min);
  if (state.max !== 35) p.set("max", state.max);
  if (state.minUse > 0) p.set("minu", state.minUse);
  if (state.maxUse > 0) p.set("maxu", state.maxUse);
  if (state.origin !== "all") p.set("origin", state.origin);
  if (state.q) p.set("q", state.q);
  if (state.sort !== "wystapienia_pierwsze") p.set("sort", state.sort);
  if (state.dir !== -1) p.set("dir", state.dir);
  if (state.regex) p.set("regex", "1");
  if (state.fav) p.set("fav", "1");
  
  var qs = p.toString();
  history.replaceState(state, "", qs ? "?" + qs : location.pathname);
}

// Synchronizacja przycisków wyboru rodzaju (żeńskie, męskie itd.) z wartością w stanie
function syncGenderButtons() {
  [].forEach.call(document.getElementById("seg-gender").querySelectorAll("button"), function (x) {
    x.setAttribute("aria-pressed", x.getAttribute("data-g") === state.g ? "true" : "false");
  });
}

// Przejście bezpośrednie do konkretnego imienia (czyszczenie kolidujących filtrów, wyszukanie i rozwinięcie)
function goToName(name) {
  var hit = nameIndex[name.toLowerCase()] || {};
  if (!hit.m && !hit.z) return;
  
  // Jeśli wybrane imię nie mieści się w bieżącej kategorii, przełącz na kategorię pasującą
  if (!((state.g === "m" && hit.m) || (state.g === "z" && hit.z) || state.g === "all" || state.g === "uni")) {
    state.g = (hit.m && hit.z) ? "all" : (hit.z ? "z" : "m");
    syncGenderButtons();
    updateHeader();
  }
  
  var r0 = (state.g === "m" ? hit.m : state.g === "z" ? hit.z : (hit.z || hit.m)) || hit.z || hit.m;
  if (state.g === "uni") {
    var zR = hit.z, mR = hit.m;
    var zT = zR ? ((zR.wystapienia_pierwsze || 0) + (zR.wystapienia_drugie || 0)) : 0;
    var mT = mR ? ((mR.wystapienia_pierwsze || 0) + (mR.wystapienia_drugie || 0)) : 0;
    var totalT = zT + mT;
    if (!totalT || Math.min(zT, mT) / totalT < 0.1) return;
  }
  
  var L = name.length, t = totalCount(r0);
  
  // Dostosowanie suwaków długości
  if (L < state.min) {
    state.min = L;
    lengthMin.value = L;
  }
  if (L > state.max) {
    state.max = L;
    lengthMax.value = L;
  }
  lengthValue.textContent = (state.min === state.max ? state.min + " liter" : state.min + "–" + state.max + " liter");
  
  // Dostosowanie filtrów wystąpień
  if (state.minUse > 0 && t < state.minUse) {
    state.minUse = 0;
    usageMin.value = "";
  }
  if (state.maxUse > 0 && t > state.maxUse) {
    state.maxUse = 0;
    usageMax.value = "";
  }
  usageValue.textContent = state.minUse && state.maxUse ? state.minUse + "–" + formatNumber(state.maxUse) : state.minUse ? "od " + formatNumber(state.minUse) : state.maxUse ? "do " + formatNumber(state.maxUse) : "dowolnie";
  
  // Reset pochodzenia, jeśli imię nie pasuje do aktualnego filtru pochodzenia
  if (state.origin !== "all" && r0.pochodzenie !== state.origin) {
    state.origin = "all";
    originSelect.value = "all";
  }
  
  // Wyłączenie trybu regex i wpisanie szukanej frazy
  state.regex = false;
  regexToggle.setAttribute("aria-pressed", "false");
  searchInput.placeholder = "np. Ala, Zof, mar…";
  state.q = name;
  searchInput.value = name;
  
  showAll = false;
  currentPage = 0;
  randomOffset = 0;
  render();
  
  // Rozwinięcie panelu szczegółów wybranego imienia po krótkim czasie (na wyrenderowanie DOM)
  setTimeout(function () {
    var tr = tableBody.querySelector('tr.main[data-imie="' + escapeHtml(name) + '"]');
    if (tr) {
      tr.scrollIntoView({ behavior: "smooth", block: "center" });
      if (tr.getAttribute("aria-expanded") !== "true") tr.click();
    }
  }, 60);
}
