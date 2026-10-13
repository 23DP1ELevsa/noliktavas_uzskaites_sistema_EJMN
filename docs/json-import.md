# JSON piedāvājumu imports

Administrators atver **Admin panelis → Imports** (`/admin/import/json`),
izvēlas JSON failu un nospiež **Importēt JSON**. Veiksmīga importa rezultātā
redzams pievienoto un atjaunināto piedāvājumu skaits. Ja kļūdains kaut viens
ieraksts, faila izmaiņas netiek saglabātas; lapā redzams ieraksta numurs,
kļūdainais lauks un iemesls. Numurs sākas ar 1, skaitot masīva elementus.
JSON sintakses kļūdai rāda faila rindas un kolonnas numuru.

Lapa, pogas, kļūdu paziņojumi un navigācija izmanto esošo StockFlow
administratora paneļa dizainu. Pieejama parauga lejupielāde; failus neglabā
lietotnes mapēs. Importēt un lejupielādēt paraugu drīkst tikai administrators;
augšupielādei nepieciešams formas CSRF kods.

## Faila paraugs un struktūra

Paraugs ir [`data_samples/offers_import.json`](../data_samples/offers_import.json)
vai **Lejupielādēt JSON paraugu** importa lapā. Tas satur divus demo
piedāvājumus. Pirms izmantošanas palaid `seed-demo` demonstrācijas datubāzē
vai pielāgo preču kodus un piegādātāju nosaukumus jau esošiem ierakstiem.
Parauga imports esošā demo datubāzē atjaunina divus piedāvājumus, nevis
izveido dublikātus; tas piemēro arī paraugā norādītās cenas un atlikumus.

Failam jābūt UTF-8 (atļauts UTF-8 BOM), līdz 2 MiB un ne vairāk kā 10 000
piedāvājumiem. Saknē jābūt masīvam, nevis objektam ar `offers` lauku:

```json
[
  {
    "product_sku": "DEMO-DRILL-001",
    "supplier_name": "Demo Baltic Supply",
    "supplier_sku": "DEMO-BS-DRILL",
    "currency": "EUR",
    "unit_price": "74.00",
    "vat_included": false,
    "vat_rate": 21,
    "min_order_qty": 2,
    "stock_qty": 6,
    "delivery_price": "7.50",
    "delivery_days": 5
  }
]
```

Lauku nosaukumi un biznesa noteikumi ir kopīgi CSV, JSON un API importam;
tos apraksta [kopīgais importa formāts](offer-import.md). JSON adapteris
papildus pārbauda paša JSON datu tipus:

| Lauki | JSON tips |
| --- | --- |
| `product_sku`, `supplier_sku`, `supplier_name`, `currency` | Teksts. Kodi paliek teksts, arī ja tie sastāv tikai no cipariem. |
| `supplier_id`, `min_order_qty`, `stock_qty`, `delivery_days` | Vesels JSON skaitlis, ne teksts, būla vērtība vai daļskaitlis. |
| `vat_included`, `is_active` | `true` vai `false`, ne teksts vai 1/0. |
| `unit_price`, `delivery_price`, `vat_rate` | JSON skaitlis vai decimālās vērtības teksts. Tekstā atļauts arī decimālais komats. `vat_rate` var būt `null` tikai cenai, kurā PVN jau iekļauts. |

Obligāti ir `product_sku`, `supplier_sku`, `currency`, `unit_price`,
`vat_included`, `min_order_qty`, `stock_qty`, `delivery_days`, kā arī
`supplier_id` vai `supplier_name`. Cenai bez PVN obligāta arī `vat_rate`.
Piegādes maksa un `is_active` ir neobligāti un izmanto kopīgā servisa noteikumus.
CSV adapteris pārvērš CSV lauku tekstu tajā pašā kopīgajā ieraksta formātā;
CSV un JSON lauku nosaukumi netiek atšķirti. [CSV importa apraksts](csv-import.md).

Tukšs fails nav derīgs. Tukšs masīvs `[]` ir derīgs un dod rezultātu 0/0.
Atkārtoti JSON objekta lauki, neatbalstīti lauki, NaN, Infinity, nepareiza
struktūra vai datu tipi tiek noraidīti. JSON decimālos skaitļus nolasa tieši
ar `Decimal`, tādēļ pirms pārbaudes cena netiek pārvērsta par `float`.

## Izmantošana kodā

`read_json_offers(stream)` nolasa bināru faila plūsmu, pārbauda visu failu un
atgriež normalizētu ierakstu sarakstu. Šī funkcija nepiekļūst datubāzei.
`JSONImportError` manto `OfferImportError`; tai ir `row`, `field` un sintakses
kļūdām `line`, `column`. Biznesa vērtību pārbaude izmanto kopīgo
`validate_import_record`, nevis atsevišķus JSON cenu vai daudzuma noteikumus.

`import_json_offers(stream, admin_id=...)` pēc veiksmīgas nolasīšanas nodod
visu sarakstu `save_imported_offers(..., source="JSON", admin_id=...)`.
Piegādātāja un preces esamību, dublikātus, transakciju, atjaunināšanas laiku
un skaitītājus pārvalda kopīgais serviss. Nepieciešams lietotnes konteksts
un tīra datubāzes sesija; faila saturs nedrīkst noteikt administratora ID.

```python
from backend.app.services.json_import import import_json_offers

with open("data_samples/offers_import.json", "rb") as source:
    result = import_json_offers(source, admin_id=authenticated_admin_id)
```

Jauna migrācija vai atkarība šim JSON papildinājumam nav vajadzīga. Datubāzei jau
jābūt piemērotai iepriekšējai importa migrācijai `0007_offer_import_identity`.
Railway lieto esošo izvietošanas procesu; failu augšupielādē caur publicētā
saita administratora importa lapu, tādēļ nav vajadzīga lokāla piekļuve datubāzei.

Pārbaudes: `tests/test_json_import.py`.
