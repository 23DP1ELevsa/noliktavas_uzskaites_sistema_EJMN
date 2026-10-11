# Pieteikumi un profila paziņojumi

Klients no groza pāriet uz `/orders/checkout`. Uzņēmuma rekvizīti un kontaktpersona
tiek aizpildīti no profila. Piegādes adresi un tālruni var labot šim pieteikumam;
šīs izmaiņas nepārraksta profilu. Pieejama izvēles piezīme administratoram līdz
1000 rakstzīmēm. Lapa rāda preces pa piegādātājiem, piegādes maksas un kopsummu.

Pirms iesniegšanas atkārtoti pārbauda profilu, pieejamību, cenas, daudzumus un
pārskatīšanas kodu. Ja groza vai profila dati mainījušies, klients pārskata pieteikumu
vēlreiz. Nederīga adrese, tālrunis vai piezīme tiek atzīmēta formā, saglabājot ievadi.

Iesniegšana vienā datubāzes transakcijā saglabā pieteikumu, preču cenu un klienta
datu kopiju, iztukšo grozu un izveido paziņojumus klientam un visiem aktīvajiem
administratoriem. Klients redz pieteikuma numuru, statusu un iesniegtos datus.
Profila izmaiņas vēlāk nepārraksta jauno pieteikumu kontaktinformāciju.

## Administratora izskatīšana

Admin paneļa sadaļa **Pieteikumi** (`/admin/orders`) pēc noklusējuma rāda iesniegtos
pieteikumus. Pieejamas arī apstiprināto, noraidīto un visu pieteikumu atlases.
Sarakstā redzams numurs, uzņēmums, kontaktpersona, datums, saglabātā summa un statuss.
Ierakstus var kārtot pēc iesniegšanas datuma abos virzienos; vienā lapā ir līdz
12 pieteikumiem. Lapošana saglabā statusa un datuma atlasi. Pieejams atlasīto
ierakstu skaits un tukšai statusa atlasei — pāreja uz visiem pieteikumiem.
Nederīgs statuss, kārtošana vai lapas numurs atgriež 400.
Detalizētajā skatā administrators redz uzņēmumu, klienta kontaktus, piegādes adresi,
piezīmi, preces pa piegādātājiem un summas.

Administratoram pieejamas pogas **Apstiprināt** un **Noraidīt**. Apstiprinot,
komentārs klientam ir izvēles; noraidot, tajā pašā laukā obligāti jānorāda iemesls.
Klienta un administratora skatā noraidīta pieteikuma komentārs tiek attēlots kā
**Noraidīšanas iemesls**. Veciem noraidītiem pieteikumiem bez komentāra parāda,
ka iemesls nav norādīts. Lēmums, administrators, izskatīšanas laiks un paziņojumi tiek
saglabāti vienā transakcijā. Pieteikuma rindas un summas netiek mainītas. Rindas
bloķēšana un statusa pārbaude nepieļauj atkārtotu vai pretēju lēmumu pēc izskatīšanas.
Pieteikums pats par sevi neveic maksājumu vai krājumu rezervāciju.

## Profils

Profila sadaļā **Paziņojumi** redzami līdz 20 jaunākajiem paziņojumiem, nelasītos
rādot pirmos. Klients saņem apstiprinājumu par iesniegšanu un administratora lēmumu;
aktīvie administratori saņem jaunus pieteikumus un paziņojumus par izskatīšanu.
Paziņojumi satur saiti uz pieteikumu un tos var atzīmēt kā lasītus.

Klienta profilā redzami pieci pēdējie pieteikumi ar statusu un summu. Pilns saraksts
pieejams `/orders`. Klients var apskatīt tikai savus pieteikumus un mainīt tikai savu
paziņojumu lasīšanas statusu. Pieteikumu lēmumus pieņem tikai administrators.
Lēmumiem un paziņojumu izmaiņām nepieciešams CSRF kods.

## Vēstures atlase un navigācija

`/orders` pieņem `status` (`all`, `iesniegts`, `apstiprināts`, `noraidīts`),
`sort` (`date-desc`, `date-asc`) un pozitīvu `page`. Pēc noklusējuma rāda jaunākos
pieteikumus visos statusos. Vienā lapā ir līdz 12 ierakstiem. Atlase, skaits un
lapošana vienmēr attiecas tikai uz pieslēgto lietotāju; norādīts cita lietotāja ID
atlasi nemaina. Pieeja sveša pieteikuma detalizētajam skatam atgriež 404.

Detalizētais skats rāda iesniegšanas laiku, saglabātās cenas un piegādātājus,
administratora komentāru un lēmuma datumu. Laikus attēlo Rīgas laika zonā.
Tukšai statusa atlasei ir saite atpakaļ uz visiem pieteikumiem.

Publiskajās, profila un admin paneļa lapās izmanto kopīgu galveni ar saitēm uz
katalogu, grozu, pieteikumiem un profilu. Aktīvā sadaļa tiek izcelta, bet pie profila
rāda nelasīto paziņojumu skaitu. Profilā paziņojumi un pēdējie pieteikumi atrodas
līdzās datu formai; šaurā ekrānā sadaļas sakārtojas vienā kolonnā.

Vēstures servera pārbaudes: `tests/test_order_history.py`.

Migrācija `0006_order_notifications` pievieno `orders.customer_snapshot` un
`notifications`. Esoši pieteikumi saglabā savas rindas un summas; tiem bez saglabātas
klienta datu kopijas attēlo saistītā profila datus. Pārbaudes:
`tests/test_order_workflow.py`, `tests/test_cart_checkout.py`, `tests/test_layout.py`.
Administratora saraksta un piekļuves pārbaudes: `tests/test_admin_orders.py`.
