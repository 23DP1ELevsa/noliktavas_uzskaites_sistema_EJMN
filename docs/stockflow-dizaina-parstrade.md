**StockFlow saskarnes aktuālie labojumi — 26.10.2026.**

Sākumlapa atjaunota pēc lietotāja pievienotā attēla: kreisajā pusē ir virsraksts, apraksts un kataloga darbība; labajā pusē — “Viss, kas vajadzīgs izvēlei” kartīte ar trim darbībām. Zem tās ir trīs priekšrocību bloki. Saglabāta mobilā pārkārtošana un esošā StockFlow krāsu palete. Iepriekšējais četru soļu izkārtojums vairs netiek izmantots.

Pieteikuma noformēšanas blokam “Pārbaudiet kopsummu / Pieteikuma kopsavilkums” noņemta piesaiste ritināšanai. Tas paliek savā vietā dokumentā un neseko lapas ritināšanai. Pārējo lapu kopsavilkumu uzvedība nav mainīta.

Paziņojumu automātisko aizvēršanu iepriekš apturēja kursora vai tastatūras fokusa atrašanās uz paziņojuma. Šī apturēšana noņemta: katrs parādītais paziņojums aizveras pēc 5–10 sekundēm atkarībā no teksta garuma arī tad, ja uz tā ir kursors vai fokuss. Vairāki paziņojumi parādās secīgi; katram ir savs taimeris un saglabāta manuālās aizvēršanas poga. Iekšējās ritjoslas netiek izmantotas.

Izmaiņas veiktas `templates/index.html`, `templates/checkout.html`, `static/css/storefront.css`, `static/css/account.css` un `static/js/ui.js`. Aktualizētas pārbaudes `tests/test_layout.py` un `scripts/ui_qa.py`.

Saglabāti iepriekšējie labojumi: reģistrācijas poga visā formas platumā, paroles maiņa abām lomām, salīdzinājuma poga “Attīrīt filtrus”, administratora horizontālā navigācija un CSV/JSON failu imports.

**Pārbaudes**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -o cache_dir=instance/pytest-cache
.\.venv\Scripts\python.exe scripts/ui_qa.py --browser-no-sandbox --interactions --screenshots representative --pages profile empty-profile --output instance/ui-qa-profile-pagination
```

- Pilnais pytest komplekts: **606 testi izturēti, viens izlaists**, 141,06 sekundes.
- Pārlūka audits: **602 pārbaudes 43 lapu/lomu scenārijiem**, bez konstatētām pārpildes, kontrasta, etiķešu vai JavaScript kļūdām.
- Stresa audits: **602 pārbaudes**, bez konstatētām kļūdām.
- Darbību pārbaudes: **85 no 85 izturētas**. Papildus pārbaudīts, ka noformēšanas kopsavilkums ritinot saglabā vietu dokumentā un divi secīgi paziņojumi automātiski aizveras arī ar kursoru un tastatūras fokusu uz tiem.
- Pārbaudīti 320, 375, 425, 768, 1024, 1440 un 1920 px platumi, arī 200% mēroga ekvivalents.
- Veikta faktisko datoru un mobilo ekrānattēlu vizuāla apskate; `git diff --check` izturēta.

| Skats | Ekrānattēls |
| --- | --- |
| Sākumlapa datorā | [Atvērt](../instance/ui-qa-restored-home/screenshots/guest-home-1440-z1.png) |
| Sākumlapa mobilajā | [Atvērt](../instance/ui-qa-restored-home/screenshots/guest-home-375-z1.png) |
| Noformēšanas kopsavilkums | [Atvērt](../instance/ui-qa-restored-home/screenshots/user-checkout-1440-z1.png) |
| Apakšējais paziņojums | [Atvērt](../instance/ui-qa-restored-home/screenshots/submission-toast.png) |

Pilnie rezultāti: [pārlūka audits un darbības](../instance/ui-qa-restored-home/report.json), [stresa audits](../instance/ui-qa-restored-home-stress/report.json). Ekrānattēli un pārskati atrodas lokālajā, Git ignorētajā `instance/` mapē.

Izlaistais tests prasa MySQL rindu bloķēšanu un atsevišķus savienojumus; šeit izmantota izolēta SQLite datubāze. Pārlūka pārbaudes veiktas instalētajā Chromium. Šīs Windows vides ierobežojumu dēļ lokālajam testa pārlūkam izmantota `--browser-no-sandbox` opcija.
