// ── Pula imion, filtrowanie i sortowanie ──

"use strict";

// Określa pulę aktywnych imion w zależności od wybranego rodzaju
function getPool() {
  if (state.g === "m") return maleNames;
  if (state.g === "z") return femaleNames;
  
  if (state.g === "uni") {
    var uSeen = {};
    var uOut = [];
    maleNames.concat(femaleNames).forEach(function (r) {
      if (!r.unisex || r.unisex < 0.1) return;
      var k = r.imie.toLowerCase();
      if (uSeen[k]) return;
      uSeen[k] = true;
      var zE = nameIndex[k] ? nameIndex[k].z : null;
      var mE = nameIndex[k] ? nameIndex[k].m : null;
      var ur = {};
      ur.imie = r.imie;
      ur._g = "uni";
      ur._rzp = zE ? (zE.wystapienia_pierwsze || 0) : 0;
      ur._rzd = zE ? (zE.wystapienia_drugie || 0) : 0;
      ur._rmp = mE ? (mE.wystapienia_pierwsze || 0) : 0;
      ur._rmd = mE ? (mE.wystapienia_drugie || 0) : 0;
      ur._war = [];
      ur.pochodzenie = r.pochodzenie;
      ur.unisex = r.unisex;
      ur._src = r;
      ur.opis_html = r.opis_html;
      ur.zrodlo = r.zrodlo;
      ur.zrodlo_baza = r.zrodlo_baza;
      ur.bazowe = r.bazowe;
      ur.pochodne = r.pochodne;
      ur.trend = r.trend;
      uOut.push(ur);
    });
    return uOut;
  }
  
  if (state.g === "nb") {
    var seen = {};
    var out = nonbinaryNames.slice();
    nonbinaryNames.forEach(function (r) { seen[r.imie.toLowerCase()] = true; });
    
    maleNames.concat(femaleNames).forEach(function (r) {
      if (r.unisex && r.unisex >= 0.1) {
        var k = r.imie.toLowerCase();
        if (!seen[k]) {
          seen[k] = true;
          var zE = nameIndex[k] ? nameIndex[k].z : null;
          var mE = nameIndex[k] ? nameIndex[k].m : null;
          var nr = {};
          nr.imie = r.imie;
          nr._g = "nb";
          nr._is_unisex_pesel = true;
          nr._rzp = zE ? (zE.wystapienia_pierwsze || 0) : 0;
          nr._rzd = zE ? (zE.wystapienia_drugie || 0) : 0;
          nr._rmp = mE ? (mE.wystapienia_pierwsze || 0) : 0;
          nr._rmd = mE ? (mE.wystapienia_drugie || 0) : 0;
          nr._war = [];
          nr.pochodzenie = r.pochodzenie;
          nr.unisex = r.unisex;
          nr._src = (zE || mE);
          out.push(nr);
        }
      }
    });
    return out;
  }
  
  return maleNames.concat(femaleNames);
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

// Sprawdza czy nazwa pasuje do aktualnego zapytania w polu szukaj (zwykłe lub regex)
function nameMatches(name) {
  var q = state.q.trim();
  if (!q) return true;
  if (state.regex) {
    var b = buildRegex(q);
    if (!b.rx) return false;
    return b.rx.test(name);
  }
  return name.toLowerCase().indexOf(q.toLowerCase()) >= 0;
}

// Zwraca przefiltrowaną listę imion zgodnie z bieżącym stanem filtrów
function getFiltered() {
  var q = state.q.trim().toLowerCase();
  if (state.regex && q) {
    var b = buildRegex(state.q.trim());
    regexError.textContent = b.err || "";
  } else {
    regexError.textContent = "";
  }
  
  return getPool().filter(function (r) {
    var L = r.imie.length;
    if (L < state.min || L > state.max) return false;
    
    var total = totalCount(r);
    if (state.minUse > 0 && total < state.minUse) return false;
    if (state.maxUse > 0 && total > state.maxUse) return false;
    
    if (state.origin === "all") {
      // bez filtra
    } else if (state.origin === "__none__") {
      if (r.pochodzenie) return false;
    } else if (r.pochodzenie !== state.origin) {
      return false;
    }
    
    if (state.fav && !favorites.has(r.imie.toLowerCase())) return false;
    
    if (!nameMatches(r.imie)) return false;
    return true;
  });
}

// Zwraca posortowaną listę wyników według klucza i kierunku w stanie
function getSorted(arr) {
  var k = state.sort;
  var d = state.dir;
  return arr.slice().sort(function (a, b) {
    var x = getSortValue(a, k);
    var y = getSortValue(b, k);
    if (x < y) return -1 * d;
    if (x > y) return 1 * d;
    return a.imie.localeCompare(b.imie, "pl");
  });
}
