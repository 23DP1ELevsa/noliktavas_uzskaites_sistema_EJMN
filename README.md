# StockFlow

StockFlow ir B2B tīmekļa lietotne, kas apvieno vairāku piegādātāju preču piedāvājumus vienā katalogā. Lietotāji var meklēt preces, salīdzināt piedāvājumus, veidot grozu un iesniegt pasūtījumus.

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

Pēc migrāciju izpildes ielādē testa kategorijas, preces, piedāvājumus un lietotājus:

```powershell
.\.venv\Scripts\python.exe -m flask --app run seed-demo
```

Demonstrācijas konti un to paroles ir aprakstītas failā [`docs/demo-data.md`](docs/demo-data.md).

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
