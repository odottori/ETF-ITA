#!/usr/bin/env python3
"""
Fix Paths - ETF Italia Project v10
Corregge automaticamente i paths in tutti gli script core
"""

import os
import re
import glob

def fix_paths_in_file(file_path):
    """Corregge i paths in un file Python"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Correggi paths che puntano a scripts/data o scripts/config
        patterns_to_fix = [
            # Fix database paths
            (r"os\.path\.join\(os\.path\.dirname\(os\.path\.dirname\(__file__\)\), 'data'", 
             r"os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data'"),
            
            # Fix config paths  
            (r"os\.path\.join\(os\.path\.dirname\(os\.path\.dirname\(__file__\)\), 'config'",
             r"os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config'"),
            
            # Fix reports paths
            (r"os\.path\.join\(os\.path\.dirname\(os\.path\.dirname\(__file__\)\), 'data', 'reports'",
             r"os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'reports'"),
        ]
        
        changes_made = 0
        for pattern, replacement in patterns_to_fix:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                changes_made += 1
        
        # Salva solo se ci sono state modifiche
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes_made
        else:
            return False, 0
            
    except Exception as e:
        print(f"Errore processando {file_path}: {e}")
        return False, 0

def main():
    """Funzione principale"""
    
    print("Fix Paths - ETF Italia Project v10")
    print("=" * 40)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    core_dir = os.path.join(base_dir, 'scripts', 'core')
    
    print(f"Core directory: {core_dir}")
    
    files_processed = 0
    files_changed = 0
    total_changes = 0
    
    for file_path in glob.glob(os.path.join(core_dir, '*.py')):
        files_processed += 1
        filename = os.path.basename(file_path)
        
        changed, changes = fix_paths_in_file(file_path)
        
        if changed:
            files_changed += 1
            total_changes += changes
            print(f"  {filename}: {changes} modifiche")
        else:
            print(f"  {filename}: nessuna modifica")
    
    print(f"\nRiepilogo:")
    print(f"  File processati: {files_processed}")
    print(f"  File modificati: {files_changed}")
    print(f"  Modifiche totali: {total_changes}")

if __name__ == "__main__":
    main()
