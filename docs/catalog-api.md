# Kataloga meklēšana un filtri

Publiskais `GET /catalog` nolasa aktīvās preces no datubāzes. Autorizācija nav
vajadzīga. Atlase notiek SQL vaicājumā; demonstrācijas saraksts vairs netiek lietots.
Pirms pirmās palaišanas jāizpilda projekta migrācijas un jāievada preces un
piedāvājumi. Tukša datubāze atgriež tukšu katalogu.

## Pieprasījuma parametri

| Parametrs | Vērtība | Darbība |
| --- | --- | --- |
| `q` | Teksts līdz 255 rakstzīmēm | Preces nosaukuma daļa, neņemot vērā lielos/mazos burtus |
| `category_id` | Pozitīvs BIGINT UNSIGNED ID | Precīza kategorijas atlase |
| `min_price` | 0–99999999.99 | Piedāvājuma vienības cenas apakšējā robeža, ieskaitot |
| `max_price` | 0–99999999.99 | Piedāvājuma vienības cenas augšējā robeža, ieskaitot |
| `supplier` | Nosaukums līdz 255 rakstzīmēm | Pilns piegādātāja nosaukums, neņemot vērā lielos/mazos burtus |
| `in_stock` | `true`/`1` vai `false`/`0` | Pieejamas preces vai preces bez pieejama piedāvājuma |

Visi parametri ir neobligāti un savstarpēji kombinējami (AND). Tukšas vērtības
un atstarpes ap vērtībām tiek ignorētas. Katru parametru var norādīt vienu reizi.
Cenai izmanto punktu un ne vairāk kā divas zīmes aiz tā; negatīvas vērtības,
`NaN`, bezgalība un apgriezts cenu intervāls tiek noraidīti ar HTTP 400.
Meklēšanas simboli `%`, `_` un `/` tiek uztverti burtiski, nevis kā SQL šabloni.
MySQL teksta salīdzināšanā darbojas tabulu `utf8mb4_unicode_ci` kolācija.
SQLite lokālajās pārbaudēs `lower()` atbalsta arī latviešu burtus.

Piemērs ar visiem filtriem (kategorijas ID aizstāj ar savas datubāzes vērtību):

```text
/catalog?q=kabelis&category_id=1&min_price=5&max_price=20&supplier=North&in_stock=true
```

Piegādātāju un citu parametru vērtībām ar atstarpēm vai īpašām rakstzīmēm izmanto
URL kodēšanu, piemēram, pārlūka `URLSearchParams`.

## Piedāvājumu un pieejamības noteikumi

Tiek izmantoti tikai aktīvu preču aktīvie piedāvājumi. Cena un piegādātājs
jāsakrīt vienā piedāvājumā: lēts piedāvājums no viena piegādātāja nevar izpildīt
cenas filtru kopā ar cita piegādātāja dārgo piedāvājumu. Produkts rezultātā
parādās vienu reizi neatkarīgi no atbilstošo piedāvājumu skaita.

Piedāvājums ir pieejams, ja `stock_qty >= min_order_qty`. Tātad pozitīvs atlikums,
kas nesasniedz minimālo pasūtāmo daudzumu, nav pietiekams.

- Bez `in_stock` filtrēšanas atbildē ir visi cenas un piegādātāja filtriem
  atbilstošie aktīvie piedāvājumi.
- Ar `in_stock=true` ir tikai piedāvājumi, kuru atlikums sasniedz minimālo
  daudzumu; precei jābūt vismaz vienam šādam piedāvājumam.
- Ar `in_stock=false` ir preces, kurām nav pieejama piedāvājuma izvēlētajā
  cenas/piegādātāja atlasē. Ja tie nav norādīti, te ietilpst arī preces bez
  aktīviem piedāvājumiem.
- Ar cenas vai piegādātāja filtru precei obligāti jābūt atbilstošam aktīvam
  piedāvājumam. Bez šiem filtriem un bez `in_stock=true` katalogā var būt arī
  aktīvas preces bez piedāvājumiem: `price=null`, `available=false`, `offers=[]`.

Atbildes `price` ir zemākā atlasītā piedāvājuma vienības cena EUR, bez piegādes
maksas. PVN statuss ir norādīts katram piedāvājumam; PVN netiek pārrēķināts.
Filtrējot pēc piegādātāja vai pieejamības, šī cena var mainīties. Salīdzināšana
datubāzē izmanto DECIMAL; JSON cenas saglabā iepriekšējo skaitlisko formātu.

## Atbilde

HTTP 200 atbildes struktūra paliek `items`, `count`, `message`.
Preces sakārtotas pēc ID; piedāvājumi — pēc cenas un pēc ID vienādām cenām.

```json
{
  "items": [
    {
      "id": 1,
      "sku": "USB-001",
      "name": "USB-C kabelis",
      "category_id": 1,
      "category": "Elektronika",
      "brand": null,
      "model": null,
      "description": null,
      "unit": "gab.",
      "active": true,
      "price": 8.99,
      "currency": "EUR",
      "available": true,
      "offer_count": 1,
      "offers": [
        {
          "id": 1,
          "supplier_name": "North",
          "supplier_sku": null,
          "unit_price": 8.99,
          "vat_included": true,
          "min_order_qty": 2,
          "stock_qty": 10,
          "delivery_price": 0,
          "delivery_days": 0,
          "available": true,
          "updated_at": "2026-10-08T10:00:00Z"
        }
      ]
    }
  ],
  "count": 1,
  "message": null
}
```

Ja nekas nav atrasts, HTTP 200:

```json
{"items": [], "count": 0, "message": "Preces netika atrastas."}
```

Ja filtrs nav derīgs, HTTP 400:

```json
{
  "error": "invalid_filters",
  "field": "max_price",
  "message": "Maksimālā cena nedrīkst būt mazāka par minimālo cenu."
}
```

## Pārbaude un integrācija

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_catalog.py -q
```

Testi izmanto migrētu SQLite datubāzi; ar `MYSQL_TEST_URL` tie paši scenāriji
tiek izpildīti arī atsevišķā MySQL/MariaDB testa datubāzē, kā aprakstīts README.
Pārbaudīta arī vaicājumu skaita neatkarība no preču skaita nelielam katalogam:
preces/kategorijas un piedāvājumi tiek ielādēti kopīgi, nevis atsevišķi katrai precei.

Šī izmaiņa ievieš servera API. Sākumlapas meklēšanas forma un filtru saskarne
jāpieslēdz šim API frontend uzdevumā. Papildu migrācijas, atkarības un Railway
mainīgie šai izmaiņai nav nepieciešami.
