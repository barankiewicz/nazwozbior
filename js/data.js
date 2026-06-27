// Przetwarzanie i mapowanie danych wejściowych ──

"use strict";

// Przypisanie rodzaju męskiego do imion męskich i zaimplementowanie tablicy
var maleNames = (window.DANE_MESKIE || []).map(function (r) {
  r._g = "m";
  return r;
});

// Przypisanie rodzaju żeńskiego do imion żeńskich i zaimplementowanie tablicy
var femaleNames = (window.DANE_ZENSKIE || []).map(function (r) {
  r._g = "z";
  return r;
});

// Kopia tablicy imion niebinarnych
var nonbinaryNames = (window.DANE_NIEBINARNE || []);

// Główny indeks po znormalizowanym imieniu (małymi literami)
var nameIndex = {};

maleNames.forEach(function (r) {
  var k = r.imie.toLowerCase();
  (nameIndex[k] = nameIndex[k] || {}).m = r;
});

femaleNames.forEach(function (r) {
  var k = r.imie.toLowerCase();
  (nameIndex[k] = nameIndex[k] || {}).z = r;
});

// Przetwarzanie imion niebinarnych i wyliczanie ich wystąpień w PESEL na podstawie wariantów zapisu
nonbinaryNames.forEach(function (r) {
  r._g = "nb";
  r._rzp = 0;
  r._rzd = 0;
  r._rmp = 0;
  r._rmd = 0;
  r._war = [];
  
  (r.warianty && r.warianty.length ? r.warianty : [r.imie]).forEach(function (v) {
    var hit = nameIndex[v.toLowerCase()] || {};
    if (hit.z) {
      r._rzp += hit.z.wystapienia_pierwsze || 0;
      r._rzd += hit.z.wystapienia_drugie || 0;
    }
    if (hit.m) {
      r._rmp += hit.m.wystapienia_pierwsze || 0;
      r._rmd += hit.m.wystapienia_drugie || 0;
    }
    r._war.push({ w: v, z: hit.z, m: hit.m });
  });
});

// Czy opisy mają być doczytywane dynamicznie shardami (sprawdzenie czy brak pola opis_html w pierwszym rekordzie)
var lazyDescriptions = !(maleNames[0] && "opis_html" in maleNames[0]) && !(femaleNames[0] && "opis_html" in femaleNames[0]);

// ── Precomputing static data pools ──
var unisexNames = [];
var uSeen = {};
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
  unisexNames.push(ur);
});

var nonbinaryPool = nonbinaryNames.slice();
var seenNb = {};
nonbinaryNames.forEach(function (r) { seenNb[r.imie.toLowerCase()] = true; });

maleNames.concat(femaleNames).forEach(function (r) {
  if (r.unisex && r.unisex >= 0.1) {
    var k = r.imie.toLowerCase();
    if (!seenNb[k]) {
      seenNb[k] = true;
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
      nonbinaryPool.push(nr);
    }
  }
});

var allNames = maleNames.concat(femaleNames);

// ── Precomputing sort/filter keys for all records to eliminate runtime overhead ──
function precomputeSortKeys(r) {
  r._sort_imie = r.imie.toLowerCase();
  r._sort_dlugosc = r.imie.length;
  
  if (r._g === "nb" || r._g === "uni") {
    r._sort_pochodzenie = getNbOriginLabel(r);
    r._sort_rejz = (r._rzp || 0) + (r._rzd || 0);
    r._sort_rejm = (r._rmp || 0) + (r._rmd || 0);
    var z = r._sort_rejz, m = r._sort_rejm, t = z + m;
    r._sort_ratio_nb = t ? z / t : 0;
    r._sort_wystapienia_razem = t;
  } else {
    r._sort_pochodzenie = getOriginLabel(r.pochodzenie);
    r._sort_wystapienia_pierwsze = r.wystapienia_pierwsze || 0;
    r._sort_wystapienia_drugie = r.wystapienia_drugie || 0;
    r._sort_wystapienia_razem = (r.wystapienia_pierwsze || 0) + (r.wystapienia_drugie || 0);
  }
}

maleNames.forEach(precomputeSortKeys);
femaleNames.forEach(precomputeSortKeys);
unisexNames.forEach(precomputeSortKeys);
nonbinaryPool.forEach(precomputeSortKeys);

