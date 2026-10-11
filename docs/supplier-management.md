# Piegādātāju pārvaldība

Administratoram sadaļā **Piegādātāji** (`/admin/suppliers`) pieejams saraksts,
meklēšana pēc nosaukuma, kontaktpersonas vai e-pasta un filtrēšana pēc statusa.
Detalizētajā skatā redzami kontakti, tīmekļa vietne, piegādes maksa, piedāvājumi
un saistīto pasūtījumu skaits.

Pievienošanas un rediģēšanas formā nosaukums un piegādes maksa ir obligāti.
Kontaktpersona, e-pasts, tālrunis un tīmekļa vietne ir izvēles lauki.
Nosaukumi ir unikāli, ignorējot burtu reģistru un liekas atstarpes.
Maksa jānorāda no 0 līdz 99999999.99 EUR, ar ne vairāk kā divām zīmēm aiz komata;
pieņem gan komatu, gan punktu. Negatīvas summas, nederīgi kontakti un nedrošas
tīmekļa saites netiek saglabātas. Kļūdas parādās pie laukiem, saglabājot ievadi.

Piegādātāja nosaukuma maiņa atjaunina tā saistītos piedāvājumus. Mainot piegādes
maksu, jauno maksu piemēro visiem tā piedāvājumiem. Pasūtījumu vēsturiskie
nosaukumi un summas paliek nemainīgi. Deaktivizēšana paslēpj piegādātāja
piedāvājumus publiskajā katalogā un bloķē to pievienošanu grozam/noformēšanu.
Aktivizēšana nemaina atsevišķu piedāvājumu aktivitātes statusu.

Dzēšana pieejama tikai piegādātājam bez saistītiem piedāvājumiem un pasūtījumiem,
pēc apstiprinājuma. Pasūtījuma rinda saglabā atsevišķu piegādātāja saiti arī tad,
ja piedāvājums vēlāk tiek izdzēsts. Ārējās atslēgas nepieļauj saistīta piegādātāja
dzēšanu. Visas pārvaldības darbības pieprasa administratora lomu; izmaiņas arī CSRF kodu.

## Migrācija

`0004_suppliers` izveido tabulu `suppliers` un saites `offers.supplier_id` un
`order_items.supplier_id`. Esošie piegādātāju nosaukumi tiek apvienoti, ignorējot
burtu reģistru un liekas atstarpes. Piedāvājumu un pasūtījumu summas netiek mainītas.
Ja viena piegādātāja piedāvājumiem ir dažādas piegādes maksas, piegādātāja formā
sākotnēji izmanto pirmā piedāvājuma maksu; piedāvājumu esošās maksas saglabājas
līdz administratora veiktai maksas maiņai. Tikai vēsturē atrodamie piegādātāji tiek
izveidoti neaktīvi. Nullable saites saglabā savietojamību ar agrākajiem datu importiem.

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
```

Pārbaudes: `tests/test_suppliers.py` un migrāciju pārbaudes `tests/test_models.py`.
