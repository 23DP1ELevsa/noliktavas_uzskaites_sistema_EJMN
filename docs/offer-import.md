# Kopīgā piedāvājumu importa saglabāšana

CSV, JSON un testa API adapteri izmanto vienu servisu:
`backend.app.services.offer_import.save_imported_offers`. Adapteris vispirms
nolasa avotu un izveido lauku/vērtību ierakstu sarakstu, pēc tam nodod visu
paketi servisam. CSV un JSON failu nolasīšana un administratora augšupielādes
lapas jau izmanto šo servisu; skatiet [CSV](csv-import.md) un
[JSON importa aprakstu](json-import.md). Testa API pieprasījumi ir nākamais uzdevums.

## Izmantošana

Flask lietotnes kontekstā, ar tīru datubāzes sesiju:

```python
from backend.app.services.offer_import import OfferImportError, save_imported_offers

records = [{
    "product_sku": "DEMO-DRILL-001",  # Esošās StockFlow preces kods.
    "supplier_name": "Demo Baltic Supply",  # Vai supplier_id ar esošu ID.
    "supplier_sku": "DEMO-BS-DRILL",  # Piegādātāja preces kods.
    "currency": "EUR",
    "unit_price": "74.00",
    "vat_included": False,
    "vat_rate": "21.00",
    "min_order_qty": 2,
    "stock_qty": 6,
    "delivery_days": 5,
    "delivery_price": "7.50",
}]

try:
    result = save_imported_offers(records, source="JSON", admin_id=admin_id)
    # Pēc veiksmīgas commit: {"added": 0, "updated": 1}, ja piedāvājums jau bija.
except OfferImportError as error:
    # error.row: rindas numurs no 1 vai None kopīgai kļūdai.
    # error.field: lauks vai None. str(error): drošs paskaidrojums latviski.
    # Adapteris parāda kļūdu lietotājam; šīs paketes izmaiņas nav saglabātas.
    message = str(error)
```

`admin_id` jāiegūst no autorizētā administratora, `source` — no izmantotā
adaptera (`CSV`, `JSON` vai `API`). Importa ieraksts nedrīkst noteikt autoru,
datu avotu vai atjaunināšanas laiku. Serviss pārbauda, vai administrators
eksistē un ir aktīvs. JSON augšupielādes maršruts pieprasa administratora
autorizāciju un CSRF pārbaudi; tas jānodrošina arī nākamajiem adapteriem.

## Ieraksta formāts

| Lauks | Noteikumi |
| --- | --- |
| `product_sku` | Obligāts esošas aktīvas preces kods, līdz 100 rakstzīmēm. |
| `supplier_id` / `supplier_name` | Vismaz viens: esoša aktīva piegādātāja ID vai nosaukums. Ja abi ir norādīti, tiem jāsakrīt. Nosaukumā normalizē atstarpes un burtu reģistru. |
| `supplier_sku` | Obligāts piegādātāja preces kods, līdz 100 rakstzīmēm. |
| `currency` | Obligāta vērtība `EUR`. Citas valūtas netiek pārrēķinātas. |
| `unit_price` | Obligāta cena no 0 līdz 99999999.99, ne vairāk kā divas zīmes aiz komata. |
| `vat_included` | Obligāts `true`/`false` vai `1`/`0` (arī virknes). |
| `vat_rate` | No 0 līdz 100 %, ne vairāk kā divas zīmes aiz komata. Obligāta cenai bez PVN; cenai ar PVN var nenorādīt. |
| `min_order_qty` | Obligāts vesels skaitlis no 1 līdz 2147483647. |
| `stock_qty`, `delivery_days` | Obligāti veseli skaitļi no 0 līdz 2147483647. |
| `delivery_price` | Neobligāta maksa ar tādiem pašiem ierobežojumiem kā cenai. Ja nav norādīta, izmanto piegādātāja aktuālo piegādes maksu. |
| `is_active` | Neobligāts `true`/`false` vai `1`/`0`. Jaunam piedāvājumam noklusējums ir aktīvs; esošam saglabā iepriekšējo statusu. |

Naudas vērtības pārvērš par `Decimal`, pieņem arī decimālo komatu. Negatīvi
skaitļi, NaN, Infinity, eksponentu pieraksts, pārmērīga precizitāte, vadības
rakstzīmes tekstā un neatbalstīti lauki izraisa kļūdu. Būla vērtības nevar
izmantot cenas vai daudzuma vietā. Adapteriem ieteicams cenas nodot kā virknes,
lai saglabātu avota precizitāti. Tukša pakete atgriež abus skaitītājus ar 0.

## Identitāte, atjaunināšana un atomiskums

- Piedāvājuma identitāte ir `(supplier_id, supplier_sku)`, neatkarīgi no
  importa avota. Ja CSV ierakstu vēlāk saņem no API, to atjaunina.
- Vienā paketē atkārtota identitāte tiek noraidīta, nevis klusi pārrakstīta.
  Vienāds kods dažādiem piegādātājiem ir atļauts.
- Ja kods jau piesaistīts citai StockFlow precei, imports apstājas. Preces
  saiti un sākotnējā administratora ID esošam piedāvājumam nemaina.
- Vecu piedāvājumu bez `supplier_id` var atrast pēc precīza piegādātāja
  saglabātā nosaukuma un tā preces koda un piesaistīt esošajam piegādātājam.
  Ja kandidāti ir vairāki, jānovērš neskaidrība pirms importa.
- Atjaunina cenas, PVN nosacījumus, atlikumu, minimālo daudzumu, piegādi,
  avotu un `updated_at` (UTC). Arī atkārtota veiksmīga tāda paša piedāvājuma
  saņemšana skaitās atjaunināšana un saglabā veiksmīgās saņemšanas laiku.
- Vispirms pārbauda visu paketi. Saglabāšana notiek vienā transakcijā ar
  vienu `commit`; kļūdas gadījumā veic `rollback`. Skaitītājus atgriež tikai
  pēc veiksmīgas saglabāšanas. Arī iepriekšējais atjaunināšanas laiks paliek
  nemainīgs, ja imports neizdodas.
- MySQL piegādātāju rindas bloķē noteiktā ID secībā; unikālais datubāzes
  indekss aizsargā identitāti arī paralēlas saglabāšanas gadījumā. Datubāzes
  konflikts izraisa visas paketes atcelšanu; adapteris var piedāvāt atkārtot importu.
- Piedāvājumus neaizstāj ar jaunām rindām: groza un pasūtījumu saites paliek.
  Saglabātie pasūtījumu cenu momentuzņēmumi netiek mainīti.

Serviss pārvalda savas paketes `commit`/`rollback`. Tam nedrīkst nodot sesiju
ar citām neapstiprinātām izmaiņām; neizmantot vienā transakcijā ar citu datu
rediģēšanu. Nesaglabātas ORM izmaiņas, kas vēl nav nosūtītas datubāzei, tiek
noraidītas pirms importa.

## Migrācija un Railway

Pirms pirmās izmantošanas piemēro `0007_offer_import_identity`:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
```

Migrācija pievieno unikālu indeksu `uq_offers_supplier_sku` uz `offers`
kolonnām `supplier_id`, `supplier_sku`. Tā nepārbūvē tabulu, nedzēš
piedāvājumus un saglabā grozu un pasūtījumu saites. Veciem manuāliem
ierakstiem bez koda vai bez piegādātāja saites NULL vērtības paliek atļautas.
Ja jau eksistē dublikāti ar aizpildītiem abiem laukiem, migrācija apstājas:
administratoram jāpārskata attiecīgie piedāvājumi un jāsalabo identitāte.
Vienkārša deaktivizēšana dublikātu nenovērš, jo neaktīviem piedāvājumiem
jāsaglabā sava identitāte atkārtotam importam.

Railway projekta esošais `preDeployCommand` jau izpilda `db upgrade`;
pēc šo izmaiņu izvietošanas atsevišķa pieslēguma konfigurācija nav vajadzīga.

Pārbaudes: `tests/test_offer_import.py` ietver atkārtotu importu no visiem
trim avotiem, kļūdainas rindas, datubāzes atteici, laika un vēstures
saglabāšanu, dublikātu aizsardzību un migrācijas abos virzienos.
