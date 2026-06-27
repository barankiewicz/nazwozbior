// ── Pula imion, filtrowanie i sortowanie ──

"use strict";

// Określa pulę aktywnych imion w zależności od wybranego rodzaju
function getPool() {
  if (state.g === "m") return maleNames;
  if (state.g === "z") return femaleNames;
  if (state.g === "uni") return unisexNames;
  if (state.g === "nb") return nonbinaryPool;
  return allNames;
}

// Pamięć podręczna dla wyrażeń regularnych
var _regexCache = { pat: null, rx: null, err: null };

// Buduje lub zwraca skeszowane wyrażenie regularne dla wyszukiwania
function buildRegex(pat) {
  if (_regexCache.pat === pat) return _regexCache;
  _regexCache.pat = pat;
  try {
    _regexCache.rx = new RegExp(pat, "i");
    _regexCache.err = null;
  } catch (e) {
    _regexCache.rx = null;
    _regexCache.err = e.message;
  }
  return _regexCache;
}

// Generator wysoko zoptymalizowanego filtra dopasowania rekordów (wykorzystuje domknięcia)
function getMatchFilter() {
  var q = state.q.trim();
  var qLower = q.toLowerCase();
  var rx = null;
  if (q && state.regex) {
    var b = buildRegex(q);
    rx = b.rx;
  }
  var min = state.min;
  var max = state.max;
  var minUse = state.minUse;
  var maxUse = state.maxUse;
  var fav = state.fav;
  var origin = state.origin;

  return function (r, skipOrigin) {
    var L = r._sort_dlugosc;
    if (L < min || L > max) return false;
    
    var t = r._sort_wystapienia_razem;
    if (minUse > 0 && t < minUse) return false;
    if (maxUse > 0 && t > maxUse) return false;
    
    if (q) {
      if (rx) {
        if (!rx.test(r.imie)) return false;
      } else {
        if (r._sort_imie.indexOf(qLower) < 0) return false;
      }
    }
    
    if (fav && !favorites.has(r._sort_imie)) return false;
    
    if (!skipOrigin) {
      if (origin === "all") {
        // brak
      } else if (origin === "__none__") {
        if (r.pochodzenie) return false;
      } else if (r.pochodzenie !== origin) {
        return false;
      }
    }
    return true;
  };
}

// Zwraca przefiltrowaną listę imion zgodnie z bieżącym stanem filtrów
function getFiltered() {
  var q = state.q.trim();
  if (state.regex && q) {
    var b = buildRegex(q);
    regexError.textContent = b.err || "";
  } else {
    regexError.textContent = "";
  }
  
  var filterFn = getMatchFilter();
  return getPool().filter(function (r) {
    return filterFn(r, false);
  });
}

// Zwraca posortowaną listę wyników według klucza i kierunku w stanie (bez dynamicznych lookupów)
function getSorted(arr) {
  var k = state.sort;
  var d = state.dir;
  var sortKey = "_sort_" + k;
  return arr.slice().sort(function (a, b) {
    var x = a[sortKey];
    var y = b[sortKey];
    if (x < y) return -1 * d;
    if (x > y) return 1 * d;
    // Tie-breaker: alfabetycznie po nazwie (zawsze rosnąco)
    var nameA = a._sort_imie;
    var nameB = b._sort_imie;
    if (nameA < nameB) return -1;
    if (nameA > nameB) return 1;
    return 0;
  });
}

