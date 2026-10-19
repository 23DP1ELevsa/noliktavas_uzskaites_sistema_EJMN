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

    if (!sorted.length) {
        catalogMessage.textContent = "Pēc izvēlētajiem kritērijiem preces netika atrastas.";
        return;
    }
    catalogMessage.textContent = "";
    sorted.forEach((product) => {
        const card = document.createElement("article");
        card.className = "product-card";
        const availability = product.available ? "Pieejams" : "Nav pieejams";
        card.innerHTML = `
            <div class="product-image" aria-hidden="true">${escapeHtml(product.name.slice(0, 1).toUpperCase())}</div>
            <p class="product-category">${escapeHtml(product.category)}</p>
            <h3><a href="${escapeHtml(product.detail_url)}">${escapeHtml(product.name)}</a></h3>
            <p class="product-sku">Preces kods: ${escapeHtml(product.sku)}</p>
            <p class="price">${formatPrice(product.price)}</p>
            <p class="offer-count">${product.offer_count} ${product.offer_count % 10 === 1 && product.offer_count % 100 !== 11 ? "piedāvājums" : "piedāvājumi"}</p>
            <p class="availability ${product.available ? '' : 'availability-unavailable'}">${escapeHtml(availability)}</p>
            <a class="card-button" href="${escapeHtml(product.detail_url)}" aria-label="${escapeHtml('Skatīt piedāvājumus: ' + product.name)}">Skatīt piedāvājumus <span aria-hidden="true">→</span></a>
        `;
        if (product.image_url) {
            const image = document.createElement("img");
            image.src = product.image_url;
            image.alt = product.name;
            image.loading = "lazy";
            image.referrerPolicy = "no-referrer";
            const container = card.querySelector(".product-image");
            container.removeAttribute("aria-hidden");
            image.addEventListener("error", () => {
                container.textContent = product.name.slice(0, 1).toUpperCase();
                container.setAttribute("aria-hidden", "true");
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
            throw new Error(errorMessage);
        }
        products = data.items;
        renderProducts();
    } catch (error) {
        if (requestNumber !== latestRequest) return;
        catalogCount.textContent = "Kļūda";
        catalogMessage.textContent = errorMessage;
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

applyFiltersButton.addEventListener("click", loadCatalog);
categorySelect.addEventListener("change", loadCatalog);
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
