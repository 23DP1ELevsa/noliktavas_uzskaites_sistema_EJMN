const searchForm = document.querySelector("#product-search-form");
const searchInput = document.querySelector("#product-search");
const searchMessage = document.querySelector("#search-message");
const languageSelect = document.querySelector("#language-select");

searchForm?.addEventListener("submit", (event) => {
	event.preventDefault();
	const query = searchInput.value.trim();

	if (!query) {
		searchMessage.textContent = "Ieraksti preces nosaukumu, zīmolu vai SKU.";
		searchInput.focus();
		return;
	}

	searchMessage.textContent = `Meklēšana pēc “${query}” būs pieejama kataloga modulī.`;
});

languageSelect?.addEventListener("change", (event) => {
	document.documentElement.lang = event.target.value;
});
