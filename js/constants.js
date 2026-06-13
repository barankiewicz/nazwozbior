// ── Stałe konfiguracyjne oraz referencje DOM ──

"use strict";

// SVG dla ikon przycisków motywu (jasny / ciemny)
var SUN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/></svg>';
var MOON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

// Słownik tłumaczeń pochodzenia imion
var ORIGIN_LABELS = {
  greckie: "greckie", lacinskie: "łacińskie", germanskie: "germańskie",
  slowianskie: "słowiańskie", staropolskie: "staropolskie", hebrajskie: "hebrajskie",
  aramejskie: "aramejskie", celtyckie: "celtyckie", arabskie: "arabskie", perskie: "perskie",
  litewskie: "litewskie", egipskie: "egipskie", sanskryckie: "sanskryckie", indyjskie: "indyjskie",
  tureckie: "tureckie", baskijskie: "baskijskie", anglosaskie: "anglosaskie", angielskie: "angielskie",
  francuskie: "francuskie", hiszpanskie: "hiszpańskie", wloskie: "włoskie", romanskie: "romańskie",
  rosyjskie: "rosyjskie", ruskie: "ruskie", ukrainskie: "ukraińskie", wegierskie: "węgierskie",
  skandynawskie: "skandynawskie", finskie: "fińskie", etiopskie: "etiopskie", fenickie: "fenickie",
  akadyjskie: "akadyjskie", sumeryjskie: "sumeryjskie", amerykanskie: "amerykańskie",
  japonskie: "japońskie", chinskie: "chińskie", koreanskie: "koreańskie", mongolskie: "mongolskie",
  polinezyjskie: "polinezyjskie", prowansalskie: "prowansalskie", holenderskie: "holenderskie",
  burgundzkie: "burgundzkie", bizantyjskie: "bizantyjskie", palestynskie: "palestyńskie",
  iberyjskie: "iberyjskie", etruskie: "etruskie", hawajskie: "hawajskie",
  gruzinskie: "gruzińskie", ormianskie: "ormiańskie"
};

// Stała określająca domyślną liczbę wierszy na jedną stronę paginacji
var PER_PAGE = 250;

// Tekst zastępczy wyświetlany, gdy dane imię nie posiada opisu znaczenia
var DESCRIPTION_MISSING = '<span style="color:var(--faint)">Źródła nie podają znaczenia tego imienia.</span>';

// Piktogram ładowania opisu (Skeleton Loader)
var DESCRIPTION_LOADING = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';

// Nagłówki tabeli dla podziału binarnego (męskie / żeńskie)
var HEADER_BINARY = '<th tabindex="0" data-key="imie">imię <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="dlugosc" class="num hide">długość <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="pochodzenie">pochodzenie <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="wystapienia_pierwsze" class="num">jako 1. imię <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="wystapienia_drugie" class="num hide">jako 2. imię <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="wystapienia_razem" class="num hide">łącznie <span class="arr">▲</span></th>' +
  '<th aria-label="rozwiń"></th>';

// Nagłówki tabeli dla podziału niebinarnego / unisex
var HEADER_NONBINARY = '<th tabindex="0" data-key="imie">imię <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="dlugosc" class="num hide">długość <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="pochodzenie">pochodzenie <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="rejz" class="num">w rej. żeńskim <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="rejm" class="num hide">w rej. męskim <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="ratio_nb" class="num"><span data-tip="Stosunek nadań żeńskich do męskich. Im bliżej 50/50, tym bardziej neutralne płciowo imię.">ż / m</span> <span class="arr">▲</span></th>' +
  '<th tabindex="0" data-key="wystapienia_razem" class="num hide">łącznie <span class="arr">▲</span></th>' +
  '<th aria-label="rozwiń"></th>';

// Słownik transliteracji polskich znaków na shardy opisów
var SHARD_MAP = { 'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z' };

// ── Referencje do elementów DOM ──
var helpCardToggle = document.getElementById("help-card-toggle");
var helpCardContent = document.getElementById("help-card-content");
var helpCardArrow = document.getElementById("help-card-arrow");

var tableBody = document.getElementById("rows");
var countElement = document.getElementById("count");
var headerRow = document.getElementById("head");
var originSelect = document.getElementById("origin");
var lengthMin = document.getElementById("len-min");
var lengthMax = document.getElementById("len-max");
var lengthValue = document.getElementById("len-val");
var usageMin = document.getElementById("use-min");
var usageMax = document.getElementById("use-max");
var usageValue = document.getElementById("use-val");
var searchInput = document.getElementById("search");
var regexToggle = document.getElementById("regex-toggle");
var favToggle = document.getElementById("fav-toggle");
var regexHelp = document.getElementById("regex-help");
var regexHelpButton = document.getElementById("regex-help-btn");
var regexError = document.getElementById("regex-err");
var randomButton = document.getElementById("random-btn");
var loadingTrigger = document.getElementById("loading-trigger");
var backToTopButton = document.getElementById("back-top");
