# Preču pārvaldība

Administratora sadaļa atrodas `/admin/products` un ir pieejama ar **Preces** saiti
sākumlapā, katalogā, profilā un kategoriju sadaļā.

- Preču sarakstā var meklēt pēc nosaukuma vai SKU un atlasīt aktīvās/neaktīvās preces.
- Formā obligāti jānorāda nosaukums, unikāls SKU, esoša kategorija un mērvienība.
  SKU tiek saglabāts ar lielajiem burtiem; dublikāti tiek pārbaudīti arī neatkarīgi no burtu reģistra.
- Var norādīt aprakstu, zīmolu, modeli un izvēles attēla saiti (HTTP/HTTPS).
- Aktīvas preces ir redzamas publiskajā katalogā, arī ja tām vēl nav piedāvājumu.
- Dzēšanas saite vispirms atver apstiprinājuma lapu. Prece bez piedāvājumiem tiek dzēsta.
  Prece ar piedāvājumiem tiek deaktivizēta, saglabājot piedāvājumus, grozus un pasūtījumus.
  Rediģēšanas formā to var atkal aktivizēt.
- Publiskās preces informācija un aktīvie piegādātāju piedāvājumi ir pieejami
  `/catalog/products/<id>`. Neaktīvas preces šeit nav pieejamas.

Pirms atjauninātās lietotnes palaišanas piemēro jauno migrāciju:

```powershell
.\.venv\Scripts\python.exe -m flask --app run db upgrade
```

Migrācija `0002_product_image` pievieno izvēles lauku `products.image_url`,
saglabājot esošās preces.
