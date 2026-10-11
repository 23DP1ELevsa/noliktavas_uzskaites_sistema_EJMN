# Uzņēmuma profils

Pēc pieslēgšanās atver **Mans profils** (`/auth/profile`). Šeit saglabā kontaktpersonas vārdu,
uzņēmuma nosaukumu, reģistrācijas numuru, PVN numuru, kontakttālruni, uzņēmuma adresi un
atsevišķu piegādes adresi. E-pasts tiek nolasīts no pieslēgtā konta.

Ja kontam uzņēmuma profila vēl nav, pirmā veiksmīgā saglabāšana to izveido.
Nākamās saglabāšanas atjaunina to pašu profilu. Atverot lapu atkārtoti, forma rāda
datubāzē saglabātās vērtības. Katrs lietotājs var mainīt tikai savu profilu.

Vārds un uzvārds, uzņēmuma nosaukums, reģistrācijas numurs un uzņēmuma adrese ir obligāti.
PVN numuru un tālruni var atstāt tukšus vai dzēst. Tukša piegādes adrese nozīmē, ka
piegādei jāizmanto uzņēmuma adrese (`CompanyProfile.effective_delivery_address`).

Reģistrācijas numuram ir atļauti latīņu burti, cipari un atdalītāji: atstarpe, punkts,
slīpsvītra vai defise. PVN numuram ir atļauti latīņu burti, cipari, atstarpes un defises.
Tālrunim jāsatur 7–15 cipari; var izmantot sākuma `+`, atstarpes, iekavas, punktus un defises.
Šīs pārbaudes pārbauda ievades formātu, nevis uzņēmuma esamību reģistrā.

Lauku garumi atbilst datubāzei: vārdam 150, nosaukumam un adresēm 255,
reģistrācijas un PVN numuriem un tālrunim 50 rakstzīmes.
Nederīga ievade netiek saglabāta; kļūdas ir norādītas pie laukiem, un ievadītās vērtības paliek formā.
Tās pašas uzņēmuma datu pārbaudes tiek izmantotas reģistrācijas formā.

Pēc koda atjaunināšanas piemēro migrāciju, kas pievieno piegādes adreses lauku:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
```

Esošie uzņēmuma profila dati tiek saglabāti. Kamēr atsevišķa piegādes adrese nav norādīta,
piegādei izmanto esošo uzņēmuma adresi.
