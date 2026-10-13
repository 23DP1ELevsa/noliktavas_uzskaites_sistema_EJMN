# Komandas testa REST API un piedāvājumu saņemšana

Komandas demonstrācijas adrese ir `GET /api/test/offers` tajā pašā StockFlow
vietnē. Lokāli: `http://127.0.0.1:5000/api/test/offers`. Railway: vietnes
publiskais domēns ar ceļu `/api/test/offers`. Atbilde ir HTTP 200,
`Content-Type: application/json` un piedāvājumu masīvs ar diviem izdomātiem
demo ierakstiem no `data_samples/offers_import.json`.

Endpoint neprasa autorizāciju un nelasa datubāzi: tas vienmēr rāda tikai
publicēto demonstrācijas paraugu, nevis reālas cenas, lietotājus vai pasūtījumus.
Lauki sakrīt ar [JSON](json-import.md), [CSV](csv-import.md) un
[kopīgā importa formātu](offer-import.md).

## Saņemšana no StockFlow

Administrators atver **Admin panelis → Imports → API** (`/admin/import/api`)
un nospiež **Saņemt un importēt piedāvājumus**. StockFlow serveris veic
HTTP GET, pārbauda atbildi un nodod visu sarakstu kopīgajai saglabāšanai ar
`source="API"`. Pēc veiksmīga importa parādās `added` / `updated` skaits.
Atkārtots imports vai tas pats piedāvājums no CSV/JSON atjaunina esošo rindu.

Pirms demonstrācijas precēm un piegādātājiem jābūt izveidotiem; piemērotā
demo datubāzē tos sagatavo `seed-demo`. Ja tie neeksistē, visa pakete tiek
noraidīta ar ieraksta numuru un kļūdaino lauku. Importa lapa saglabā esošo
paneļa noformējumu; POST pieprasa administratora sesiju un CSRF kodu.

Noklusētā avota adrese ir
`http://127.0.0.1:<PORT vai 5000>/api/test/offers`. Tā ir **servera** adrese,
nevis pārlūka savienojums ar administratora datoru. Tādēļ noklusētā adrese
darbojas arī Railway konteinerī. Avotu neņem no Host galvenes vai formas
ievades. Vajadzības gadījumā konfigurē `TEST_API_URL` Flask servisa vides
mainīgajos, piemēram, citas komandas testa API pilnu HTTP/HTTPS adresi.

## Atbildes pārbaude un kļūdas

- Pieprasa HTTP 200; 204, 4xx/5xx un pāradresācijas izraisa kļūdu.
- Pieprasa `application/json` vai `application/*+json`. Saspiešana netiek
  pieprasīta; neatbalstītu `Content-Encoding` noraida.
- Atbildi lasa ar 2 MiB ierobežojumu un to pašu JSON pārbaudi kā failu
  importā: UTF-8, masīvs, līdz 10 000 ierakstiem, obligātie lauki,
  pareizie datu tipi, precīzas `Decimal` cenas un bez atkārtotiem JSON laukiem.
- Savienojumam un atbildes lasīšanas operācijām izmanto 5 sekunžu socket
  timeout. Savienojuma atteice, timeout un nepilnīgs HTTP ķermenis dod
  saprotamu paziņojumu; kļūdaino atbildi neimportē.
- Vispirms saņem un pārbauda visu atbildi. HTTP kļūdas nevar izraisīt
  daļējas datubāzes izmaiņas. Saglabāšanas kļūdai kopīgais serviss veic
  visas paketes rollback un saglabā iepriekšējos atjaunināšanas laikus.

`fetch_api_offers(url, timeout=5)` veic pieprasījumu un atgriež normalizētu
sarakstu, nepiekļūstot datubāzei. `import_api_offers(url, admin_id=...,
timeout=5)` pēc saņemšanas izmanto `save_imported_offers`.
`APIImportError` manto `OfferImportError`; strukturālām kļūdām saglabā
ieraksta numuru un lauku. `admin_id` jāņem no autorizētā administratora,
URL — no servera konfigurācijas. URL drīkst būt HTTP/HTTPS, bez iebūvēta
lietotājvārda/paroles, fragmenta vai vadības rakstzīmēm.

## Railway un lokāla palaišana

Jauna datubāzes migrācija vai Python atkarība šai funkcijai nav vajadzīga.
Pēc parastās izvietošanas izmanto API cilni. `railway.json` Gunicorn komandai
pievienots `--threads 4`: viens pavediens apstrādā importa formu, cits var
atbildēt uz tajā pašā lietotnē izvietotā testa API pieprasījumu.

Ja Railway panelī Start Command ir norādīta manuāli, izmanto:

```text
gunicorn run:app --bind 0.0.0.0:$PORT --threads 4
```

Vienas lietotnes pieprasījumi izmanto kopīgu pavedienu kopu. Ja testa API
vēlāk izvieto atsevišķā servisā, iestati `TEST_API_URL` uz tā adresi.
Ārējo API formā nevar izvēlēties ar patvaļīgu URL; mainīgo konfigurē projekta
uzturētājs. HTTPS sertifikāti tiek pārbaudīti, pāradresācijas netiek sekotas.

Lokālai atsevišķa testa API demonstrācijai var atvērt otro termināli:

```powershell
.\.venv\Scripts\python.exe test_api.py
```

Tas palaiž neatkarīgu API uz `http://127.0.0.1:5001/api/test/offers`, bez
datubāzes. StockFlow `.env` iestati
`TEST_API_URL=http://127.0.0.1:5001/api/test/offers` un pārstartē StockFlow.
Noklusētajai API vienā StockFlow lietotnē otrais process nav nepieciešams.

Testi: `tests/test_api_import.py` ietver īstu lokālu HTTP serveri, sekmīgu
saņemšanu, timeout, pāradresāciju noraidīšanu, kļūdainus statusus/ķermeņus,
kopīgo identitāti, atkārtotu importu, rollback un administratora/CSRF aizsardzību.
