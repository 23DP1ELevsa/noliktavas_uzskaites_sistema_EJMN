const body = document.body;
const catalogUrl = body.dataset.catalogUrl;
const searchForm = document.querySelector("#catalog-search-form");
const searchInput = document.querySelector("#catalog-search");
const supplierInput = document.querySelector("#supplier-filter");
const minPriceInput = document.querySelector("#min-price");
const maxPriceInput = document.querySelector("#max-price");
const stockInput = document.querySelector("#stock-filter");
const sortSelect = document.querySelector("#sort-control");
const productGrid = document.querySelector("#product-grid");
const catalogCount = document.querySelector("#catalog-count");
const catalogMessage = document.querySelector("#catalog-message");
const clearFiltersButton = document.querySelector("#clear-filters");
const applyFiltersButton = document.querySelector("#apply-filters");
const categoryLinks = document.querySelectorAll("[data-category]");

let products = [];

function currentParams() {
    const params = new URLSearchParams(window.location.search);
    const fields = [
        ["q", searchInput.value.trim()],
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
    return price === null ? "Cena nav norādīta" : `${price.toFixed(2)} €`;
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
    catalogCount.textContent = `${sorted.length} ${sorted.length === 1 ? "prece" : "preces"}`;
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
            <h3>${escapeHtml(product.name)}</h3>
            <p class="product-sku">SKU: ${escapeHtml(product.sku)}</p>
            <p class="price">${formatPrice(product.price)}</p>
            <p class="offer-count">${product.offer_count} ${product.offer_count === 1 ? "piedāvājums" : "piedāvājumi"} · ${escapeHtml(availability)}</p>
            <a class="card-button" href="${escapeHtml(product.detail_url)}">Skatīt piedāvājumus</a>
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
    catalogMessage.textContent = "Ielādē katalogu...";
    const params = currentParams();
    updateUrl(params);
    try {
        const response = await fetch(`${catalogUrl}?${params.toString()}`, {
            headers: { Accept: "application/json" },
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || "Katalogu neizdevās ielādēt.");
        }
        products = data.items;
        renderProducts();
    } catch (error) {
        catalogCount.textContent = "Kļūda";
        catalogMessage.textContent = error.message;
        productGrid.replaceChildren();
    }
}

function restoreFilters() {
    const params = new URLSearchParams(window.location.search);
    searchInput.value = params.get("q") || "";
    supplierInput.value = params.get("supplier") || "";
    minPriceInput.value = params.get("min_price") || "";
    maxPriceInput.value = params.get("max_price") || "";
    stockInput.checked = params.get("in_stock") === "true";
    const selectedCategory = params.get("category_id") || "";
    categoryLinks.forEach((link) => {
        link.classList.toggle("category-active", link.dataset.category === selectedCategory);
    });
}

searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadCatalog();
});

applyFiltersButton.addEventListener("click", loadCatalog);
sortSelect.addEventListener("change", renderProducts);
clearFiltersButton.addEventListener("click", () => {
    searchInput.value = "";
    supplierInput.value = "";
    minPriceInput.value = "";
    maxPriceInput.value = "";
    stockInput.checked = false;
    window.history.replaceState({}, "", window.location.pathname);
    categoryLinks.forEach((link) => link.classList.toggle("category-active", !link.dataset.category));
    loadCatalog();
});

categoryLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();
        const params = currentParams();
        if (link.dataset.category) params.set("category_id", link.dataset.category);
        else params.delete("category_id");
        updateUrl(params);
        categoryLinks.forEach((item) => item.classList.toggle("category-active", item === link));
        loadCatalog();
    });
});

restoreFilters();
loadCatalog();
