# Railway: datu apmaiņa un pasūtījumu atlikumi

## Izvietošana

1. Izvietojiet šo koda versiju Flask servisā. `railway.json` pirms palaišanas
   jau izpilda `python -m flask --app run db upgrade` un `db-check`.
   Deploy žurnālā pārbaudiet migrāciju `0008_order_stock`.
2. Flask servisa `DATABASE_URL` jāatsaucas uz projekta MySQL servisu,
   piemēram, `${{MySQL.MYSQL_URL}}` (izmantojiet sava servisa nosaukumu).
   `localhost` apzīmē pašu Flask konteineri, nevis atsevišķo MySQL servisu.
3. Ja Start Command ir pārrakstīta Railway panelī, tai jābūt
   `gunicorn run:app --bind 0.0.0.0:$PORT --threads 4`.
   Noklusētā testa API adrese ir `http://127.0.0.1:<PORT>/api/test/offers`:
   tā ir HTTP saziņa ar pašu lietotni. `TEST_API_URL` uz lokālā datora
   portu 5001 darbojas tikai tad, ja atsevišķais API tiešām pieejams servisam.
   Noklusētajam testam noņemiet šo mainīgā pārrakstījumu.
4. Demonstrācijas paraugam vajag esošās demo preces un piegādātājus.
   Ja datubāze ir tukša, **Railway Flask servisa konteinerī** vienu reizi
   izpildiet `python -m flask --app run seed-demo`. Lokāla komanda bez
   Railway MySQL pieslēguma nepapildina izvietotās vietnes datubāzi.

Railway norādes: [pre-deploy migrācijas](https://docs.railway.com/deployments/pre-deploy-command),
[MySQL savienojums](https://docs.railway.com/databases/mysql),
[mainīgo atsauces](https://docs.railway.com/variables).

## Pārbaude vietnē

1. Ar administratoru atveriet **Imports → API**, importējiet paraugu un
   pārbaudiet rezultāta skaitītājus. CSV/JSON izmanto to pašu saglabāšanu.
2. Katalogā pierakstiet konkrētā piegādātāja piedāvājuma atlikumu N.
   Ar klientu pasūtiet Q vienības (ievērojot minimālo daudzumu).
   Pēc iesniegšanas atlikumam jābūt N−Q; cita piegādātāja atlikums nemainās.
3. Atkārtojiet to pašu importu: atlikums joprojām ir N−Q.
   Apstipriniet pieteikumu: atkārtota norakstīšana nenotiek.
4. Izveidojiet vēl vienu pieteikumu un noraidiet to ar iemeslu:
   tiek atcelta tikai šī pieteikuma rezervācija. Atkārtots lēmums dod 409
   un atlikumu nemaina.
5. Pēc pēdējo vienību pasūtīšanas cits klients tās nevar pasūtīt.

Imports saņem kopējo piegādātāja atlikumu pirms StockFlow lokālajiem
pasūtījumiem; [precīza nozīme un ierobežojumi](order-workflow.md#krājumu-migrācija-un-imports).
Testa API ir statisks demonstrācijas avots, nevis ārējā piegādātāja noliktava.
