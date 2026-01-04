#!/usr/bin/env python3
"""
Analisi Fonti Dati Alternative - ETF Italia Project v10
Verifica disponibilità dati per record respinti da Yahoo Finance
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import requests

def analyze_rejected_data():
    """Analizza dati respinti e alternative"""
    
    print("🔍 Analisi dati XS2L.MI e fonti alternative")
    print("=" * 50)
    
    # Analisi XS2L.MI
    ticker = yf.Ticker('XS2L.MI')
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    print(f"📊 Analisi XS2L.MI: {start_date} → {end_date}")
    
    try:
        hist = ticker.history(start=start_date, end=end_date)
        
        if not hist.empty:
            # Calcola variazioni giornaliere
            hist['daily_change'] = hist['Close'].pct_change()
            
            # Trova spike >15%
            spikes = hist[hist['daily_change'].abs() > 0.15]
            
            print(f"📈 Totali: {len(hist)} giorni")
            print(f"⚠️ Spike >15%: {len(spikes)} giorni")
            
            if not spikes.empty:
                print("\n📅 Date con spike:")
                for date, row in spikes.iterrows():
                    change_pct = row['daily_change'] * 100
                    print(f"  {date.date()}: {row['Close']:.2f} ({change_pct:+.1f}%)")
                    print(f"    Volume: {row['Volume']:,}")
        
    except Exception as e:
        print(f"❌ Errore analisi XS2L.MI: {e}")
    
    # Fonti dati alternative
    print("\n🔄 FONTI DATI ALTERNATIVE GRATUITE:")
    print("=" * 50)
    
    alternatives = {
        "Stooq.com": {
            "gratis": True,
            "storico": "Limitato (~2 anni)",
            "coverage": "Europe/US",
            "quality": "Media",
            "note": "API semplice, affidabile per ETF europei"
        },
        "Alpha Vantage": {
            "gratis": True,
            "storico": "Completo",
            "coverage": "Global",
            "quality": "Alta",
            "note": "500 calls/giorno free, richiede API key"
        },
        "Polygon.io": {
            "gratis": True,
            "storico": "Limitato",
            "coverage": "US/Europe",
            "quality": "Alta",
            "note": "Micro dati free, end-of-day a pagamento"
        },
        "Quandl/EODHD": {
            "gratis": "Limitato",
            "storico": "Completo",
            "coverage": "Global",
            "quality": "Alta",
            "note": "20 calls/giorno free, dati adjusted"
        },
        "MarketStack": {
            "gratis": "Limitato",
            "storico": "Completo",
            "coverage": "Global",
            "quality": "Media",
            "note": "1000 calls/mese free"
        },
        "IEX Cloud": {
            "gratis": "Limitato",
            "storico": "Limitato",
            "coverage": "US",
            "quality": "Alta",
            "note": "50k calls/mese free, ETF europei limitati"
        }
    }
    
    for source, info in alternatives.items():
        status = "✅" if info["gratis"] == True else "🔶" if info["gratis"] == "Limitato" else "❌"
        print(f"\n{status} {source}")
        print(f"   Storico: {info['storico']}")
        print(f"   Coverage: {info['coverage']}")
        print(f"   Qualità: {info['quality']}")
        print(f"   Note: {info['note']}")
    
    # Raccomandazione per XS2L.MI
    print("\n💡 RACCOMANDAZIONE PER XS2L.MI:")
    print("=" * 50)
    print("1️⃣ **Stooq.com** - Migliore per ETF europei:")
    print("   • API gratuita senza registrazione")
    print("   • Buona qualità per ETF Milano/Xetra")
    print("   • Storico sufficiente per backtest")
    
    print("\n2️⃣ **Alpha Vantage** - Backup strategico:")
    print("   • Qualità dati elevata")
    print("   • Coverage globale completo")
    print("   • Limitazione 500 calls/giorno")
    
    print("\n3️⃣ **Yahoo Finance + Stooq** - Hybrid approach:")
    print("   • Primario: Yahoo Finance (veloce, completo)")
    print("   • Fallback: Stooq per record respinti")
    print("   • Merge intelligente dei dati")
    
    # Test Stooq
    print("\n🧪 TEST STOOQ PER XS2L.MI:")
    print("=" * 50)
    
    try:
        # Stooq URL format
        stooq_url = "https://stooq.com/q/l/?s=xs2l.mi&i=d"
        response = requests.get(stooq_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Stooq.com raggiungibile per XS2L.MI")
            print("📊 Dati disponibili per integrazione")
        else:
            print(f"⚠️ Stooq response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Errore test Stooq: {e}")
    
    print("\n🎯 PROSSIMA AZIONE CONSIGLIATA:")
    print("Implementare fallback provider in ingest_data.py:")
    print("1. Primario: Yahoo Finance")
    print("2. Fallback: Stooq per record respinti")
    print("3. Merge: Unione intelligente dei dati")

if __name__ == "__main__":
    analyze_rejected_data()
