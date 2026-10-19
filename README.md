# StockFlow

Railway datu apmaiņas un pasūtījumu atlikumu izvietošana/pārbaude:
[soļi un nepieciešamie iestatījumi](docs/railway-verification.md).

StockFlow ir B2B tīmekļa lietotne, kas apvieno vairāku piegādātāju preču piedāvājumus vienā katalogā. Lietotāji var meklēt preces, salīdzināt piedāvājumus, veidot grozu un iesniegt pasūtījumus.

Saskarnes pārveide: [dizaina sistēma un lapu pārklājums](docs/ui-redesign.md),
[pārlūka pārbaužu palaišana](docs/ui-verification.md) un
[pārveides rezultāti](docs/ui-redesign-report.md).

## Tehnoloģijas

- Python 3.11+
- Flask 3
- Flask-SQLAlchemy un Flask-Migrate
- MySQL 8.4
- HTML, CSS, Bootstrap un JavaScript

## Projekta struktūra

```text
StockFlow/
├─ backend/       Flask lietotne, modeļi, maršruti un veidnes
├─ data_samples/  demonstrācijas dati
├─ migrations/    datubāzes migrācijas
├─ tests/         automātiskie testi
├─ compose.yaml   lokālās MySQL datubāzes konfigurācija
├─ run.py         lietotnes palaišanas fails
└─ requirements.txt
```

## Prasības

- Python `3.11+`
- Docker Desktop ar Docker Compose atbalstu

Lokāli var izmantot arī jau instalētu MySQL `8.0.16+`.

## Ātrais starts

Komandas paredzētas PowerShell un izpildei no projekta saknes mapes.

### 1. Virtuālā vide un konfigurācija

```powershell
py -m venv .venv
Copy-Item .env.example .env
```

Failā `.env` nomaini `SECRET_KEY` uz nejaušu vērtību:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Iegūto vērtību iestati `.env` failā, piemēram:

```dotenv
SECRET_KEY=your-secret-key
DATABASE_URL=mysql+pymysql://stockflow:stockflow@127.0.0.1:3306/stockflow?charset=utf8mb4
```

### 2. Atkarības un datubāze

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d --wait
```

Docker izveidos MySQL datubāzi `stockflow` un lietotāju `stockflow`.

### 3. Migrācijas un lietotnes palaišana

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m flask --app run db-check
.\.venv\Scripts\python.exe run.py
```

Lietotne būs pieejama: `http://127.0.0.1:5000/`

Veselības pārbaude: `http://127.0.0.1:5000/health`

## Demonstrācijas dati

Administratora piegādātāju pārvaldība aprakstīta failā
[Piegādātāju pārvaldība](docs/supplier-management.md).

Piedāvājumu salīdzināšana, daudzuma izvēle un lietotāja grozs ir aprakstīti
failā [Piedāvājumu salīdzināšana](docs/offer-comparison.md).

CSV, JSON un API adapteriem kopīgā piedāvājumu pārbaude un atomiskā saglabāšana,
ierakstu formāts un dublikātu aizsardzība ir aprakstīta
failā [Piedāvājumu imports](docs/offer-import.md).

JSON failu var augšupielādēt **Admin panelis → Imports** (`/admin/import/json`).
Paraugs: [`data_samples/offers_import.json`](data_samples/offers_import.json).
Struktūra, datu tipi un izmantošana: [JSON imports](docs/json-import.md).

CSV augšupielāde: **Admin panelis → Imports → CSV** (`/admin/import/csv`).
Paraugs: [`data_samples/offers_import.csv`](data_samples/offers_import.csv).
Kolonnas, atdalītāji un kļūdu rindu numerācija: [CSV imports](docs/csv-import.md).

Komandas testa REST API: `GET /api/test/offers`. Piedāvājumu saņemšana:
**Admin panelis → Imports → API** (`/admin/import/api`). HTTP pārbaudes,
timeout un Railway konfigurācija: [API imports](docs/api-import.md).

Uzņēmuma profila izveide, saglabāšana un ievades pārbaudes ir aprakstītas
failā [Uzņēmuma profils](docs/company-profile.md).

Pēc migrāciju izpildes ielādē testa kategorijas, preces, piedāvājumus un lietotājus:

```powershell
.\.venv\Scripts\python.exe -m flask --app run seed-demo
```

Demonstrācijas konti un to paroles ir aprakstītas failā [`docs/demo-data.md`](docs/demo-data.md).

Testa administratora piekļuve:

| Loma | E-pasts | Parole |
| --- | --- | --- |
| Administrators | `admin.demo@stockflow.test` | `DemoAdmin123!` |

Pēc pieslēgšanās administrators nonāk vienotajā **Admin panelī** (`/admin`).
Tajā ir sadaļas pieteikumiem, piegādātājiem, precēm, piedāvājumiem un kategorijām.
Administrators pats pievieno piegādātājus un preces, norāda cenas, PVN, atlikumus
un pasūtīšanas nosacījumus. [Paneļa apraksts](docs/admin-panel.md).
[Preču pārvaldības apraksts](docs/product-management.md).
[Pieteikumu iesniegšana, izskatīšana un profila paziņojumi](docs/order-workflow.md).
Komanda `seed-demo` izveido šo kontu,
ja tas vēl neeksistē; esoša konta parole netiek pārrakstīta.

## Noderīgas komandas

```powershell
# Izveidot jaunu migrāciju pēc modeļu izmaiņām
.\.venv\Scripts\python.exe -m flask --app run db migrate -m "Describe schema change"

# Piemērot migrācijas
.\.venv\Scripts\python.exe -m flask --app run db upgrade

# Pārbaudīt datubāzes savienojumu un tabulas
.\.venv\Scripts\python.exe -m flask --app run db-check

# Apturēt MySQL konteineri
docker compose stop

# Apturēt un noņemt konteineri, saglabājot datus
docker compose down
```

## Testēšana

Palaid visus testus:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Pēc noklusējuma testi izmanto SQLite. MySQL testēšanai iestati atsevišķu testa datubāzes serveri, izmantojot `MYSQL_TEST_URL`. Neizmanto produkcijas datubāzi.
