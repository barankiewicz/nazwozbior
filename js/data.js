// ── Przetwarzanie i mapowanie danych wejściowych ──

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
