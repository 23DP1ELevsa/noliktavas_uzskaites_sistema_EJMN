# StockFlow saskarnes dizaina sistēma

Saskarne izmanto gaišu neitrālu fonu, baltus paneļus, grafīta tekstu un vienu
atturīgu zaļu akcentu. Lietotnes teksti ir latviešu valodā. Saglabāts esošais
Flask, Jinja2, HTML, CSS un JavaScript risinājums.

## Dizaina mainīgie

Mainīgie definēti `backend/app/static/css/style.css` faila `:root` blokā.

| Mainīgais | Vērtība | Lietojums |
| --- | --- | --- |
| `--canvas` | `#f5f6f7` | Lapas fons |
| `--surface` | `#ffffff` | Paneļi, kartītes un lauki |
| `--surface-subtle` | `#f0f3f2` | Papildu informācija un kopsavilkumi |
| `--ink` | `#202925` | Pamatteksts un virsraksti |
| `--muted` | `#58635e` | Paskaidrojumi un metadati |
| `--accent` | `#176b52` | Galvenās darbības, saites un aktīvā sadaļa |
| `--accent-hover` | `#10513e` | Galvenās darbības kursora stāvoklī |
| `--accent-soft` | `#eaf4ee` | Statusu un akcentu fons |
| `--danger` | `#a22d37` | Kļūdas un dzēšanas darbības |
| `--warning` | `#805519` | Darbību apstiprinājumi |
| `--line` | `#dce2de` | Paneļu un tabulu robežas |
| `--input-line` | `#8b9990` | Ievades lauku robežas |
| `--space-1`–`--space-7` | `4, 8, 12, 16, 24, 32, 48px` | Atstarpju skala |
| `--radius-sm`, `--radius`, `--radius-lg` | `6, 10, 14px` | Vienoti noapaļojumi |
| `--control-height` | `44px` | Vadīklu minimālais augstums |
| `--page-width` | `1320px`, lielos ekrānos `1480px` | Satura platums |

Fontu secība ir Segoe UI, Helvetica Neue, Arial un sistēmas bezserifa fonts.
Fonti un ikonas neprasa ārējus pakalpojumus.

## Komponentu uzbūve

- `_market_header.html` un `_footer.html` nodrošina kopīgo navigāciju un kājeni.
  `ui.js` pārvalda mobilo izvēlni, latviskus validācijas paziņojumus, faila
  izvēles nosaukumu un kategorijas dzēšanas dialogu ar tastatūras atbalstu.
- `_icons.html` satur vienota līniju stila SVG ikonu makrosu.
- `_messages.html` attēlo kopīgos paziņojumus ar kļūdas vai statusa lomu.
- `admin-primary-button`, `admin-secondary-button` un `admin-danger-button`
  nosaka galvenās, papildu un dzēšanas darbības.
- `form-field`, `form-grid` un `form-section` grupē laukus. Kopīgie lauku makrosi
  ir `auth/_form_macros.html`; kļūdainiem laukiem izmanto `aria-invalid` un
  piesaistītus paskaidrojumus.
- `panel`, `panel-heading`, `admin-page-heading` un `eyebrow` veido paneļu
  hierarhiju. `status-badge` izmanto tekstu kopā ar krāsu.
- `product-card`, `product-detail` un `offer-card` atdala preces informāciju,
  piegādātāja nosacījumus un cenu kopsavilkumu.
- `admin-table` tabulas ievietotas nosauktā, ar tastatūru fokusējamā
  `table-scroll` apgabalā. Plata tabula ritinās savā panelī.
- `_cart_groups.html`, `_cart_totals.html` un `_order_*` daļējie šabloni vienoti
  attēlo groza, noformēšanas un saglabātā pieteikuma datus.
- `import-layout`, `file-upload-field` un `import-guide` nošķir datu ievadi un
  sagatavošanas norādes.

## Lapu pārklājums

| Sadaļa | Lapas un stāvokļi | Šabloni |
| --- | --- | --- |
| Publiskā daļa | Sākumlapa `/`, katalogs `/catalog/page`, prece un piedāvājumu salīdzinājums `/catalog/products/<id>` | `index.html`, `catalog.html`, `product.html` |
| Konts | Pieslēgšanās `/auth/login`, reģistrācija `/auth/register`, profils ar paziņojumiem `/auth/profile` | `auth/login.html`, `auth/register.html`, `auth/profile.html` |
| Iepirkšanās | Grozs `/cart`, pieteikuma noformēšana `/orders/checkout`, pieteikumu vēsture `/orders`, saglabāts pieteikums `/orders/<id>` | `cart.html`, `checkout.html`, `orders.html`, `order.html` |
| Administratora pārskats | `/admin` un `/admin/` | `admin/dashboard.html` |
| Pieteikumu izskatīšana | Saraksts `/admin/orders`, informācija un lēmums `/admin/orders/<id>` | `admin/orders.html`, `admin/order_detail.html` |
| Preču pārvaldība | Saraksts, detaļas, pievienošana, rediģēšana un dzēšanas vai deaktivizēšanas apstiprinājums zem `/admin/products` | `admin/products.html`, `admin/product_detail.html`, `admin/product_form.html`, `admin/product_delete.html` |
| Piegādātāju pārvaldība | Saraksts, detaļas, pievienošana, rediģēšana un dzēšanas apstiprinājums zem `/admin/suppliers` | `admin/suppliers.html`, `admin/supplier_detail.html`, `admin/supplier_form.html`, `admin/supplier_delete.html` |
| Piedāvājumu pārvaldība | Saraksts, pievienošana, rediģēšana un dzēšanas vai deaktivizēšanas apstiprinājums zem `/admin/supplier-products` | `admin/supplier_products.html`, `admin/offer_form.html`, `admin/offer_delete.html` |
| Kategoriju pārvaldība | Saraksts, izveide un rediģēšana zem `/admin/categories`; dzēšana ar apstiprinājumu | `admin/categories.html`, `admin/category_form.html` |
| Imports | JSON, CSV un API lapas `/admin/import/json`, `/admin/import/csv`, `/admin/import/api` | `admin/import_json.html`, `admin/import_api.html`, `admin/_import_tabs.html` |
| Kļūdas | Lokalizētas pārlūka kļūdu lapas un iepirkšanās datubāzes kļūdas | `error.html`, `shopping_error.html` |

Kopīgais administratora ietvars ir `admin/base.html`. Tukšie saraksti, neaktīvie
piedāvājumi, lauku kļūdas un jau izskatīti pieteikumi izmanto šo pašu komponentu
sistēmu. Datu API `/catalog`, `/api/test/offers` un veselības pārbaude `/health`
paliek datu saskarnes.

## Pielāgošanās un piekļūstamība

Izkārtojumā izmantots CSS Grid, Flexbox, `min-width: 0` un garu tekstu dalīšana.
Navigācija mobilā skatā kļūst par atveramu izvēlni; kartītes, formas, filtri un
kopsavilkumi pārkārtojas vienā kolonnā. Platām tabulām saglabātas kolonnu galvenes
un vietēja horizontāla ritināšana. Globāla horizontālās pārplūdes slēpšana netiek
izmantota.

Ir saite pāriešanai uz saturu, lauku etiķetes, redzams fokuss, teksta statusi,
aprakstītas kļūdas un neaktīvas vadīklas. `prefers-reduced-motion` atslēdz
pārejas un animācijas. Pārbaudes darbības un reproducējamas komandas aprakstītas
[saskarnes pārbaudes dokumentā](ui-verification.md); faktiskie rezultāti jāskatās
attiecīgās pārbaudes ģenerētajā pārskatā.

## Saglabātā darbība un robežas

Pārveide saglabā maršrutus, lomas, autentifikāciju, Jinja mainīgos, formu lauku
nosaukumus, CSRF kodus un JavaScript izmantotos identifikatorus. Cenu, PVN,
krājumu, pasūtījumu vēstures un importa aprēķini paliek servera atbildībā;
datubāzes shēma nav mainīta. Kataloga pieprasījumu secības kontrole novērš
novecojuša meklēšanas rezultāta parādīšanu pēc jaunāka pieprasījuma.

Kataloga meklēšanai un filtrēšanai joprojām vajadzīgs JavaScript; bez tā redzams
paskaidrojums. Faila izvēles vadīkla, validācijas teksti un kategorijas dzēšanas
dialogs ir latviski; operētājsistēmas failu atlasītāja valodu nosaka sistēmas
iestatījumi. Ārējo preču attēlu
un API avotu pieejamība ir atkarīga no attiecīgā pakalpojuma.
