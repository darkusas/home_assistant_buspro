# Etapas 0 — protokolo patikra su tikra įranga

Tikslas: patvirtinti tai, ko neradome oficialiuose dokumentuose (žr. `docs/device-scan-plan.md`, 2.3 skyrių), prieš rašant skanerį. Rezultatus (žurnalus ir išvadas) dėkite į šį aplanką, pvz. `2026-10-26-rele-1.89.md` + `.jsonl`.

## Ką reikia patvirtinti

| # | Klausimas | Kaip |
|---|---|---|
| 1 | `0x000E` → `0x000F`: ar atsakymas = 20 B pavadinimas be papildomų baitų? | `remark` |
| 2 | `0xF00E [kanalas]` → `0xF00F [kanalas, 20 B]`: ar opkodai ir formatas teisingi? | `channel-remarks` |
| 3 | Kokia koduotė naudojama lietuviškoms raidėms (`cp1257`? `utf-8`? `gbk`?) | įrankis rodo visas; žiūrėti, kuri teisinga |
| 4 | `0xE548` → `0xE549`: ką praneša kiekvienas jūsų modelis (rėlė, dimeris, jutiklis, panelė, DLP, užuolaidos)? | `module` |
| 5 | Ar rėlių/dimerių moduliai atsako į *broadcast* `0x0033`? | `channels 255.255` |
| 6 | Ar šliuzo atsakymai pasiekia PC (broadcast ar unicast)? Atsakymo laikas? | `listen`, laiko žymos žurnale |

## Būdas A — zondavimo įrankis (rekomenduojama)

Reikia tik Python 3.10+ PC, esančiame tame pačiame tinkle kaip HDL IP šliuzas (Home Assistant nereikia). **Uždarykite HDL Buspro Setup Tool** — abiem reikia UDP porto 6000.

```bash
G="--gateway 192.168.1.10 --log docs/protocol-captures/probe.jsonl"
python tools/hdl_probe.py $G listen --seconds 20         # kas vyksta magistralėje
python tools/hdl_probe.py $G module --seconds 10          # visi įrenginiai, kurie save aprašo
python tools/hdl_probe.py $G remark 1.89                  # įrenginio pavadinimas
python tools/hdl_probe.py $G channels 1.89                # kanalų skaičius ir būsenos
python tools/hdl_probe.py $G channel-remarks 1.89         # kanalų pavadinimai
python tools/hdl_probe.py $G channels 255.255             # 5 klausimas
```

Šios komandos tik skaito. `raw` siunčia bet ką — ja galima ir perjungti apkrovą.

## Būdas B — Wireshark + HDL Buspro Setup Tool 2

1. Wireshark: pasirinkti tinklo plokštę, filtras `udp.port == 6000`, pradėti įrašymą.
2. Setup Tool 2: **Search** (online įrenginių paieška).
3. Atidaryti vieną rėlės modulį ir peržiūrėti kanalų pavadinimus (remark).
4. Neprivaloma, tik ant atsarginio kanalo: pakeisti pavadinimą į tekstą su `ąčęėįšųūž`, įrašyti, perskaityti, grąžinti seną.
5. Sustabdyti, išsaugoti `.pcapng`, dekoduoti:

```bash
tshark -r capture.pcapng -Y "udp.port==6000" -T fields -e udp.payload | python tools/hdl_probe.py decode -
```

Taip matysime, ką siunčia pats HDL įrankis (ypač paieškos ir pavadinimų skaitymo opkodus).

## Ką pateikti

- `.jsonl` žurnalą ir/arba `decode` išvestį;
- kokie modeliai yra (iš lipdukų arba Setup Tool), ir kaip jie vadinasi Setup Tool'e — kad galėtume palyginti su nuskaitytais pavadinimais;
- atsakymus į 1–6 klausimus.

Žurnaluose bus vietinio tinklo IP ir įrenginių pavadinimai — jei tai nepageidautina viešame repo, juos galima pateikti tiesiai sesijoje.
