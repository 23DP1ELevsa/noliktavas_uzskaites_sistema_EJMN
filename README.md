# StockFlow — noliktavas un iepirkumu uzskaites sistēma

StockFlow ir B2B tīmekļa lietotne vairāku piegādātāju preču meklēšanai, piedāvājumu salīdzināšanai un iepirkumu pieteikumu pārvaldībai. Pircējs saglabā uzņēmuma datus, veido grozu un seko pieteikumiem. Administrators pārvalda piegādātājus, kategorijas, preces, piedāvājumus un izskata pieteikumus.

## Komanda

- Eduards Levša
- Jegors Gurjevs
- Maksims Koršunovs
- Nikita Kolcovs

## Tehnoloģijas un prasības

- Python 3.11+, Flask 3 un Flask-Login.
- SQLAlchemy, Flask-SQLAlchemy un Flask-Migrate/Alembic datubāzes darbībām un migrācijām.
- MySQL 8.4 un PyMySQL; lokālai demonstrācijai un testiem var izmantot SQLite.
- HTML/Jinja2, CSS un JavaScript; Node.js būvēšana nav nepieciešama.
- pytest; pārlūka pārbaudēm Chrome vai Edge.
- Docker Desktop ar Docker Compose lokālajam MySQL; alternatīva ir instalēts MySQL 8.0.16+.
- Gunicorn un Railway konfigurācija izvietošanai Linux vidē.

## Projekta struktūra

```text
backend/app/
├─ models/           Datubāzes modeļi
├─ routes/           Autentifikācija, katalogs, grozs un administratora darbības
├─ services/         Importi, salīdzināšana, pasūtījumi un paroles prasības
├─ templates/        Jinja2 lapu veidnes
├─ static/           CSS, JavaScript un attēli
├─ commands.py       db-check un seed-demo komandas
└─ config.py         Vides un datubāzes konfigurācija
data_samples/        Demonstrācijas katalogs un importa piemēri
migrations/          Datubāzes shēmas migrācijas
scripts/ui_qa.py      Pārlūka un ekrāna izmēru pārbaudes
tests/               Automatizētie testi
compose.yaml         Lokālā MySQL konfigurācija
railway.json         Izvietošanas konfigurācija
run.py               Lietotnes palaišana
requirements.txt     Python atkarības
.env.example         Konfigurācijas paraugs
```

## Palaišana

Komandas izpilda PowerShell terminālī no projekta saknes mapes.

### 1. Virtuālā vide un konfigurācija

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Iegūto nejaušo vērtību ieraksta `.env` mainīgajā `SECRET_KEY`. MySQL piemērs:

```dotenv
SECRET_KEY=šeit-ievieto-ģenerēto-vērtību
DATABASE_URL=mysql+pymysql://stockflow:stockflow@127.0.0.1:3306/stockflow?charset=utf8mb4
```

### 2. Datubāze

```powershell
docker compose up -d --wait
```

Docker sagatavo datubāzi `stockflow` un lietotāju `stockflow`. Savam MySQL serverim `.env` norāda tā pieslēguma datus. Demonstrācijai bez Docker var iestatīt `DATABASE_URL=sqlite:///stockflow.db`; fails tiks izveidots `instance/` mapē, Docker komandu izlaiž.

### 3. Migrācijas, demonstrācijas dati un serveris

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m flask --app run db-check
.\.venv\Scripts\python.exe -m flask --app run seed-demo
.\.venv\Scripts\python.exe run.py
```

Sākumlapa: <http://127.0.0.1:5000/>. Katalogs: `/catalog/page`. Pieslēgšanās: `/auth/login`. Veselības pārbaude: `/health`.

Jauna konta parolei vajag **vismaz 8 rakstzīmes, 1 lielo burtu un 1 speciālo simbolu**, piemēram, `!`, `@` vai `#`. Rakstīšanas laikā pie katras prasības redzams sarkans × vai zaļš ✓. Atstarpe nav speciālais simbols; tiek atbalstīti arī latviešu lielie burti. Serveris neatkarīgi pārbauda tās pašas prasības.

## Demonstrācijas dati un testa piekļuve

`seed-demo` ielādē `data_samples/demo_catalog.json`: 4 kategorijas, 10 preces (9 aktīvas), 3 piegādātājus, 18 piedāvājumus (17 aktīvus), 2 kontus, pircēja uzņēmuma profilu un grozu ar 2 pozīcijām. Piegādātāji: **Demo NordTech**, **Demo Baltic Supply**, **Demo Office Hub**.

| Loma | E-pasts | Sākotnējā parole |
| --- | --- | --- |
| Testa administrators | `admin.demo@stockflow.test` | `DemoAdmin123!` |
| Testa pircējs | `user.demo@stockflow.test` | `DemoUser123!` |

Šie ir publiski demonstrācijas konti. Administratoram pēc pieslēgšanās atveras `/admin`. Pircējam sagatavots profils **Demo Uzņēmums SIA**. Paroles datubāzē glabājas jaucējkodu veidā.

Komandu var atkārtot: esošās paroles, cenas, profila dati un grozs netiek atiestatīti. Sākotnējās paroles darbojas, ja konti izveidoti ar noklusētajām vērtībām. Jauniem kontiem citas paroles norāda ar `DEMO_ADMIN_PASSWORD`, `DEMO_USER_PASSWORD` vai `seed-demo --admin-password 'CitaParole!' --user-password 'PircējaParole!'`.

Demonstrēšanai katalogā meklē **kabelis**, salīdzini piegādātāju cenas un minimālos daudzumus. Izmanto pircēja grozu, iesniedz pieteikumu un administratora panelī to apstiprini vai noraidi. Paziņojumi un vēsture pieejami profilā. Iesniedzot pieteikumu, atlikums tiek rezervēts; noraidot rezervācija tiek atbrīvota.

## Piedāvājumu imports

Administratora sadaļā **Imports** ir JSON, CSV un API cilnes. Piemēri: `data_samples/offers_import.json` un `data_samples/offers_import.csv`. Precēm un piegādātājiem jau jābūt sistēmā; kļūdas gadījumā datu kopa netiek daļēji saglabāta. Atkārtots imports atjaunina piedāvājumu pēc tā identitātes, ņemot vērā vietējās rezervācijas.

Iebūvētais demonstrācijas avots ir `GET /api/test/offers`. `TEST_API_URL` ļauj norādīt citu avotu; noklusējums ir lietotnes HTTP adrese ar `PORT` (lokāli 5000). Importā piegādātāja atlikums nozīmē kopējo atlikumu pirms StockFlow vietējām rezervācijām.

## Testēšana

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts/ui_qa.py --interactions --screenshots representative
```

Testi izmanto atsevišķu SQLite datubāzi. Ar `MYSQL_TEST_URL` var pārbaudīt MySQL, izveidojot un pēc pārbaudes dzēšot atsevišķu testa shēmu.

Pārlūka rīks izmanto Chrome/Edge un pagaidu demonstrācijas datubāzi. Tas pārbauda viesa, pircēja un administratora lapas pie 320, 375, 425, 768, 1024, 1440 un 1920 px, arī 200% mēroga ekvivalentu. Rezultāti un ekrānattēli: `instance/ui-qa/`. Nestandarta pārlūka ceļam norāda `--browser 'C:\ceļš\chrome.exe'`.

```powershell
# Konkrētu lapu pārbaude
.\.venv\Scripts\python.exe scripts/ui_qa.py --pages home register catalog cart product-edit --widths 320 768 1440 --zooms 1 2
# Gari nosaukumi un liels preču skaits
.\.venv\Scripts\python.exe scripts/ui_qa.py --stress --screenshots representative
```

## Uzturēšana un izvietošana

```powershell
# Pēc modeļu izmaiņām izveidot un piemērot migrāciju
.\.venv\Scripts\python.exe -m flask --app run db migrate -m "Shēmas izmaiņas"
.\.venv\Scripts\python.exe -m flask --app run db upgrade
# Apturēt MySQL, saglabājot datus
docker compose stop
```

`railway.json` pirms servera palaišanas izpilda migrācijas un `db-check`. Flask servisam iestata `SECRET_KEY` un `DATABASE_URL`, kas norāda uz MySQL servisu (piemēram, `${{MySQL.MYSQL_URL}}`). Palaišanas komanda: `gunicorn run:app --bind 0.0.0.0:$PORT --threads 4`. Demonstrācijas datus ielādē ar `python -m flask --app run seed-demo` attiecīgā servisa vidē.
