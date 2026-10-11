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
Detalizētajā skatā administrators redz uzņēmumu, klienta kontaktus, piegādes adresi,
piezīmi, preces pa piegādātājiem un summas.

Administratoram pieejamas pogas **Apstiprināt** un **Noraidīt**, kā arī izvēles
komentārs klientam. Lēmums, administrators, izskatīšanas laiks un paziņojumi tiek
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

Migrācija `0006_order_notifications` pievieno `orders.customer_snapshot` un
`notifications`. Esoši pieteikumi saglabā savas rindas un summas; tiem bez saglabātas
klienta datu kopijas attēlo saistītā profila datus. Pārbaudes:
`tests/test_order_workflow.py`, `tests/test_cart_checkout.py`, `tests/test_layout.py`.
