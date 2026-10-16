# Motorsport Calendar — automatická synchronizace

Synchronizace závodních startů do Google Calendar v `Europe/Prague`. Spouští se přes GitHub Actions první den každého měsíce nebo manuálně (`Actions → Motorsport calendar sync → Run workflow`). Bez změn a bez chyb Discord mlčí.

## Datové zdroje

| Série | Zdroj | Chování |
| --- | --- | --- |
| F1 | [Jolpica](https://api.jolpi.ca/ergast/f1/) | Sprint kvalifikace, sprint, kvalifikace a hlavní závod; 2 hodiny od publikovaného času startu |
| WEC | [MotoDB](https://github.com/vishwapramuditha/moto-db) | Hlavní závod, 2 hodiny od publikovaného času startu |
| Formula E | [MotoDB](https://github.com/vishwapramuditha/moto-db) | Jedna celodenní událost pro každý závod, i při dvojitých závodech |
| 24h Daytona | [IMSA](https://www.imsa.com/weathertech/2027-schedule/) | Celodenní událost v sobotu víkendu Rolex 24 |
| 24h Nürburgring | [ADAC](https://www.24h-rennen.de/termine/) | Celodenní událost v sobotu víkendu 24h |

U Daytony a Nürburgringu zdroje obvykle zveřejňují vícedenní **závodní víkend**; den hlavního 24h závodu se vybírá jako sobota před nedělním koncem víkendu. Pokud se program změní, je nutné aktualizovat pravidlo. Nejde o garantovaný čas startu. Když nový ročník ještě není publikován nebo zdroj změní formát, skript závod neodhaduje.

## Nasazení jako nový GitHub projekt

1. Zálohujte původní repozitář a exportujte kalendář. **Starý repozitář nemažte, dokud nový neprojde ověřením.**
2. Nahrajte obsah tohoto adresáře do nového repozitáře (soubor `.github/workflows/sync.yml` musí být součástí).
3. V `Settings → Secrets and variables → Actions → Secrets` nastavte `GOOGLE_CALENDAR_ID`, `GOOGLE_CREDENTIALS_B64` a `DISCORD_WEBHOOK_URL`.
4. Google service account musí mít oprávnění upravovat daný kalendář. `GOOGLE_CREDENTIALS_B64` je celý JSON klíč zakódovaný přes base64; nikdy jej necommitujte.
5. Otestujte nejdříve lokálně s `DRY_RUN=true`, pak nastavte `DRY_RUN=false` pro reálný zápis. GitHub Actions má produkční režim již nastaven.
6. Teprve po úspěšném ověření vypněte původní GitHub Actions a odstraňte staré události, pokud jde o jiná ID.

### Konfigurace

Viz `.env.example`. Pět `*_ICS_URL` už **není potřeba**. `OVERRIDES_FILE` zůstává volitelný. Časy v override musí mít explicitní zónu nebo UTC offset:

```json
[
  {
    "series": "DAYTONA",
    "key": "2027:rolex-24",
    "title": "DAYTONA | Rolex 24 – závod",
    "start": "2027-01-30T13:40:00-05:00",
    "source": "https://www.imsa.com/events/2027-rolex-24-at-daytona/"
  }
]
```

**Výše uvedený čas je pouze demonstrace formátu! Není ověřeným startem pro rok 2027; nepřidávejte jej bez potvrzení pořadatele.** Výchozí `config/starts.json` je prázdné pole.

### Chování

- F1 importuje 4 požadované typy sessions; ostatní šampionáty pouze hlavní závod.
- F1 a WEC mají **2 hodiny od startu**; Formula E, Daytona a Nürburgring jsou **celodenní pouze v den závodu**.
- Google Calendar štítek `Basil` se používá přes `eventLabelId` a `eventLabelVersion=1`.
- Identita událostí je deterministická; existující spravované události se upravují namísto duplikování.
- Při žádné změně a bez chyby Discord nic neposílá. Při změnách nebo chybách odešle shrnutí.
- Automatické mazání se záměrně neprovádí, aby výpadek zdroje nezničil už zapsaný kalendář.

### Lokální spuštění

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
python -m motorsport
```

## Bezpečnost

Nekommitujte `.env`, Google JSON klíče, tokeny ani Discord webhook. Závislosti a skript používají jen HTTPS. Přístup k účtu je omezen oprávněním přiděleným service accountu. Doporučeno vytvořit samostatný kalendář pro motorsport.

### Celodenní závody (bez času startu)

- Formula E: MotoDB, jedna celodenní událost za každý závod/round (včetně dvojitých závodů).
- 24h Daytona: oficiální víkend IMSA; vyznačí sobotu před nedělním koncem víkendu.
- 24h Nürburgring: oficiální víkend ADAC; vyznačí sobotu před nedělním koncem víkendu.
- Celodenní událost používá `start.date` a `end.date` následujícího dne (Google Calendar API vyžaduje exkluzivní konec). Zobrazuje se pouze jediný den.
- Pro Daytonu/Nürburgring je **sobota pravidlem pro 24h start z víkendu**, nikoliv zveřejněným přesným časem. Pokud pořadatel změní den hlavního závodu, parser je nutné aktualizovat.
- Nové sezóny Formula E v MotoDB se objeví teprve po jejich zveřejnění v daném zdroji; nepoužívá se odhad data.
