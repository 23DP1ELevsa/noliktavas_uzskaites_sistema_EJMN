# StockFlow saskarnes pārveides pārskats

## Dizaina izmaiņas

Visas esošās lapas izmanto vienotu gaišu noformējumu: tumši zils teksts, balti
paneļi, zili un violeti akcenti, kopīga tipogrāfija un vienāda komponentu sistēma.
Pārveidota sākumlapa, navigācija un kājene, katalogs, preču kartītes, piedāvājumu
salīdzināšana, grozs, noformēšana, pieteikumi, autentifikācija, profils,
paziņojumi un visas administrēšanas un importa lapas.

Mobilā navigācija atveras ar pogu un aizveras ar Escape. Platās tabulas ritinās
savā fokusējamā apgabalā. Formām ir grupēti lauki, etiķetes, kļūdu skaidrojumi
un latviska pārlūka validācija. Kategorijas dzēšanai ir latvisks dialogs;
importam — faila izvēles vadīkla ar atlasītā faila nosaukumu. Attēla ielādes
kļūdas gadījumā redzams preces iniciālis.

Saglabāti Flask maršruti, lomas, Jinja dati, lauku nosaukumi, CSRF un
JavaScript piesaistes. Datubāzes shēma un biznesa aprēķini nav mainīti.
Lokalizētas pārlūka kļūdu lapas un pieslēgšanās prasības paziņojums;
saglabāti HTTP statusi un atbildes galvenes.

## Mainītie faili

- `backend/app/static/css/style.css`: pārveidota kopējā dizaina sistēma.
- `backend/app/static/js/app.js`: kartītes, latvisks cenu attēlojums, ielādes un
  kļūdu stāvokļi, pieprasījumu secības kontrole.
- `backend/app/static/js/ui.js`: kopīgā navigācija, validācija, faila izvēle,
  apstiprināšanas dialogs un administratora attēlu aizstājēji.
- `backend/app/templates/`: visas pilnās lapu veidnes un saistītie komponenti;
  pievienotas `_icons.html` un `error.html`. Precīzs lapu saraksts ir
  [dizaina sistēmas dokumentā](ui-redesign.md#lapu-pārklājums).
- `backend/app/__init__.py`, `backend/app/extensions.py`: pārlūka kļūdu un
  autentifikācijas paziņojumu lokalizācija.
- `tests/test_ui_contract.py`: lokalizācijas, piekļuves un HTTP/API līgumu testi.
- `scripts/ui_qa.py`: reproducējama pārlūka pārbaude ar atsevišķu testa datubāzi.
- `README.md`, `docs/ui-redesign.md`, `docs/ui-verification.md` un šis pārskats:
  dokumentācija un pārbaužu norādes.

## Automātiskie funkcionālie testi

Komanda `python -m pytest tests -q -p no:cacheprovider` projekta `.venv` vidē:
**616 testi izturēti, 1 izlaists**. Tas aptver esošās autentifikācijas,
kataloga, salīdzināšanas, groza, pieteikumu, administrēšanas, importa un
krājumu pārbaudes, kā arī jaunās saskarnes valodas un HTTP līgumu pārbaudes.
Visas 44 Jinja veidnes veiksmīgi parsētas; `git diff --check` kļūdu nav.

## Pārlūka un izkārtojuma pārbaudes

Izmantots instalētais Chrome un pagaidu SQLite datubāze. Projekta `.env`
datubāze netika mainīta. Izveidoti arī testa pasūtījumi, tukšs konts un kļūdu
stāvokļi.

| Pārbaude | Apjoms | Rezultāts |
| --- | --- | --- |
| Visas lapas un stāvokļi | 44 varianti × 7 platumi × 2 mērogi = 616 pārbaudes | Veiksmīgi |
| Gari nosaukumi, liela cena, 80 papildu preces un nederīga attēla adrese | 12 varianti × 7 platumi × 2 mērogi = 168 pārbaudes | Veiksmīgi |
| Noslēguma izmaiņas pieslēgšanās, kategoriju un importa vadīklās | 24 papildu pārbaudes | Veiksmīgi |

Platumi: **320, 375, 425, 768, 1024, 1440 un 1920 px**. Katrā pamatpārbaudē
vērtēts dokumenta platums, elementi ārpus skata, aprēķinātais teksta kontrasts,
lauku etiķetes, attēli, angļu kļūdu paziņojumi un JavaScript izņēmumi.
Noslēguma pārskatos nevienā no šīm kategorijām kļūdas nav atrastas.
Veikta arī reprezentatīvo darbvirsmas un mobilo ekrānattēlu apskate.

Visas **37 pārlūka mijiedarbības pārbaudes** izturētas. Pārbaudīta mobilā
izvēlne, Escape un Tab, meklēšana, filtri, kārtošana,
reģistrācija un pieslēgšanās, salīdzināšanas daudzums, groza papildināšana un
labošana, pieteikuma iesniegšana, paziņojums profilā, administratora lēmums,
reālas JSON un CSV failu augšupielādes, API importa panākums un kļūda.
Kategorijas dzēšanas dialogam pārbaudīta atvēršana, atcelšana, Escape,
fokusa atgriešana un dzēšana atsevišķā testa kategorijā.

JSON pārskati un ekrānattēli saglabāti ignorētajā mapē `instance/ui-qa/`:
`final/`, `errors-interactions/`, `stress-final/`, `controls-final/` un
`dialog-final/`. Pēdējā dialoga pārbaudē pie 320 px un 200% ekvivalenta
virsraksts ir redzams un fokusēts, un iekšējas horizontālās ritjoslas nav.
Pārbaudes var atkārtot pēc [norādēm](ui-verification.md).

## Pārbaudes robežas

200% mērogs pārbaudīts ar uz pusi samazinātu CSS skata laukumu un pikseļu
attiecību 2; pārlūka rīkjoslas mērogs netika manuāli pārslēgts. Kontrasta
pārbaude izmanto aprēķinātās teksta un vienkrāsas fona krāsas; tā nav pilns
manuāls piekļūstamības audits.

MySQL konkurējošu pasūtījumu tests SQLite vidē tiek izlaists, jo tam vajadzīgs
atsevišķs MySQL serveris un rindu bloķēšana. Pārbaude pret produkcijas vai
Railway datubāzi netika veikta. Operētājsistēmas failu atlasītāja valodu nosaka
lietotāja sistēmas iestatījumi.
