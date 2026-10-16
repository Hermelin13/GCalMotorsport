# Motorsport Calendar Sync (nový projekt)

Každý měsíc synchronizuje starty motorsportu do Google Calendar a posílá Discord zprávu **pouze při změně nebo chybě**. Funguje bez lokální databáze. Nedokáže automaticky odebrat zrušené závody; to je záměrná ochrana před chybně prázdnými zdroji.

**Stav projektu:** hotová synchronizační infrastruktura, ověřené Google `eventLabelId` a filtrování závodů. **Zdrojové ICS adresy je nutné doplnit a otestovat** pro všech pět sérií. Tento balíček proto není bez konfigurace plně automatický sběrač oficiálních webů. Žádné neověřené ICS adresy nejsou v projektu vydávány za funkční. Nejbezpečnější je použít ověřené aktuální ICS se skutečnými časy startů; pro zvláštní závody jde přidat přesný start přes `config/starts.json`.

## Instalace zcela od nuly

1. Vytvoř nový prázdný GitHub repozitář nebo vymaž původní **zdrojové soubory** a nakopíruj sem obsah tohoto ZIPu. Zálohuj si původní GitHub repo a Google kalendář; samotný ZIP neodstraňuje žádné původní události.
2. Povol Google Calendar API v Google Cloud, vytvoř service account, stáhni jeho JSON a sdílej s jeho `client_email` cílový Google kalendář s oprávněním upravovat události. Service account nemusí mít přístup k primárnímu kalendáři bez sdílení.
3. Přidej GitHub **Secrets** `GOOGLE_CALENDAR_ID`, `GOOGLE_CREDENTIALS_B64`, `DISCORD_WEBHOOK_URL`. `GOOGLE_CREDENTIALS_B64` je Base64 obsahu celého JSON; například `base64 -w 0 credentials.json` na Linuxu. Nikdy necommituj credentials.
4. Přidej GitHub **Variables** `F1_ICS_URL`, `FORMULA_E_ICS_URL`, `WEC_ICS_URL`, `NURBURGRING_ICS_URL`, `DAYTONA_ICS_URL`. Jsou to ověřené HTTPS ICS feedy s jednotlivými závody a skutečnými časovými značkami. Při chybě chybějícího feedu dostaneš Discord alert a job skončí chybou, ostatní feedy se ale zpracují.
5. Nahraj projekt na GitHub, v Actions otevři **Motorsport calendar sync → Run workflow**. Po nastavení GitHub Actions běží automaticky každého 1. v měsíci v 07:17 UTC. Změnu tohoto času udělej v `.github/workflows/sync.yml`.
6. Lokálně spusť `python -m venv .venv`, aktivuj prostředí, `pip install -r requirements.txt`, kopíruj `.env.example` do `.env`, vyplň hodnoty a spusť `python -m pytest -q` a `python -m motorsport`. Dokud je `DRY_RUN=true`, změny se neprovedou, ale stav se porovná a Discord může dostat ukázku; nastav `DRY_RUN=false` až po kontrole.

## Pravidla

- F1: pouze sprint kvalifikace, sprint, kvalifikace a závod, všechny události 2 hodiny.
- Formula E: pouze hlavní závody, včetně dvoudenních podniků.
- WEC: pouze závody, žádný prolog či kvalifikace.
- Nürburgring 24h a Daytona 24h: pouze hlavní závod, zobrazit první 2 h od startu.
- Datum bez **ověřeného času** (`DTSTART;VALUE=DATE`) se nezapíše. Důvod: víkendové datum oficiálního programu není přesný start.
- Používá `eventLabelId` s `eventLabelVersion=1`. Štítek Basil `#0B8043` se vytvoří, pokud neexistuje. Existující vlastní štítky v kalendáři se zachovají.
- Používá svůj vlastní ID události (`motorsport-v2`). Staré události starého projektu **nepřepisuje a nemaže**. Chceš-li je odstranit, proveď to zvlášť po záloze nebo použij nový prázdný kalendář.
- Discord nevypisuje úspěšné běhy bez změn.
- GitHub Action s `DRY_RUN=false` provádí změny okamžitě; před spuštěním zkontroluj kalendář, do kterého service account zapisuje.

## Ruční doplnění potvrzených startů

V `config/starts.json` můžeš zadat pole objektů podle `config/starts.example.json`, ale **ukázkový čas je fiktivní; NEKOPÍRUJ ho bez ověření**. Datum musí obsahovat časové pásmo, například `+02:00`. Pro změny termínu nech `key` stejný (např. `nurburgring-2027`). Nevkládej shodnou událost zároveň do ICS a overrides; měla by dva rozdílné identifikátory.

## Oficiální zdroje pro kontrolu

- F1: https://www.formula1.com/en/racing/2027 (časové rozpisy jednotlivých Grand Prix až po jejich potvrzení)
- Formula E: https://www.fiaformulae.com/en/calendar
- WEC: https://www.fiawec.com/en/ (odkaz na jednotlivé race schedule)
- Nürburgring: https://www.24h-rennen.de/termine/
- Daytona: https://www.imsa.com/events/2027-rolex-24-at-daytona/

Zdroje uvádějí někdy **jen datum víkendu, nikoliv čas hlavního závodu**. Použitý ICS feed může být komunitní, proto je nutné ověřit jeho původ a pravidelnou údržbu. Externí ICS zdroje nikdy nepředstavujeme jako oficiální, pokud jimi nejsou.

## Omezení

- GitHub scheduled actions mohou být opožděny nebo při dlouhé neaktivitě repozitáře pozastaveny.
- Pokud feed při každém obnovení mění název závodu, může vzniknout duplicitní událost: stabilita je odvozena od textového klíče (v overrides od pevného `key`).
- Při velkých změnách názvů je vhodné použít přesně řízené `key`.
- Přesun přes hranici kalendářního roku mimo synchronizované období vyžaduje ruční kontrolu.
- Pro plnou bezobslužnou integraci **oficiálních webů** by byly potřeba jednotlivé parsery a testy jejich aktuální struktury, které nejsou v této verzi implementované.
