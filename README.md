# StockFlow

StockFlow ir B2B tīmekļa platforma, kas apkopo vairāku piegādātāju preču piedāvājumus vienā katalogā. Lietotājs var meklēt preces, salīdzināt cenas, atlikumus, piegādes laikus un citus nosacījumus, kā arī izveidot vienu kopīgu pasūtījuma pieteikumu no vairākiem piegādātājiem.

## Projekta mērķis

Izveidot pārskatāmu sistēmu, kas samazina manuālu preču meklēšanu vairākās piegādātāju vietnēs un palīdz uzņēmumiem izvēlēties izdevīgākos piedāvājumus.

## Galvenās funkcijas

- publisks preču katalogs;
- preču meklēšana un filtrēšana;
- piegādātāju piedāvājumu salīdzināšana;
- lietotāju reģistrācija un autorizācija;
- lietotāju lomas: viesis, lietotājs un administrators;
- grozs un pasūtījuma izveide;
- pasūtījumu statusu pārvaldība;
- administratora panelis;
- produktu, piegādātāju un piedāvājumu CRUD darbības;
- datu imports no CSV un JSON;
- testa REST API datu saņemšana;
- backend automātiskie testi.

## Izmantotās tehnoloģijas

- Python
- Flask
- Flask-SQLAlchemy
- MySQL
- HTML
- CSS
- Bootstrap
- JavaScript
- pytest
- GitHub
- Trello
- Figma
- draw.io

## Projekta struktūra

```text
backend/        - servera loģika
templates/      - HTML veidnes
static/         - CSS, JavaScript un citi statiskie faili
tests/          - automātiskie testi
docs/           - projekta dokumentācija
data_samples/   - CSV, JSON un testa dati
README.md
requirements.txt
.gitignore
```

## Komanda

- **Eduards Levša** — projekta vadītājs un backend izstrādātājs
- **Jegors Gurjevs** — datubāzes un piegādātāju datu moduļa izstrādātājs
- **Maksims Koršunovs** — frontend un UX/UI izstrādātājs
- **Ņikita Koļcovs** — administratora moduļa, testēšanas un dokumentācijas izstrādātājs

## Darba organizēšana

Uzdevumi tiek plānoti Trello dēlī, izmantojot kolonnas:

`Backlog → To Do → In Progress → Review → Done`

Katra funkcija tiek izstrādāta atsevišķā Git branch un pēc pārbaudes apvienota ar Pull Request.

## Saites

- GitHub: https://github.com/23DP1ELevsa/noliktavas_uzskaites_sistema_EJMN
- Trello: https://trello.com/invite/b/6a980a4d46d02ba825dca092/ATTId64451d8734b100e5c32b12e75aa47a5E8EB929A/projekts

## Projekta statuss

Projekts atrodas izstrādes stadijā.
