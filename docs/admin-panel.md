# Administratora panelis

Vienotais pārskats pieejams `/admin` un caur saiti **Admin panelis** publiskajās
lapās. Pēc administratora pieslēgšanās tas atveras automātiski, ja nav norādīta
cita lokāla mērķa adrese. Visās pārvaldības lapās ir kopīga sadaļu navigācija.

Panelī ir pieteikumi, piegādātāji, preces, piedāvājumi un kategorijas. Katra pārskata
sadaļa rāda ierakstu skaitu un saites pievienošanai un saraksta atvēršanai.
Pieteikumu sadaļa rāda izskatīšanu gaidošo pieteikumu skaitu un saites izskatīšanai
un visiem pieteikumiem. [Pieteikumu un paziņojumu apraksts](order-workflow.md).

## Piegādātāja preču pievienošana

1. Izveidojiet piegādātāju un norādiet piegādes maksu.
2. Piegādātāja lapā izvēlieties **Pievienot jaunu preci**. Pēc kataloga preces
   saglabāšanas atveras cenas un atlikuma forma ar jau izvēlēto piegādātāju un preci.
   Ja prece katalogā jau ir, izmantojiet **Piesaistīt esošu preci**.
3. Norādiet vienības cenu, PVN likmi un statusu, atlikumu, minimālo daudzumu un piegādes termiņu.
   Piegādātāja preces kods ir izvēles lauks. Piegādes maksa tiek ņemta no piegādātāja.

Piedāvājumu saraksts atrodas `/admin/supplier-products`; meklēšana darbojas
pēc preces nosaukuma, kataloga SKU, piegādātāja koda vai nosaukuma. Pieejams filtrs
pēc piedāvājuma aktivitātes statusa. Ierakstu var rediģēt
arī piegādātāja un kataloga preces detalizētajos skatos.

Cena pieņem komatu vai punktu un līdz divām zīmēm aiz komata. Daudzumiem un
termiņam jābūt veseliem nenegatīviem skaitļiem; minimālajam daudzumam jābūt vismaz 1.
PVN statusa izvēle un likme (0–100 %, līdz divām zīmēm aiz komata) ir obligāti.
Valūta ir EUR, tāpat kā katalogā un grozā. PVN netiek automātiski pieskaitīts
piegādātāja norādītajai cenai. Ja formā ir kļūda, ieraksts netiek saglabāts un ievade paliek.

## Izmaiņas un vēsture

Rediģējot var mainīt cenu, PVN likmi un statusu, atlikumu, minimālo daudzumu, termiņu, kodu un
aktivitāti. Saglabājot piemēro piegādātāja aktuālo piegādes maksu. Preci un jau
piesaistītu piegādātāju esošam ierakstam mainīt nevar; citai kombinācijai izveido jaunu
ierakstu. Agrākie piedāvājumi bez piegādātāja saites rediģējot jāpiesaista piegādātājam.

Deaktivizēšana saglabā groza rindas un pasūtījumu vēsturi; publiskais katalogs un
pasūtīšana izmanto tikai aktīvas preces, piegādātājus un piedāvājumus. Jau iesniegto
pasūtījumu nosaukumi, cenas un summas netiek pārrēķinātas. Jaunie ieraksti saglabā
administratoru kā autoru un `manual` kā datu avotu.

Saraksts un rediģēšanas forma rāda pēdējās atjaunošanas laiku. Katru saglabāšanu
reģistrē UTC; pārlūkā to attēlo Rīgas laikā. Dzēšana pieprasa atsevišķu apstiprinājumu
un CSRF kodu. Piedāvājumu bez groza un pasūtījumu rindām dzēš, pārējos deaktivizē.

Migrācija `0005_offer_terms` pievieno piedāvājumiem un pasūtījumu rindām `vat_rate`
un `currency`. Esošām cenām saglabā EUR; agrāk nenorādītās PVN likmes paliek tukšas,
līdz administrators tās ievada. Jaunos pasūtījumos likmi un valūtu kopē vēstures ierakstā.
Pārbaudes: `tests/test_offer_crud.py`, `tests/test_admin_panel.py`, `tests/test_layout.py`.
