# Performance Reporting — Convenzione e metodologia

Questo file **non** è un report di una singola run.

## Sorgente unica dei report runtime
I report di performance *run-specific* vengono salvati nella **sessione corrente**:

- `data/reports/current_session.json` (puntatore alla sessione corrente)
- `data/reports/sessions/<session_id>/08_performance/` (report markdown e artefatti runtime)

Motivazione: evitare duplicazioni e ambiguità tra `docs/` e `data/`.

## Metodologia (principi)
- Equity curve: `cash + market_value`
- Segnali: su `adj_close`
- Valorizzazione: su `close` (con fallback `last close <= date`)
- Periodo KPI: coerente con il periodo simulato
- Benchmark: allineato sulle stesse date

## Riproducibilità
```powershell
py scripts\\data\\compute_signals.py --preset full
py scripts\\backtest\\backtest_runner.py --preset recent --recent-days 365
py scripts\\quality\\run_tests.py
```

## Next steps
- Aggiungere diagnostica execution-rate e sizing (root cause di bassa attività).
