/* Wires the navbar theme toggle. The initial data-bs-theme is set by an inline
   snippet in the document head so the page never flashes the wrong theme; this
   file only handles the click that flips and persists the choice.

   A stored choice wins over the system preference. When no choice is stored the
   page follows prefers-color-scheme and keeps following it live, so a visitor
   who never touched the toggle sees the theme track their OS setting. */
(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var root = document.documentElement;
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  function systemTheme() {
    return media.matches ? "dark" : "light";
  }

  function apply(theme) {
    root.setAttribute("data-bs-theme", theme);
  }

  media.addEventListener("change", function () {
    if (!localStorage.getItem(STORAGE_KEY)) {
      apply(systemTheme());
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("theme-toggle");
    if (!button) {
      return;
    }
    button.addEventListener("click", function () {
      var next =
        root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(STORAGE_KEY, next);
      apply(next);
    });
  });
})();
