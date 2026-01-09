# HOTFIX_07 addendum

## ingest_data.py: ingest chirurgico per simbolo

Esempi:

- Un solo giorno, un solo simbolo:
  py scripts\data\ingest_data.py --start-date 2022-02-23 --end-date 2022-02-23 --symbol CSSPX.MI

- Più simboli:
  py scripts\data\ingest_data.py --start-date 2022-02-23 --end-date 2022-02-23 --symbols CSSPX.MI,EIMI.MI

Nota: `--symbols` è un alias comodo di `--symbol`.

## operability_gate.py: alias CLI + import robusto

Esempio (dry-run):
  py scripts\quality\operability_gate.py --venue BIT --start-date 2022-02-23 --end-date 2022-02-23

Esempio (apply):
  py scripts\quality\operability_gate.py --venue BIT --start-date 2022-02-23 --end-date 2022-02-23 --apply

Soglie configurabili:
  --warn-threshold 0.8
  --alert-threshold 0.5
