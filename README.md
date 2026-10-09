# StockFlow

StockFlow ir B2B tīmekļa platforma, kas apkopo vairāku piegādātāju preču piedāvājumus vienā katalogā. Lietotāji var meklēt preces, salīdzināt cenas, atlikumus un piegādes laikus, kā arī veidot pasūtījumu pieteikumus no vairākiem piegādātājiem.

## Projekta mērķis

Samazināt manuālu preču meklēšanu dažādās piegādātāju vietnēs un palīdzēt uzņēmumiem izvēlēties izdevīgākos piedāvājumus.

## Galvenās funkcijas

* publisks preču katalogs, meklēšana un filtrēšana;
* piegādātāju piedāvājumu salīdzināšana;
* lietotāju reģistrācija, autorizācija un lomas;
* grozs un pasūtījumu izveide un statusu pārvaldība;
* administratora panelis un produktu, piegādātāju un piedāvājumu pārvaldība;
* datu imports no CSV un JSON, kā arī izmēģinājuma REST API datu saņemšana;
* backend automātiskie testi.

## Tehnoloģijas

Python 3.11+, Flask, Flask-SQLAlchemy, Flask-Migrate, MySQL, Flask-Login,
HTML, CSS, Bootstrap, JavaScript un pytest.

## Projekta struktūra

```text
backend/app/        Modeļi, maršruti, servisi, veidnes un statiskie faili
data_samples/       CSV, JSON un demonstrācijas dati
migrations/         Datubāzes migrācijas
tests/              Automātiskie testi
compose.yaml        Lokālā MySQL konteinera konfigurācija
run.py              Flask lietotnes palaišanas fails
requirements.txt    Python atkarības
```

## Prasības

* Python 3.11 vai jaunāka versija.
* Lokālai MySQL palaišanai ar Docker — Docker Desktop ar Compose atbalstu.
* Ja izmanto jau instalētu datubāzi, MySQL 8.0.16 vai jaunāka versija (ieteicams MySQL 8.4).

## Kā palaist ar Docker

Šajā projektā Docker Compose palaiž tikai MySQL 8.4 datubāzes konteineri. Flask lietotne darbojas lokāli ar Python virtuālajā vidē. Komandas paredzētas PowerShell un izpildei no projekta saknes mapes.

### Pēc pirmās uzstādīšanas

Ja virtuālā vide, `.env` fails, Python atkarības un datubāzes migrācijas jau ir sagatavotas, lietotni palaid šādi:

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe run.py
```

Pēc tam atver [http://127.0.0.1:5000/](http://127.0.0.1:5000/) pārlūkprogrammā. Flask process jāatstāj darbojoties atvērtajā PowerShell logā. Lai to apturētu, nospied `Ctrl+C`.

### Pirmā palaišanas reize

1. Pārliecinies, ka ir instalēts Python 3.11 vai jaunāks un Docker Desktop ar Compose atbalstu.

2. Izveido virtuālo vidi un nokopē vides mainīgo paraugu. `.env` izveido tikai pirmajā palaišanas reizē; esošu konfigurācijas failu nepārraksti.

   ```powershell
   py -m venv .venv
   Copy-Item .env.example .env
   ```

3. `.env` failā nomaini `SECRET_KEY` pret unikālu, nejaušu un slepenu vērtību:

   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
   ```

   Piemērā norādītā `DATABASE_URL` un parole atbilst `compose.yaml` noklusējuma konfigurācijai. `.env` failu neiekļauj versiju kontrolē.

4. Uzstādi Python atkarības un palaid MySQL konteineri:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   docker compose up -d --wait
   ```

   Pirmajā reizē Docker lejupielādēs MySQL attēlu. Datubāze `stockflow` un lietotājs `stockflow` tiks izveidoti automātiski. Dati tiek glabāti Docker sējumā, bet datubāzes ports ir pieejams tikai lokālajā datorā (`127.0.0.1:3306`).

5. Izveido datubāzes tabulas ar migrācijām un pārbaudi savienojumu:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run db upgrade
   .\.venv\Scripts\python.exe -m flask --app run db-check
   ```

   Veiksmīga `db-check` izpilde apstiprina savienojumu un visu deviņu lietotnes tabulu esamību. Lietotne pati tabulas neveido, tāpēc migrācija jāizpilda pirms pirmās palaišanas.

6. Palaid Flask lietotni:

   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```

   Atver [http://127.0.0.1:5000/](http://127.0.0.1:5000/) pārlūkprogrammā. Veselības pārbaude pieejama [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health).

### Ikdienas Docker komandas

```powershell
# Pārbaudīt konteineru stāvokli
docker compose ps

# Apskatīt MySQL žurnālus
docker compose logs -f mysql

# Apturēt MySQL, saglabājot datubāzes datus
docker compose stop

# Atkal palaist iepriekš apturēto MySQL konteineri
docker compose start

# Apturēt un noņemt konteineri, saglabājot sējumu
docker compose down
```

Lai pilnībā atiestatītu lokālo datubāzi, ieskaitot visus datus, izmanto `docker compose down -v` un pēc tam vēlreiz `docker compose up -d --wait`. Šo komandu izmanto tikai tad, ja datu zudums ir pieņemams.

## Palaišana ar jau instalētu MySQL

Izveido datubāzi un atsevišķu lietotāju (paroli aizstāj ar savu):

```sql
CREATE DATABASE IF NOT EXISTS stockflow
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'stockflow'@'localhost' IDENTIFIED BY 'replace-this-password';
GRANT ALL PRIVILEGES ON stockflow.* TO 'stockflow'@'localhost';
```

Nokopē `.env.example` uz `.env`, iestati nejaušu `SECRET_KEY` un `DATABASE_URL` ar datubāzes pieslēguma parametriem. Ja lietotājvārdā vai parolē ir īpašas rakstzīmes, tās URL adresē nokodē (piemēram, `@` kā `%40`). Pēc tam izpildi iepriekš norādītās atkarību uzstādīšanas, migrācijas, savienojuma pārbaudes un palaišanas komandas.

Konfigurācijai izmantotais prioritātes secīgums ir lietotnes konfigurācija, `DATABASE_URL`, `MYSQL_URL` un visbeidzot lokālā noklusējuma adrese. Sistēmas vides mainīgie ir prioritāri pār `.env` faila vērtībām. MySQL adreses ar shēmu `mysql://` lietotne pārveido uz PyMySQL draivera formātu, un, ja nav norādīts, pievieno `utf8mb4` rakstzīmju kopu.

## Railway datubāze

1. Railway projektā pievieno MySQL servisu.
2. Ja Flask lietotne atrodas tajā pašā Railway projektā un vidē, Flask servisa mainīgajos iestati `DATABASE_URL=${{MySQL.MYSQL_URL}}` (ja datubāzes servisa nosaukums ir cits, `MySQL` aizstāj ar tā nosaukumu) un iestati atsevišķu nejaušu `SECRET_KEY`.
3. Ja lokālā lietotne pieslēdzas Railway datubāzei, MySQL servisa **Settings → Networking** sadaļā iespējo **Public Access** un lokālajā `.env` failā kā `DATABASE_URL` norādi `MYSQL_PUBLIC_URL`. Railway privātā adrese `*.railway.internal` no lokālā datora nav sasniedzama.
4. Izpildi `flask --app run db upgrade` un `flask --app run db-check` vidē, kurai ir piekļuve datubāzei. Šajā projektā Railway `preDeployCommand` izpilda abas komandas pirms lietotnes palaišanas; migrācijas nedrīkst izpildīt būvēšanas laikā, jo privātais tīkls būvēšanas laikā nav pieejams. Lietotnes palaišanai konfigurēts Gunicorn WSGI serveris.

Vairāk informācijas: [Railway MySQL](https://docs.railway.com/databases/mysql) un [Railway privātais tīkls](https://docs.railway.com/networking/private-networking/how-it-works).

## Datubāzes shēma

Sākotnējā migrācija izveido deviņas pamatdatu tabulas; `alembic_version` ir migrāciju servisa tabula un šajā skaitā nav iekļauta.

| Tabula | Nolūks | Unikālie lauki |
| --- | --- | --- |
| `users` | Lietotāju konti, paroles jaucējkods, loma un statuss | `email` |
| `company_profiles` | Lietotājam piesaistīts uzņēmuma profils | `user_id` |
| `categories` | Preču kategorijas | `name` |
| `products` | Kategorijas preces un to apraksti | `sku` |
| `offers` | Produkta piegādātāja piedāvājums, cena, atlikums un piegāde | — |
| `carts` | Lietotāja aktīvais grozs | `user_id` |
| `cart_items` | Grozā izvēlētie piedāvājumi un daudzumi | (`cart_id`, `offer_id`) |
| `orders` | Pircēja pasūtījums, statuss un kopsumma | — |
| `order_items` | Pasūtījumā fiksētā piedāvājuma informācija un daudzums | — |

Galvenās saites: profilam un grozam ir lietotājs; prece pieder kategorijai, piedāvājums — precei; groza rinda piesaista piedāvājumu; pasūtījums piesaista pircēju un uzņēmuma profilu, bet tā rindas glabā pasūtījuma brīdī fiksētās vērtības. Atsevišķa piegādātāju tabula shēmā nav paredzēta.

MySQL tabulās tiek lietota InnoDB un `utf8mb4` (`utf8mb4_unicode_ci`). Identifikatori un ārējās atslēgas ir `BIGINT UNSIGNED`; SQLite testos lieto `INTEGER`. Cenas ir `DECIMAL(10,2)`, pasūtījumu un rindu summas — `DECIMAL(12,2)`. Python naudas aprēķinos izmanto `Decimal`, nevis `float`.

Obligātie lauki ir `NOT NULL`, izņemot uzņēmuma PVN numuru un tālruni, kategorijas un preces aprakstus, preces zīmolu un modeli, piedāvājuma piegādātāja SKU, administratora piezīmi un apstrādes informāciju, kā arī pasūtījuma rindas saiti uz piedāvājumu. Noklusētās vērtības: lietotāja loma `user` un aktīvs konts; preces vienība `gab.` un aktīva prece; piedāvājuma minimālais daudzums 1, atlikums un piegādes cena/laiks 0, datu avots `manual` un aktīvs piedāvājums; aktīvs grozs; pasūtījuma statuss `iesniegts`. Datumi pēc noklusējuma tiek iestatīti datubāzē.

Atļautās lomas ir `user` un `admin`; pasūtījuma statusi — `iesniegts`, `apstiprināts`, `noraidīts`; datu avoti — `manual`, `CSV`, `JSON`, `API`. Datubāze pārbauda obligātos laukus, unikālumu un ierobežojumus: daudzumiem jābūt pozitīviem, bet cenām, atlikumiem, piegādes laikiem un summām — nenegatīviem. Paroles iestata un pārbauda ar lietotāja modeļa paroļu metodēm.

Preču kategorijas ar precēm un preces ar piedāvājumiem nevar dzēst. Pasūtījumu un piedāvājumu autoru vēsture tiek aizsargāta no dzēšanas; kontu deaktivizēšanai izmanto `is_active`. Dzēšot grozu, tiek dzēstas tā rindas; dzēšot piedāvājumu, groza rindas tiek dzēstas, bet pasūtījuma rindā piedāvājuma saite kļūst tukša. Pasūtījuma rindās tiek saglabāti nosaukuma, cenas, PVN, daudzuma, piegādes un summas momentuzņēmumi, lai vēsture nemainītos līdz ar piedāvājumu.

Lietojumprogrammas līmenī jānodrošina arī tas, ka piedāvājumu autori un pasūtījumu apstrādātāji ir administratori, pasūtījuma profils pieder pircējam, daudzums atbilst minimālajam pasūtījumam un atlikumam, pasūtījums nav tukšs un to nevar apstrādāt atkārtoti. Veidojot pasūtījumu, piedāvājuma vērtības un summas jāsaglabā vienā transakcijā. Pamatdatu shēma pati šos biznesa nosacījumus un summu aprēķinus automātiski nepārbauda.

## Kataloga API

`GET /catalog` nolasa aktīvās preces no datubāzes un atbalsta nosaukuma meklēšanu
(`q`), kategoriju (`category_id`), cenu (`min_price`, `max_price`), piegādātāju
(`supplier`) un pieejamību (`in_stock`). Filtrus var izmantot vienlaicīgi.
Piemēri, atbildes un atlases noteikumi: [kataloga API](docs/catalog-api.md).

## Demonstrācijas dati

Pēc migrācijām demonstrācijas datubāzē izpildi:

```powershell
.\.venv\Scripts\python.exe -m flask --app run seed-demo
```

Komanda pievieno 4 kategorijas, 10 preces, 18 piedāvājumus no 3 piegādātājiem,
administratora un pircēja testa kontus, uzņēmuma profilu un grozu ar 2 pozīcijām.
Atkārtota palaišana neveido dublikātus un nepārraksta esošās paroles vai datus.
Pēc ielādes atver `/catalog/page` vai galvenajā lapā spied **Atvērt katalogu**.
[Testa konti, scenāriji un ielādes noteikumi](docs/demo-data.md).

### Demonstrācijas konti

Pēc veiksmīgas `seed-demo` izpildes pieejami šādi konti ar noklusējuma parolēm:

| Loma | E-pasts | Parole |
| --- | --- | --- |
| Administrators | `admin.demo@stockflow.test` | `DemoAdmin123!` |
| Pircējs | `user.demo@stockflow.test` | `DemoUser123!` |

Ja kontu izveides laikā norādītas pielāgotas paroles ar `DEMO_ADMIN_PASSWORD`,
`DEMO_USER_PASSWORD` vai komandas parametriem, izmanto tās. Atkārtota `seed-demo`
palaišana esošo kontu paroles nemaina.

## Migrācijas

Migrācijas atrodas `migrations/`. Pēc modeļu shēmas izmaiņām izveido un piemēro jaunu migrāciju:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db migrate -m "Describe schema change"
.\.venv\Scripts\python.exe -m flask --app run db upgrade
```

`db upgrade` piemēro tikai vēl neizpildītās migrācijas. Migrāciju vietā neizmanto `db.create_all()`. Komanda `db downgrade base` dzēš tabulas un datus, tāpēc to izmanto tikai atsevišķā, iznīcināmā testa datubāzē.

## Testi

Palaid automātiskos testus:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Bez papildu iestatījumiem modeļu testi izmanto SQLite ar ieslēgtām ārējām atslēgām. MySQL testēšanai konfigurē atsevišķu testa lietotāju ar globālām `CREATE` un `DROP` privilēģijām, jo katrai izpildei tests izveido nejaušu datubāzi. `MYSQL_TEST_URL` jānorāda servera pieslēguma adrese bez datubāzes nosaukuma. Nepieslēdz testus produkcijas datubāzei un neizmanto lietotāju bez vajadzīgajām privilēģijām (piemēram, lokālā Compose konfigurācijā lietotājam `stockflow` tās nav):

```powershell
$env:MYSQL_TEST_URL = 'mysql+pymysql://<test-user>:<password>@127.0.0.1:3306'
.\.venv\Scripts\python.exe -m pytest tests -q
Remove-Item Env:MYSQL_TEST_URL
```

MySQL testu izpilde izveido nejauši nosauktu `stockflow_test_<uuid>` datubāzi un pēc tam dzēš tikai to. Testi pārbauda modeļus, saites, ierobežojumus, paroles, pasūtījumu vēstures saglabāšanu, dzēšanas uzvedību, transakciju kļūmju atcelšanu un migrāciju.

## Komanda

* **Eduards Levša** — projekta vadītājs un backend izstrādātājs
* **Jegors Gurjevs** — datubāzes un piegādātāju datu moduļa izstrādātājs
* **Maksims Koršunovs** — frontend un UX/UI izstrādātājs
* **Ņikita Koļcovs** — administratora moduļa, testēšanas un dokumentācijas izstrādātājs

## Darba organizēšana

Uzdevumi tiek plānoti Trello dēlī, izmantojot kolonnas:

`Backlog → To Do → In Progress → Review → Done`

Katra funkcija tiek izstrādāta atsevišķā Git zarā un pēc pārbaudes apvienota ar galveno projekta versiju, izmantojot Pull Request.

## Saites

* GitHub: https://github.com/23DP1ELevsa/noliktavas_uzskaites_sistema_EJMN
* Trello: https://trello.com/invite/b/6a980a4d46d02ba825dca092/ATTId64451d8734b100e5c32b12e75aa47a5E8EB929A/projekts

## Projekta statuss

Projekts atrodas izstrādes stadijā.
