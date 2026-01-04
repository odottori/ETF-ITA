### 0.5 Cosa può e cosa non può fare
Ecco cosa il tuo sistema può gestire perfettamente ("tutte le altre modalità"):
1. Swing Trading (Orizzonte: Giorni/Settimane)
Logica: Cerchi di catturare un movimento di breve durata (es. un rimbalzo tecnico, una rottura di resistenza).
Fattibilità: Totale. Il tuo sistema scarica i dati la sera, calcola i segnali e ti dice "Domani mattina compra in apertura".
Vantaggio: Hai il tempo (la notte) per analizzare il segnale senza stress, controllare il grafico e decidere.
Nota: Qui il costo commissionale e lo slippage pesano di più. Il tuo modulo di reporting sarà fondamentale per capire se ne vale la pena.
2. Trend Following (Orizzonte: Settimane/Mesi)
Logica: "Il trend è tuo amico". Usi medie mobili (es. SMA 200) o breakout dei massimi a 20 giorni. Stai dentro finché il trend regge.
Fattibilità: È lo scenario ideale per questo progetto.
Vantaggio: Meno operazioni, meno stress, meno commissioni. Il Risk Management (guardrails) qui lavora benissimo per proteggerti dai crolli prolungati.
3. Rotazione Settoriale / Momentum (Orizzonte: Mensile)
Logica: Ogni fine mese guardi il tuo universo ETF (Tecnologia, Energy, Gold, Bond) e compri solo i 2 o 3 più forti (Momentum relativo).
Fattibilità: Molto alta. I calcoli di Ranking si fanno facilmente in SQL/Pandas sui dati storici.
Vantaggio: È una strategia classica che storicamente funziona bene e richiede poco tempo (ribilanciamento periodico).
4. Mean Reversion "Lenta" (Orizzonte: Giorni)
Logica: "È sceso troppo, deve risalire". Compri quando l'RSI è a terra o il prezzo tocca la banda di Bollinger inferiore.
Fattibilità: Sì, ma con un vincolo: operando EOD (End Of Day), entri il giorno dopo il segnale. A volte ti perdi il rimbalzo immediato, ma eviti anche di "afferrare il coltello mentre cade".
Il vero limite (e perché è un bene)
La tua architettura ti impone un vincolo operativo salutare: l'Esecuzione Differita (T+1 Open o T+0 Close).
Non puoi reagire alla notizia uscita alle 14:30.
Non puoi vendere per panico alle 11:00 perché il mercato fa -2%.
Questo vincolo tecnico diventa un vantaggio psicologico. Ti costringe alla disciplina. Il sistema "pensa" a bocce ferme, la sera, a mercati chiusi. Tu esegui la mattina dopo. Questo filtro elimina il 90% degli errori emotivi che distruggono i portafogli retail.
Conclusione:
Sì, il progetto supporta tutto ciò che non è "tempo reale". È una macchina da guerra per gestire il patrimonio seriamente, spaziando dall'investimento pigro (Buy & Hold) allo speculativo ragionato (Swing), mantenendo sempre il controllo del rischio e della fiscalità.

---