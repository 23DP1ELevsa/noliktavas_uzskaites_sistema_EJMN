# Piedāvājumu salīdzināšana un grozs

Katalogā izvēlieties **Skatīt piedāvājumus**, lai atvērtu preces salīdzināšanas lapu
(`/catalog/products/<id>`). Lapa izmanto kopīgo StockFlow dizainu un rāda preces
nosaukumu, attēlu, aprakstu un aktīvos piegādātāju piedāvājumus.

Katram piedāvājumam redzama vienības cena, PVN statuss, atlikums, minimālais
daudzums, piegādes maksa un termiņš, kā arī pēdējais datu atjaunošanas laiks.
Pārlūkā laiks tiek rādīts Rīgas laika joslā; bez JavaScript — UTC.

Norādiet kopīgo daudzumu un kārtošanas veidu. Noklusētā kārtošana ir pēc kopsummas
augošā secībā. Pieejama arī dilstoša kopsumma, piegādes termiņš un piegādātāja
nosaukums. Izvēle tiek saglabāta lapas URL parametros `quantity` un `sort`.
Bez JavaScript nospiediet **Salīdzināt**; ar JavaScript izvēles maiņa iesniedz formu.

Salīdzinājuma kopsumma tiek aprēķināta ar `Decimal`:
`preču summa ar PVN + piegādes maksa`. Visām rindām izmanto vienu un to pašu
izvēlēto daudzumu; to nepalielina līdz konkrētā piegādātāja minimālajam pasūtījumam.
Ja PVN jau iekļauts vienības cenā, to atkārtoti nepieskaita. Pretējā gadījumā
PVN aprēķina kā `vienības cena × daudzums × vat_rate / 100` un noapaļo līdz
centiem ar `ROUND_HALF_UP` visai preču summai, nevis katrai vienībai atsevišķi.
Lapa atsevišķi rāda preču summu ar PVN, pieskaitīto PVN un piegādes maksu.

Piegādes maksu pieskaita vienu reizi katram piedāvājumam kā norādītu gala maksu;
modelī nav atsevišķas piegādes PVN pazīmes. Kārtošanai izmanto aprēķināto
kopsummu ar PVN un piegādi, vienādas summas kārto stabili pēc piedāvājuma ID.
Piemēram, 3 vienības par 10,00 € bez PVN, ar 21 % likmi un 4,50 € piegādi
salīdzinājumā maksā 40,80 €. Ja 10,00 € jau ietver PVN, kopsumma ir 34,50 €.

Vecam piedāvājumam bez PVN un bez `vat_rate` likmi nepieņem automātiski:
kopsummas vietā rāda **Nav aprēķināma** un paskaidro trūkstošo likmi. Šādas
rindas abos kopsummas kārtošanas virzienos atrodas beigās. Administrators var
norādīt likmi piedāvājuma rediģēšanas lapā. Neaktīvu piegādātāju piedāvājumi
netiek rādīti. Minimālā daudzuma un atlikuma neatbilstības rāda atsevišķi no
PVN aprēķina; nepieejamu piedāvājumu izmaksas joprojām var salīdzināt.

Pēc pieslēgšanās **Pievienot grozam** saglabā izvēlēto piedāvājumu un daudzumu
lietotāja datubāzes grozā. Pie katras pogas laukā **Pasūtīt** var atsevišķi izvēlēties
šī piedāvājuma daudzumu; tas nemaina kopīgo salīdzināšanas daudzumu vai kārtošanu.
Ar JavaScript blakus redzama izvēlētā pasūtījuma summa ar piegādi. Daudzuma laukā
norādīti piegādātāja minimālā daudzuma un atlikuma ierobežojumi.
Groza un pasūtījuma summas turpina izmantot piegādātāja norādītās cenas un to
PVN statusu; salīdzinājuma aprēķins nemaina saglabātās cenas vai pasūtījumu vēsturi.
Viena piedāvājuma atkārtota pievienošana palielina tā
daudzumu esošajā rindā. Serveris pārbauda aktīvu preci un piedāvājumu, pozitīvu
veselu daudzumu, minimālo pasūtījumu un atlikumu, ieskaitot grozā esošo daudzumu.
Preču pievienošana grozam nerezervē atlikumu.

**Grozs** (`/cart`) rāda aktuālās cenas un brīdina par deaktivizētiem piedāvājumiem
vai nepietiekamu atlikumu. Preces grupētas pēc piegādātāja, katrai grupai rādot
piegādes maksu un kopējo summu. Kopsavilkumā atsevišķi redzama preču summa,
piegādes maksas un kopsumma. Piegāde tiek summēta no katra piedāvājuma maksas;
nav pieņemts, ka viena piegādātāja precēm ir viena kopīga piegādes maksa.
Tajā var atjaunināt daudzumu un izņemt preces. Grozs
saglabājas pēc iziešanas un atkārtotas pieslēgšanās. Groza darbības pieprasa
pieslēgšanos un CSRF kodu; sveša lietotāja groza rindas nav pieejamas.

**Noformēt pieteikumu** atver `/orders/checkout` ar preču pārskatu, uzņēmuma datiem
un piegādes adresi no profila. Tukšs grozs vai nepieejamas preces bloķē noformēšanu.
Pirms iesniegšanas jābūt aizpildītam uzņēmuma nosaukumam, reģistrācijas numuram un
adresei. Ja pēc pārskata atvēršanas mainās cenas, daudzumi vai uzņēmuma dati,
lietotājam jāpārskata aktuālā informācija un jāiesniedz atkārtoti.

Iesniegšana izveido pieteikumu ar statusu `iesniegts`, saglabā preču nosaukumu,
piegādātāju, cenu, daudzumu, piegādi un PVN pazīmi pieteikuma rindās un iztukšo
grozu vienā datubāzes darījumā. Preces netiek rezervētas, maksājums netiek veikts.
Apstiprinājums pieejams `/orders/<id>` tikai pieteikuma īpašniekam.
Datubāzes kļūdu gadījumā darbības tiek atceltas un parādīta saprotama kļūdas lapa
ar iespēju atvērt grozu atkārtoti.

Automātiskās pārbaudes: `tests/test_comparison.py`, `tests/test_cart_checkout.py`.
