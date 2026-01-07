"""
Console Utils - ETF Italia Project v10.8
Utility per gestione robusta console Windows (UTF-8 encoding)
"""

import sys
import io


def setup_windows_console():
    """
    Configura console Windows per UTF-8 encoding
    
    Risolve problemi di UnicodeEncodeError su Windows console (cp1252)
    quando si stampano caratteri Unicode (emoji, simboli speciali).
    
    Approccio multi-layer:
    1. Tenta reconfigure() se disponibile (Python 3.7+)
    2. Fallback con TextIOWrapper se reconfigure fallisce
    3. Gestisce gracefully errori (non blocca esecuzione)
    """
    
    # Layer 1: Reconfigure (Python 3.7+)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            return True
        except Exception:
            pass  # Fallback to layer 2
    
    # Layer 2: TextIOWrapper fallback
    try:
        # Solo se encoding non è già UTF-8
        if getattr(sys.stdout, "encoding", None) and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding="utf-8", 
                errors="replace", 
                line_buffering=True
            )
        
        if getattr(sys.stderr, "encoding", None) and sys.stderr.encoding.lower() != "utf-8":
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, 
                encoding="utf-8", 
                errors="replace", 
                line_buffering=True
            )
        
        return True
        
    except Exception:
        # Se tutto fallisce, continua senza UTF-8
        # (meglio funzionare con encoding limitato che crashare)
        return False


def safe_print(text, **kwargs):
    """
    Print sicuro che gestisce errori di encoding
    
    Args:
        text: Testo da stampare
        **kwargs: Argomenti aggiuntivi per print()
    
    Returns:
        bool: True se print riuscito, False altrimenti
    """
    try:
        print(text, **kwargs)
        return True
    except UnicodeEncodeError:
        # Fallback: rimuovi caratteri non-ASCII
        safe_text = text.encode('ascii', errors='replace').decode('ascii')
        print(safe_text, **kwargs)
        return False


if __name__ == '__main__':
    # Test console setup
    print("🔧 CONSOLE UTILS TEST")
    print("=" * 60)
    
    # Test encoding attuale
    print(f"Current stdout encoding: {sys.stdout.encoding}")
    print(f"Current stderr encoding: {sys.stderr.encoding}")
    
    # Setup Windows console
    success = setup_windows_console()
    
    if success:
        print("\n✅ Console setup completato")
        print(f"New stdout encoding: {sys.stdout.encoding}")
        print(f"New stderr encoding: {sys.stderr.encoding}")
    else:
        print("\n⚠️  Console setup fallito (usando encoding default)")
    
    # Test caratteri Unicode
    print("\n📊 Test caratteri Unicode:")
    safe_print("✅ Check mark")
    safe_print("❌ Cross mark")
    safe_print("📁 Folder")
    safe_print("🚀 Rocket")
    safe_print("💰 Money bag")
    
    print("\n✅ Test completato")
