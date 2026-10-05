# StockFlow

StockFlow ir B2B tīmekļa platforma, kas apkopo vairāku piegādātāju preču piedāvājumus vienā katalogā. Lietotājs var meklēt preces, salīdzināt cenas, atlikumus, piegādes laikus un citus nosacījumus, kā arī izveidot vienu kopīgu pasūtījuma pieteikumu no vairākiem piegādātājiem.

## Projekta mērķis

Izveidot pārskatāmu sistēmu, kas samazina manuālu preču meklēšanu vairākās piegādātāju vietnēs un palīdz uzņēmumiem izvēlēties izdevīgākos piedāvājumus.

## Galvenās funkcijas

* publisks preču katalogs;
* preču meklēšana un filtrēšana;
* piegādātāju piedāvājumu salīdzināšana;
* lietotāju reģistrācija un autorizācija;
* lietotāju lomas: viesis, lietotājs un administrators;
* grozs un pasūtījuma izveide;
* pasūtījumu statusu pārvaldība;
* administratora panelis;
* produktu, piegādātāju un piedāvājumu CRUD darbības;
* datu imports no CSV un JSON;
* testa REST API datu saņemšana;
* backend automātiskie testi.

## Izmantotās tehnoloģijas

* Python 3.11+
* Flask
* Flask-SQLAlchemy
* MySQL
* Flask-Login autorizācijai un lietotāju lomām
* HTML
* CSS
* Bootstrap
* JavaScript
* pytest
* CSV, JSON un REST API datu importa modulis
* GitHub
* Trello
* Figma
* draw.io

## Projekta struktūra

```text
backend/
  app/
    models/        Datubāzes modeļi
    routes/        Auth, katalogs, piedāvājumi, grozs, pasūtījumi, admin un imports
    services/      Biznesa loģikas servisi
    templates/     Flask HTML veidnes
    static/        CSS, JavaScript un citi statiskie faili

tests/             Automātiskie testi
data_samples/      CSV, JSON un demonstrācijas dati
docs/              Diagrammas un projekta dokumentācija
run.py             Flask lietotnes palaišanas fails
README.md
requirements.txt
.gitignore
```

## Lokālā palaišana

1. Izveido virtuālo vidi:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Uzinstalē projekta atkarības:

```powershell
pip install -r requirements.txt
```

3. Nokopē `.env.example` uz `.env` un norādi lokālās MySQL datubāzes parametrus.
   MySQL un Railway konfigurēšana: [datubāzes instrukcija](docs/database-setup.md).
   Datubāzē ir deviņas tabulas atbilstoši apstiprinātā dokumenta 2.3. sadaļai.
   [Modeļu shēma un ierobežojumi](docs/database-schema.md).

   Izveido tabulas un pārbaudi savienojumu:

   ```powershell
   python -m flask --app run db upgrade
   python -m flask --app run db-check
   ```

4. Palaid lietotni:

```powershell
py run.py
```

5. Atver lietotni pārlūkprogrammā:

```text
http://127.0.0.1:5000/
```

Veselības pārbaude ir pieejama adresē:

```text
http://127.0.0.1:5000/health
```

## Testi

Automātiskos testus var palaist ar komandu:

```powershell
pytest
```

## Komanda

* **Eduards Levša** — projekta vadītājs un backend izstrādātājs
* **Jegors Gurjevs** — datubāzes un piegādātāju datu moduļa izstrādātājs
* **Maksims Koršunovs** — frontend un UX/UI izstrādātājs
* **Ņikita Koļcovs** — administratora moduļa, testēšanas un dokumentācijas izstrādātājs

## Darba organizēšana

Uzdevumi tiek plānoti Trello dēlī, izmantojot kolonnas:

`Backlog → To Do → In Progress → Review → Done`

Katra funkcija tiek izstrādāta atsevišķā Git branch un pēc pārbaudes apvienota ar galveno projekta versiju, izmantojot Pull Request.

## Saites

* GitHub: https://github.com/23DP1ELevsa/noliktavas_uzskaites_sistema_EJMN
* Trello: https://trello.com/invite/b/6a980a4d46d02ba825dca092/ATTId64451d8734b100e5c32b12e75aa47a5E8EB929A/projekts

## Projekta statuss

Projekts atrodas izstrādes stadijā.
