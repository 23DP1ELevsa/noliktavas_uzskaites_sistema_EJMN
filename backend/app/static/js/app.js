const body = document.body;
const catalogUrl = body.dataset.catalogUrl;
const searchForm = document.querySelector("#catalog-search-form");
const searchInput = document.querySelector("#catalog-search");
const supplierInput = document.querySelector("#supplier-filter");
const categorySelect = document.querySelector("#category-filter");
const minPriceInput = document.querySelector("#min-price");
const maxPriceInput = document.querySelector("#max-price");
const stockInput = document.querySelector("#stock-filter");
const sortSelect = document.querySelector("#sort-control");
const productGrid = document.querySelector("#product-grid");
const catalogCount = document.querySelector("#catalog-count");
const catalogMessage = document.querySelector("#catalog-message");
const clearFiltersButton = document.querySelector("#clear-filters");
const applyFiltersButton = document.querySelector("#apply-filters");
const filtersToggle = document.querySelector("#filters-toggle");
const filtersPanel = document.querySelector(".catalog-filter-panel");
const mobileFilters = window.matchMedia("(max-width: 760px)");
const retryButton = document.querySelector("#catalog-retry");
const resultsTitle = document.querySelector("#catalog-results-title");
const filterControls = { category_id: categorySelect, supplier: supplierInput, min_price: minPriceInput, max_price: maxPriceInput, q: searchInput };
const placeholderMarkup = '<span class="product-image-placeholder"><svg class="icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="M3 8v9l9 5 9-5V8M12 13v9M7.5 5.5l9 5"/></svg><small>Attēls nav pieejams</small></span>';

// Paslēpjam tikai paneļa attēlojumu, lai izvēlētie filtri nepazustu pēc aizvēršanas.
function setFiltersOpen(open) {
    filtersToggle.setAttribute("aria-expanded", String(open));
    filtersToggle.setAttribute("aria-label", open ? "Aizvērt filtrus" : "Atvērt filtrus");
    filtersPanel.classList.toggle("is-open", open);
}

filtersToggle.addEventListener("click", () => {
    setFiltersOpen(filtersToggle.getAttribute("aria-expanded") !== "true");
});
filtersPanel.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && mobileFilters.matches && filtersToggle.getAttribute("aria-expanded") === "true") {
        setFiltersOpen(false);
        filtersToggle.focus();
    }
});
mobileFilters.addEventListener("change", () => {
    // Mainot orientāciju, fokusu neatstājam tikko paslēptā ievades laukā.
    const focusInside = filtersPanel.contains(document.activeElement);
    setFiltersOpen(false);
    if (focusInside && mobileFilters.matches) filtersToggle.focus();
    else if (document.activeElement === filtersToggle) categorySelect.focus();
});

let products = [];
let latestRequest = 0;

function currentParams() {
    const params = new URLSearchParams(window.location.search);
    const fields = [
        ["q", searchInput.value.trim()],
        ["category_id", categorySelect.value],
        ["supplier", supplierInput.value.trim()],
        ["min_price", minPriceInput.value.trim()],
        ["max_price", maxPriceInput.value.trim()],
        ["in_stock", stockInput.checked ? "true" : ""],
    ];
    fields.forEach(([key, value]) => {
        if (value) params.set(key, value);
        else params.delete(key);
    });
    return params;
}

function updateUrl(params) {
    const query = params.toString();
    window.history.replaceState({}, "", query ? `?${query}` : window.location.pathname);
}

function formatPrice(price) {
    return price === null ? "Cena nav norādīta" : new Intl.NumberFormat('lv-LV', {
        style: 'currency', currency: 'EUR', minimumFractionDigits: 2,
    }).format(price);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[character]));
}

function sortProducts(items) {
    const sorted = [...items];
    const sort = sortSelect.value;
    if (sort === "price-asc" || sort === "price-desc") {
        sorted.sort((a, b) => {
            if (a.price === null && b.price === null) return 0;
            if (a.price === null) return 1;
            if (b.price === null) return -1;
            return (a.price - b.price) * (sort === "price-asc" ? 1 : -1);
        });
    } else if (sort === "name-asc" || sort === "name-desc") {
        sorted.sort((a, b) => a.name.localeCompare(b.name, "lv") * (sort === "name-asc" ? 1 : -1));
    }
    return sorted;
}

function renderProducts() {
    const sorted = sortProducts(products);
    const singular = sorted.length % 10 === 1 && sorted.length % 100 !== 11;
    catalogCount.textContent = `${sorted.length} ${singular ? "prece" : "preces"}`;
    productGrid.replaceChildren();
    resultsTitle.textContent = categorySelect.selectedOptions[0]?.value
        ? categorySelect.selectedOptions[0].textContent : searchInput.value.trim() ? "Meklēšanas rezultāti" : "Visas preces";

    if (!sorted.length) {
        catalogMessage.textContent = "Pēc izvēlētajiem kritērijiem preces netika atrastas.";
        return;
    }
    catalogMessage.textContent = "";
    sorted.forEach((product) => {
        const card = document.createElement("article");
        card.className = "product-card";
        const availability = product.available ? "Pieejams" : "Nav pieejams";
        const priceOffer = product.offers?.[0];
        card.innerHTML = `
            <a class="product-image" href="${escapeHtml(product.detail_url)}" aria-label="${escapeHtml('Atvērt preci: ' + product.name)}">${placeholderMarkup}</a>
            <div class="product-card-body">
            <p class="product-category">${escapeHtml(product.category)}</p>
            <h3><a href="${escapeHtml(product.detail_url)}">${escapeHtml(product.name)}</a></h3>
            <p class="product-sku">SKU: ${escapeHtml(product.sku)}</p>
            <div class="product-pricing">
            <p class="price ${product.price === null ? 'price-missing' : ''}">${product.price === null ? '' : '<span class="price-label">No</span>'}${escapeHtml(formatPrice(product.price))}</p>
            ${priceOffer ? `<p class="product-tax-note">/ ${escapeHtml(product.unit)} · ${priceOffer.vat_included ? 'Ar PVN' : 'Bez PVN'} · bez piegādes</p>` : ''}
            <p class="offer-count">${escapeHtml(product.offer_count)} ${product.offer_count % 10 === 1 && product.offer_count % 100 !== 11 ? "piedāvājums" : "piedāvājumi"}</p>
            </div>
            <p class="availability ${product.available ? '' : 'availability-unavailable'}">${escapeHtml(availability)}</p>
            <a class="card-button" href="${escapeHtml(product.detail_url)}" aria-label="${escapeHtml('Skatīt piedāvājumus: ' + product.name)}">Skatīt piedāvājumus <span aria-hidden="true">→</span></a>
            </div>
        `;
        if (product.image_url) {
            const image = document.createElement("img");
            image.src = product.image_url;
            image.alt = product.name;
            image.loading = "lazy";
            image.referrerPolicy = "no-referrer";
            image.decoding = "async";
            const container = card.querySelector(".product-image");
            image.addEventListener("error", () => {
                container.innerHTML = placeholderMarkup;
            }, { once: true });
            container.replaceChildren(image);
        }
        productGrid.append(card);
    });
}

async function loadCatalog() {
    const requestNumber = ++latestRequest;
    const content = productGrid.closest('.catalog-content');
    content.setAttribute('aria-busy', 'true');
    retryButton.hidden = true;
    catalogMessage.classList.remove('is-error');
    Object.values(filterControls).forEach((control) => {
        control.removeAttribute('aria-invalid');
        control.removeAttribute('aria-errormessage');
    });
    catalogMessage.textContent = "Ielādē katalogu...";
    let errorMessage = "Katalogu neizdevās ielādēt. Pārbaudiet savienojumu un mēģiniet vēlreiz.";
    const params = currentParams();
    updateUrl(params);
    try {
        const response = await fetch(`${catalogUrl}?${params.toString()}`, {
            headers: { Accept: "application/json" },
        });
        const data = await response.json();
        if (requestNumber !== latestRequest) return;
        if (!response.ok) {
            errorMessage = data.message || errorMessage;
            if (filterControls[data.field]) {
                filterControls[data.field].setAttribute('aria-invalid', 'true');
                filterControls[data.field].setAttribute('aria-errormessage', 'catalog-message');
                if (mobileFilters.matches) setFiltersOpen(true);
            }
            throw new Error(errorMessage);
        }
        products = data.items;
        renderProducts();
        return true;
    } catch (error) {
        if (requestNumber !== latestRequest) return;
        catalogCount.textContent = "Kļūda";
        catalogMessage.textContent = errorMessage;
        catalogMessage.classList.add('is-error');
        retryButton.hidden = false;
        productGrid.replaceChildren();
    } finally {
        if (requestNumber === latestRequest) content.setAttribute('aria-busy', 'false');
    }
}

function restoreFilters() {
    const params = new URLSearchParams(window.location.search);
    searchInput.value = params.get("q") || "";
    supplierInput.value = params.get("supplier") || "";
    categorySelect.value = params.get("category_id") || "";
    minPriceInput.value = params.get("min_price") || "";
    maxPriceInput.value = params.get("max_price") || "";
    stockInput.checked = params.get("in_stock") === "true";
}

searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadCatalog();
});

applyFiltersButton.addEventListener("click", async () => {
    // Pēc veiksmīgas atlases telefonā atbrīvojam vietu rezultātiem; kļūdas gadījumā filtrus atstājam vaļā.
    if (await loadCatalog() && mobileFilters.matches) {
        setFiltersOpen(false);
        filtersToggle.focus();
    }
});
categorySelect.addEventListener("change", loadCatalog);
retryButton.addEventListener("click", loadCatalog);
sortSelect.addEventListener("change", renderProducts);
clearFiltersButton.addEventListener("click", () => {
    searchInput.value = "";
    supplierInput.value = "";
    categorySelect.value = "";
    minPriceInput.value = "";
    maxPriceInput.value = "";
    stockInput.checked = false;
    window.history.replaceState({}, "", window.location.pathname);
    loadCatalog();
});

restoreFilters();
loadCatalog();
