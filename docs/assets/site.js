document.addEventListener("DOMContentLoaded", () => {
  const setupFilters = ({
    searchId,
    listId,
    resultId,
    clearId,
    emptyId,
    filters,
    singular,
    plural,
  }) => {
    const search = document.querySelector(`#${searchId}`);
    const list = document.querySelector(`#${listId}`);
    const cards = list ? [...list.querySelectorAll(".publication-card")] : [];
    const resultCount = document.querySelector(`#${resultId}`);
    const clearFilters = document.querySelector(`#${clearId}`);
    const emptyState = document.querySelector(`#${emptyId}`);
    const filterControls = filters.map(({ id, data }) => ({
      element: document.querySelector(`#${id}`),
      data,
    }));

    const applyFilters = () => {
      const query = search?.value.trim().toLocaleLowerCase() ?? "";
      let visible = 0;

      cards.forEach((card) => {
        const matchesSearch = !query || (card.dataset.search ?? "").includes(query);
        const matchesFilters = filterControls.every(({ element, data }) => (
          !element?.value || card.dataset[data] === element.value
        ));
        const matches = matchesSearch && matchesFilters;
        card.hidden = !matches;
        if (matches) visible += 1;
      });

      if (resultCount) resultCount.textContent = `${visible} ${visible === 1 ? singular : plural}`;
      const hasFilters = Boolean(query || filterControls.some(({ element }) => element?.value));
      if (clearFilters) clearFilters.hidden = !hasFilters;
      if (emptyState) emptyState.hidden = visible !== 0;
    };

    search?.addEventListener("input", applyFilters);
    filterControls.forEach(({ element }) => element?.addEventListener("change", applyFilters));
    clearFilters?.addEventListener("click", () => {
      if (search) search.value = "";
      filterControls.forEach(({ element }) => {
        if (element) element.value = "";
      });
      applyFilters();
      search?.focus();
    });
    if (list || resultCount) applyFilters();
  };

  setupFilters({
    searchId: "tool-search",
    listId: "tool-list",
    resultId: "tool-result-count",
    clearId: "tool-clear-filters",
    emptyId: "tool-empty-state",
    filters: [
      { id: "tool-type-filter", data: "tooltype" },
      { id: "tool-status-filter", data: "status" },
    ],
    singular: "tool",
    plural: "tools",
  });

  setupFilters({
    searchId: "catalogue-search",
    listId: "catalogue-list",
    resultId: "catalogue-result-count",
    clearId: "catalogue-clear-filters",
    emptyId: "catalogue-empty-state",
    filters: [
      { id: "catalogue-year-filter", data: "year" },
      { id: "catalogue-type-filter", data: "type" },
    ],
    singular: "entry",
    plural: "entries",
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
