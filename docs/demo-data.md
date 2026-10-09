# StockFlow demonstrācijas dati

Komanda `seed-demo` sagatavo datus kataloga, piedāvājumu salīdzināšanas un
turpmākās pasūtījuma plūsmas demonstrēšanai. Tā izmanto lietotnes pašreizējo
datubāzes konfigurāciju (`DATABASE_URL` vai README aprakstīto alternatīvu).

## Palaišana

Konfigurē demonstrācijas datubāzes pieslēgumu `.env` failā vai vides mainīgajos.
No projekta saknes izpildi:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
.\.venv\Scripts\python.exe -m flask --app run seed-demo
.\.venv\Scripts\python.exe run.py
```

Atver `http://127.0.0.1:5000/catalog/page` vai galvenajā lapā spied **Atvērt
katalogu**. Aktuālā kataloga lapa nolasa kategorijas un saņem preces no `/catalog`.
Ja datubāze jau ir migrēta un lietotne darbojas, pietiek ar `seed-demo` un lapas
pārlādi. Šai izmaiņai nav vajadzīgas jaunas migrācijas vai atkarības.

Datu komplekts glabājas
[`data_samples/demo_catalog.json`](../data_samples/demo_catalog.json).
Naudas vērtības ir virknes, kuras ielādē pārveido par `Decimal`. Tas ir demo
ielādes formāts, nevis nākotnes importa API līgums.

## Komplektā iekļautie dati

| Dati | Skaits tukšā datubāzē |
| --- | ---: |
| Kategorijas | 4 |
| Preces | 10, no tām 9 aktīvas |
| Piegādātāji piedāvājumos | 3 |
| Piedāvājumi | 18, no tiem 17 aktīvi |
| Konti | 2 |
| Pircēja uzņēmuma profils | 1 |
| Pircēja grozs | 1 ar 2 pozīcijām |

Kategorijas: Elektronika, Biroja preces, Instrumenti, Saimniecības preces.
Piegādātāji ir izdomāti: **Demo NordTech**, **Demo Baltic Supply**, **Demo Office Hub**.
Tie glabājas `offers.supplier_name`, kā paredz shēma; atsevišķu piegādātāju tabulu
vai kontu nav. Prefikss `DEMO-` preču un piegādātāju SKU ir rezervēts šim komplektam.

## Testa konti

| Loma | E-pasts | Sākotnējā parole |
| --- | --- | --- |
| Administrators | `admin.demo@stockflow.test` | `DemoAdmin123!` |
| Pircējs | `user.demo@stockflow.test` | `DemoUser123!` |

Paroles ir publiskas demo vērtības, tāpēc šie konti paredzēti demonstrācijas
videi. Datubāzē paroles glabājas tikai kā jaucējkodi. Pieslēgšanās lapa:
`/auth/login`. Pircējam ir fiktīvs profils **Demo Uzņēmums SIA**.

Jauniem kontiem var norādīt citas paroles (vismaz 8 rakstzīmes):

```powershell
$env:DEMO_ADMIN_PASSWORD = 'your-demo-admin-password'
$env:DEMO_USER_PASSWORD = 'your-demo-user-password'
.\.venv\Scripts\python.exe -m flask --app run seed-demo
Remove-Item Env:DEMO_ADMIN_PASSWORD
Remove-Item Env:DEMO_USER_PASSWORD
```

Pieejamas arī opcijas `--admin-password` un `--user-password`. Esošo kontu
paroles netiek mainītas pat tad, ja atkārtotai izpildei norāda jaunas vērtības.

## Demonstrācijas scenāriji

1. `/catalog` atgriež 9 aktīvas preces. Arhīva kaste `DEMO-BOX-001` ir arhivēta
   un publiskajā katalogā nav redzama.
2. `/catalog?q=kabelis` rāda USB-C kabeli ar diviem aktīviem piedāvājumiem:
   NordTech — 9.99 EUR, MOQ 1, atlikums 120, piegāde 3.50 EUR vienā dienā;
   Baltic Supply — 8.49 EUR, MOQ 5, atlikums 40, piegāde 5.00 EUR trīs dienās.
   Trešais piedāvājums par 7.99 EUR ir neaktīvs un netiek rādīts.
3. Pildspalvu cenas ir 0.65 un 0.49 EUR, minimālie daudzumi — 10 un 50.
   Urbju piedāvājumiem atšķiras arī PVN statuss. PVN netiek pārrēķināts.
4. `/catalog?in_stock=false` atgriež tīrītāju (atlikums 0) un cimdus (atlikums 2,
   minimālais daudzums 5). Pelei ir izpārdots piedāvājums un pieejams alternatīvs
   piedāvājums. Kataloga lapā atzīme **Tikai pieejamās** paslēpj nepieejamās preces.
5. Kombinācija
   `/catalog?q=kabelis&supplier=Demo%20NordTech&min_price=9&max_price=10&in_stock=true`
   atgriež kabeli ar cenu 9.99 EUR. UI piegādātāja laukā ievadi pilno nosaukumu
   `Demo NordTech`. Kategorijām izmanto reālos ID, nevis pieņem fiksētas vērtības.
6. Pircēja grozā ir 2 NordTech USB-C kabeļi un 5 Office Hub papīra pakas.
   Abi daudzumi atbilst minimālajam daudzumam un atlikumam. Pēc projekta formulas
   sākotnējā summa ir `2 × 9.99 + 3.50 + 5 × 4.50 + 2.50 = 48.48 EUR`.

Grozs ir datubāzē sagatavots piemērs. Šī komanda neievieš groza un pasūtījumu
maršrutus un nerada iesniegtus pasūtījumus; šo moduļu darbība ir atsevišķs uzdevums.

## Atkārtojamība un komandas kopīgie dati

Komandu var atkārtot secīgi. Tā izdrukā tikai jaunizveidoto ierakstu skaitu;
nemainītā datubāzē otrajā izpildē visi skaiti ir 0.

- Kategorijas atpazīst pēc nosaukuma; jau esoši apraksti netiek mainīti.
- Kontus atpazīst pēc e-pasta; parole, vārds un aktivitāte tiek saglabāta.
  Ja kontam ir cita loma, ielāde tiek atcelta, nevis mainītas tā tiesības.
- Preces atpazīst pēc SKU, piedāvājumus — pēc produkta un piegādātāja SKU.
  Cenas, atlikumi, piegādātāja attēlojamais nosaukums un aktivitāte netiek atiestatīti.
  Ja vienai demo piedāvājuma identitātei jau ir dublikāti, komanda ziņo par kļūdu.
- Esošs uzņēmuma profils un grozs tiek saglabāts. Izņemtu groza pozīciju komanda
  neatjauno; sākotnējās pozīcijas pievieno tikai jauna groza izveidē. Ja iepriekš
  labots piedāvājums vairs nav pasūtāms šajā daudzumā, pozīciju nepievieno.
- Trūkstošus ierakstus izveido no jauna. Citi dati netiek dzēsti. Lai saglabātu
  demo ierakstu identitāti, nemaini rezervētos SKU un demo kontu e-pastus.

Visas izmaiņas ir viena transakcija: kļūda neatstāj daļēji saglabātu komplektu.
Izpildi komandu secīgi, nevis reizē no vairākiem termināļiem: `offers` tabulai
nav unikāla demo identifikatora, kas garantētu paralēlas ielādes deduplikāciju.

## Railway

Pēc koda izvietošanas demo vides terminālī ar pareizo `DATABASE_URL` izpildi:

```text
python -m flask --app run db upgrade
python -m flask --app run seed-demo
```

Automātiska datu ielāde `preDeployCommand` nav pievienota. Lokālam pieslēgumam
Railway izmanto README aprakstīto publisko MySQL URL. Pēc ielādes pārlādē katalogu.

## Testi

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_demo_data.py -q
```

Pārbaudes aptver komplektu, atkārtojamību, citu datu un manuālo izmaiņu
saglabāšanu, lomu konfliktus, transakcijas atcelšanu, kontu pieslēgšanos, groza
derīgumu, katalogu un aktuālo `/catalog/page`. Ar `MYSQL_TEST_URL` tās pašas
pārbaudes izmanto arī atsevišķu MySQL/MariaDB testa datubāzi.
