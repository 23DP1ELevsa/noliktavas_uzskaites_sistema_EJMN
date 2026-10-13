# CSV piedāvājumu imports

Administrators atver **Admin panelis → Imports → CSV** (`/admin/import/csv`),
izvēlas failu un nospiež **Importēt CSV**. Lapa izmanto to pašu noformējumu,
formas aizsardzību un rezultātu paziņojumus kā JSON imports. Paraugu var
lejupielādēt no lapas vai atrast
[`data_samples/offers_import.csv`](../data_samples/offers_import.csv).

Paraugs izmanto demonstrācijas preces un piegādātājus. Demonstrācijas
datubāzē ar `seed-demo` sagatavotiem datiem tas atjaunina divus piedāvājumus.
Citā datubāzē pielāgo kodus un piegādātāju nosaukumus esošiem aktīviem
ierakstiem. Imports piemēro visas failā norādītās cenas un atlikumus.

## Faila struktūra

UTF-8 (atļauts BOM), līdz 2 MiB, līdz 10 000 piedāvājumiem. Pirmā rinda
ir galvene. Automātiski atpazīst komatu vai semikolu kā atdalītāju pēc
galvenes. Kolonnu secība var atšķirties; to nosaukumi ir reģistrjutīgi un
sakrīt ar [JSON](json-import.md) un [kopīgā importa](offer-import.md) laukiem.

```csv
product_sku,supplier_name,supplier_sku,currency,unit_price,vat_included,vat_rate,min_order_qty,stock_qty,delivery_price,delivery_days
DEMO-DRILL-001,Demo Baltic Supply,DEMO-BS-DRILL,EUR,74.00,false,21.00,2,6,7.50,5
```

Obligātās kolonnas: `product_sku`, `supplier_sku`, `currency`, `unit_price`,
`vat_included`, `min_order_qty`, `stock_qty`, `delivery_days`, kā arī
`supplier_id` vai `supplier_name`. `vat_rate` nepieciešama piedāvājumiem,
kuru cenā PVN nav iekļauts. Neobligātas ir `delivery_price` un `is_active`.

- Cenas un PVN likmes pārvērš par `Decimal`, daudzumus, ID un piegādes dienas
  — par veseliem skaitļiem. Atļauti decimālais punkts un komats; eksponenti,
  NaN, Infinity, negatīvas cenas un pārmērīga precizitāte nav atļauti.
- `vat_included` un `is_active`: `true`/`false` vai `1`/`0`; burtu reģistrs
  šīm vērtībām nav svarīgs.
- Teksta kodi paliek teksts, saglabājot sākuma nulles. Šūnu malu atstarpes
  noņem pirms kopīgās pārbaudes.
- Tukšas neobligātās šūnas izlaiž. Ja piegādes maksa nav norādīta, izmanto
  piegādātāja maksu; ja nav `is_active`, esošam piedāvājumam saglabā statusu.
  Tukša obligātā šūna ir kļūda. Tukši abi piegādātāja lauki ir kļūda.
- Atkārtotas, tukšas vai neatbalstītas galvenes kolonnas tiek noraidītas.
  Katrā datu rindā jābūt tieši tik šūnām, cik galvenē.
- Pilnīgi tukšas datu rindas izlaiž, saglabājot fizisko rindu numerāciju.
  Rinda ar atdalītājiem un tukšām šūnām nav tukša rinda. Tukšs fails nav
  derīgs; pareiza galvene bez datiem ir derīga un dod rezultātu 0/0.

Ja vērtībā ir atdalītājs vai pēdiņas, izmanto CSV pēdiņu noteikumus:
piemēram, `"Piegādātājs, SIA"`. Ar komatu atdalītā failā decimālajam
komatam arī nepieciešamas pēdiņas: `"74,00"`. Semikola formātā tās nav vajadzīgas:

```csv
product_sku;supplier_name;supplier_sku;currency;unit_price;vat_included;vat_rate;min_order_qty;stock_qty;delivery_price;delivery_days
DEMO-DRILL-001;Demo Baltic Supply;DEMO-BS-DRILL;EUR;74,00;false;21,00;2;6;7,50;5
```

## Kļūdas un saglabāšana

CSV kļūdai rāda fizisko faila rindu (galvene ir 1. rinda), lauku un iemeslu.
Tiek ņemtas vērā arī tukšas rindas un pēdiņās iekļautas šūnas, kas aizņem
vairākas faila rindas. Šādas šūnas kļūdai izmanto datu rindas sākuma numuru.
Galvenes kļūdas norāda 1. rindu. Arī datubāzes preču/piegādātāju pārbaudes
kļūdas pārvērš no ieraksta numura uz sākotnējo CSV rindas numuru.

`read_csv_offers(stream)` pieņem bināru faila plūsmu, pārbauda galveni,
struktūru un visas vērtības, izmantojot `validate_import_record`. Tas
nepiekļūst datubāzei un atgriež kopīgā formāta sarakstu ar `Decimal`,
`int` un `bool` vērtībām. `CSVRecords.lines` glabā sākotnējos rindu numurus.

`import_csv_offers(stream, admin_id=...)` nodod visu normalizēto sarakstu
`save_imported_offers(..., source="CSV", admin_id=...)`. Ja kaut kas nav
derīgs, imports nesaglabā daļējas izmaiņas. Piegādātājs un tā preces kods
nosaka identitāti neatkarīgi no avota: CSV un JSON par vienu piedāvājumu
atjaunina to pašu datubāzes rindu. Rezultāts ir `added` un `updated` skaits.

```python
from backend.app.services.csv_import import import_csv_offers

with open("data_samples/offers_import.csv", "rb") as source:
    result = import_csv_offers(source, admin_id=authenticated_admin_id)
```

Nepieciešams Flask lietotnes konteksts un tīra datubāzes sesija. Failā
nedrīkst noteikt autoru, avotu vai atjaunināšanas laiku. Tīmekļa lapa un
parauga lejupielāde pieejama tikai administratoram; saglabāšana prasa CSRF kodu.

Jauna migrācija vai atkarība nav vajadzīga. Railway pietiek ar parasto
izvietošanu; CSV augšupielādē administratora panelī, nepieslēdzoties
datubāzei no lokālā termināļa. Pārbaudes: `tests/test_csv_import.py`.
