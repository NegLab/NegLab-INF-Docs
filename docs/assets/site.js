document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-catalogue]").forEach((catalogue) => {
    const search = catalogue.querySelector("[data-search-input]");
    const cards = [...catalogue.querySelectorAll("[data-list] .publication-card")];
    const resultCount = catalogue.querySelector("[data-result-count]");
    const clearFilters = catalogue.querySelector("[data-clear]");
    const emptyState = catalogue.querySelector("[data-empty]");
    const filters = [...catalogue.querySelectorAll("select[data-filter]")];
    const singular = resultCount?.dataset.singular ?? "entry";
    const plural = resultCount?.dataset.plural ?? "entries";

    const matchesFilter = (card, select) => {
      if (!select.value) return true;
      const value = card.dataset[select.dataset.filter] ?? "";
      if (select.dataset.filterMode === "token") return value.split("|").includes(select.value);
      return value === select.value;
    };

    const applyFilters = () => {
      const query = search?.value.trim().toLocaleLowerCase() ?? "";
      let visible = 0;

      cards.forEach((card) => {
        const matches = (!query || (card.dataset.search ?? "").includes(query))
          && filters.every((select) => matchesFilter(card, select));
        card.hidden = !matches;
        if (matches) visible += 1;
      });

      if (resultCount) resultCount.textContent = `${visible} ${visible === 1 ? singular : plural}`;
      if (clearFilters) clearFilters.hidden = !(query || filters.some((select) => select.value));
      if (emptyState) emptyState.hidden = visible !== 0;
    };

    search?.addEventListener("input", applyFilters);
    filters.forEach((select) => select.addEventListener("change", applyFilters));
    clearFilters?.addEventListener("click", () => {
      if (search) search.value = "";
      filters.forEach((select) => { select.value = ""; });
      applyFilters();
      search?.focus();
    });
    applyFilters();
  });

  document.querySelector("[data-copy-bib]")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const bibtexEntry = document.querySelector("#bibtex-entry");
    const bibtex = bibtexEntry?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(bibtex);
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = "Copy"; }, 1600);
    } catch (_) {
      if (!bibtexEntry) return;
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(bibtexEntry);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  });
});
