# Saskarnes pārbaude

Pārlūka pārbaudes rīks `scripts/ui_qa.py` izmanto projektā jau instalēto Python vidi un lokālu Chrome vai Edge. Playwright, Selenium un papildu pakotnes nav nepieciešamas. Rīks izveido pagaidu SQLite datubāzi, ielādē demonstrācijas datus un izveido pieteikumu ar esošo noformēšanas darbību. Konfigurācijā vienmēr norādīta šī atsevišķā datubāze; `.env` datubāze netiek izmantota.

Palaidiet komandas no projekta saknes PowerShell vidē:

```powershell
# Esošie funkcionalitātes un datubāzes migrāciju testi
.\.venv\Scripts\python.exe -m pytest tests -q

# Visas lapas un visi pieprasītie platumi; arī 200% mērogojuma ekvivalents
.\.venv\Scripts\python.exe scripts\ui_qa.py --interactions --screenshots all

# Gari nosaukumi, liela cena un palielināts preču skaits
.\.venv\Scripts\python.exe scripts\ui_qa.py --stress --screenshots all

# Ātra konkrētu lapu atkārtota pārbaude
.\.venv\Scripts\python.exe scripts\ui_qa.py --pages catalog cart product-edit --widths 320 375 1440 --zooms 1 2
```

Ja Chrome nav standarta mapē, norādiet `--browser 'C:\ceļš\chrome.exe'` vai vides mainīgo `CHROME_PATH`. Chrome palaišanai ierobežotā izpildes vidē var būt nepieciešama atļauja, jo tās noteikumi var bloķēt pārlūka grafikas apakšprocesu.

Rīks pārbauda 44 lapu un stāvokļu variantus viesa, pircēja, tukša pircēja konta un administratora lomā. Tie aptver sākumlapu, katalogu un tukšu meklējumu, preces piedāvājumus un nederīgu daudzumu, pieslēgšanos, reģistrāciju, profilu, grozu, noformēšanu, pieteikumu sarakstu un detaļas, administratora paneli, visus preču, piegādātāju, piedāvājumu un kategoriju sarakstus, detaļas, izveidi, labošanu un dzēšanas apstiprinājumus, visus trīs importa veidus un piekļuves/kļūdu stāvokļus. Groza servera kļūdas lapa tiek atvērta ar īpašu maršrutu, kas pastāv tikai šīs pagaidu pārbaudes procesā.

Katru variantu pārbauda pie 320, 375, 425, 768, 1024, 1440 un 1920 px. 200% ekvivalentam CSS skata laukums ir uz pusi mazāks, bet ierīces pikseļu attiecība ir 2. Tas pārbauda satura pārkārtošanos un lasāmību palielinājumā; tas nepārslēdz pārlūka rīkjoslas mēroga iestatījumu.

Pārskats `instance/ui-qa/<palaišanas-laiks>/report.json` satur dokumenta platumu, elementus ārpus skata, teksta kontrasta attiecības, lauku nosaukumus, attēlu problēmas, valodas norādes un JavaScript izņēmumus. Pēc noklusējuma tiek saglabāti 375 un 1440 px ekrānattēli. Ar `--screenshots all` attēli tiek saglabāti katrai kombinācijai. Izejas kods `1` nozīmē, ka pārskatā ir pārbaudāma kļūda. Pārlūka diagnostika pieejama `browser.log`.

Kontrasta pārbaude salīdzina aprēķināto teksta krāsu ar tā elementa un priekšteču vienkrāsas foniem. Parastam tekstam slieksnis ir 4,5:1, lielam tekstam 3:1; neaktīvas vadīklas tiek izlaistas. Attēlu un gradientu fonus rīks atzīmē atsevišķi kā vizuāli pārbaudāmus. Automātiskais pārskats neaizstāj ekrānattēlu apskati, īpaši pārklāšanās, kursora uzvedes un fokusa stāvokļu vērtēšanai.

Ar `--interactions` papildus tiek pārbaudīta mobilās izvēlnes atvēršana un aizvēršana ar Escape, fokuss ar Tab, latviska ievades lauku validācija, meklēšana, filtru notīrīšana, kārtošana, kategorijas un piegādātāja filtrs, īsta pieslēgšanās un reģistrācija, salīdzināšanas daudzuma automātiska iesniegšana, preces pievienošana un daudzuma labošana grozā, pieteikuma iesniegšana, profila paziņojums un administratora apstiprinājums. Kategorijas dzēšanas dialogu pārbauda pie 320 un 375 px, kā arī īsā skatā 200% ekvivalentā: sākuma fokusu, satura robežas, atcelšanu, Escape, fokusa atgriešanos un apstiprinātu dzēšanu. CSV/JSON pārbaudē tiek izvēlēts īsts fails sākotnējā `#import-file` laukā, pārbaudīta faila nosaukuma maiņa, veidlapas kļūda un veiksmīga augšupielāde; API pārbaudē — veiksmīgs imports un īslaicīgi nepieejams avots. Pārējās administratora darbības un importa datu integritātes un kļūdu scenārijus pārbauda esošā `tests/` kopa.
