# Administratora panelis

Vienotais pārskats pieejams `/admin` un caur saiti **Admin panelis** publiskajās
lapās. Pēc administratora pieslēgšanās tas atveras automātiski, ja nav norādīta
cita lokāla mērķa adrese. Visās pārvaldības lapās ir kopīga sadaļu navigācija.

Panelī ir piegādātāji, preces, piegādātāju preces un kategorijas. Katra pārskata
sadaļa rāda ierakstu skaitu un saites pievienošanai un saraksta atvēršanai.

## Piegādātāja preču pievienošana

1. Izveidojiet piegādātāju un norādiet piegādes maksu.
2. Piegādātāja lapā izvēlieties **Pievienot jaunu preci**. Pēc kataloga preces
   saglabāšanas atveras cenas un atlikuma forma ar jau izvēlēto piegādātāju un preci.
   Ja prece katalogā jau ir, izmantojiet **Piesaistīt esošu preci**.
3. Norādiet vienības cenu, PVN statusu, atlikumu, minimālo daudzumu un piegādes termiņu.
   Piegādātāja preces kods ir izvēles lauks. Piegādes maksa tiek ņemta no piegādātāja.

Piegādātāju preču saraksts atrodas `/admin/supplier-products`; meklēšana darbojas
pēc preces nosaukuma, kataloga SKU vai piegādātāja nosaukuma. Ierakstu var rediģēt
arī piegādātāja un kataloga preces detalizētajos skatos.

Cena pieņem komatu vai punktu un līdz divām zīmēm aiz komata. Daudzumiem un
termiņam jābūt veseliem nenegatīviem skaitļiem; minimālajam daudzumam jābūt vismaz 1.
PVN izvēle ir obligāta. Ja formā ir kļūda, ieraksts netiek saglabāts un ievade paliek.

## Izmaiņas un vēsture

Rediģējot var mainīt cenu, PVN, atlikumu, minimālo daudzumu, termiņu, kodu un
aktivitāti. Saglabājot piemēro piegādātāja aktuālo piegādes maksu. Preci un jau
piesaistītu piegādātāju esošam ierakstam mainīt nevar; citai kombinācijai izveido jaunu
ierakstu. Agrākie piedāvājumi bez piegādātāja saites rediģējot jāpiesaista piegādātājam.

Deaktivizēšana saglabā groza rindas un pasūtījumu vēsturi; publiskais katalogs un
pasūtīšana izmanto tikai aktīvas preces, piegādātājus un piedāvājumus. Jau iesniegto
pasūtījumu nosaukumi, cenas un summas netiek pārrēķinātas. Jaunie ieraksti saglabā
administratoru kā autoru un `manual` kā datu avotu.

Jaunajām iespējām nav nepieciešama papildu datubāzes migrācija. Pārbaudes:
`tests/test_admin_panel.py` un `tests/test_layout.py`.
