document.addEventListener("DOMContentLoaded", () => {
  const search = document.querySelector("#publication-search");
  const yearFilter = document.querySelector("#year-filter");
  const typeFilter = document.querySelector("#type-filter");
  const cards = [...document.querySelectorAll(".publication-card")];
  const resultCount = document.querySelector("#result-count");
  const clearFilters = document.querySelector("#clear-filters");
  const emptyState = document.querySelector("#empty-state");

  const applyFilters = () => {
    const query = search?.value.trim().toLocaleLowerCase() ?? "";
    const year = yearFilter?.value ?? "";
    const type = typeFilter?.value ?? "";
    let visible = 0;

    cards.forEach((card) => {
      const matches = (!query || card.dataset.search.includes(query))
        && (!year || card.dataset.year === year)
        && (!type || card.dataset.type === type);
      card.hidden = !matches;
      if (matches) visible += 1;
    });

    if (resultCount) resultCount.textContent = `${visible} project${visible === 1 ? "" : "s"}`;
    if (clearFilters) clearFilters.hidden = !(query || year || type);
    if (emptyState) emptyState.hidden = visible !== 0;
  };

  search?.addEventListener("input", applyFilters);
  yearFilter?.addEventListener("change", applyFilters);
  typeFilter?.addEventListener("change", applyFilters);
  clearFilters?.addEventListener("click", () => {
    search.value = "";
    yearFilter.value = "";
    typeFilter.value = "";
    applyFilters();
    search.focus();
  });
  if (cards.length || resultCount) applyFilters();

  document.querySelector("[data-copy-bib]")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const bibtex = document.querySelector("#bibtex-entry")?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(bibtex);
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = "Copy"; }, 1600);
    } catch (_) {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(document.querySelector("#bibtex-entry"));
      selection.removeAllRanges();
      selection.addRange(range);
    }
  });
});
