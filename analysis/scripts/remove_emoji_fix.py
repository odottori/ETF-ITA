#!/usr/bin/env python3
"""
Remove Emoji Fix - ETF Italia Project v10
Rimuove automaticamente tutti gli emoji dai script core per compatibilità Windows
"""

import os
import re
import glob

# Lista di emoji da rimuovere
EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000027BF\U0001F300-\U0001F5FF\U0001F200-\U0001F2FF\U0001F100-\U0001F1FF]'
)

def remove_emoji_from_file(file_path):
    """Rimuove emoji da un file Python"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Rimuovi emoji
        content_clean = EMOJI_PATTERN.sub('', content)
        
        # Fix per print con emoji
        content_clean = re.sub(r'print\("([^"]*?)\s*[\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000027BF\U0001F300-\U0001F5FF\U0001F200-\U0001F2FF\U0001F100-\U0001F1FF][^"]*?"\)', r'print("\1")', content_clean)
        content_clean = re.sub(r"print\('([^']*?)\s*[\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000027BF\U0001F300-\U0001F5FF\U0001F200-\U0001F2FF\U0001F100-\U0001F1FF][^']*?'\)", r"print('\1')", content_clean)
        
        # Salva il file pulito
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content_clean)
        
        return True
        
    except Exception as e:
        print(f"Errore processando {file_path}: {e}")
        return False

def main():
    """Funzione principale"""
    
    print("Remove Emoji Fix - ETF Italia Project v10")
    print("=" * 50)
    
    # Trova tutti i file Python nelle directory core e analysis
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Vai su di due livelli
    core_dir = os.path.join(base_dir, 'scripts', 'core')
    analysis_dir = os.path.join(base_dir, 'analysis', 'scripts')
    
    print(f"Base directory: {base_dir}")
    print(f"Core directory: {core_dir}")
    print(f"Analysis directory: {analysis_dir}")
    
    # Pattern per tutti i file Python
    patterns = [
        os.path.join(core_dir, '*.py'),
        os.path.join(analysis_dir, '*.py')
    ]
    
    files_processed = 0
    files_success = 0
    
    for pattern in patterns:
        print(f"Cercando: {pattern}")
        for file_path in glob.glob(pattern):
            files_processed += 1
            print(f"Processando: {os.path.basename(file_path)}")
            
            if remove_emoji_from_file(file_path):
                files_success += 1
                print(f"   Completato")
            else:
                print(f"   Errore")
    
    print(f"\nRiepilogo:")
    print(f"  File processati: {files_processed}")
    print(f"  Success: {files_success}")
    print(f"  Errori: {files_processed - files_success}")

if __name__ == "__main__":
    main()
