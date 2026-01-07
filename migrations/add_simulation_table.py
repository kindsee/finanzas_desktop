#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para ejecutar migración: Crear tabla simulation_variables
"""

import os
import sys
from database import db
from sqlalchemy import text

def run_migration(sql_file_path):
    """Ejecuta un archivo SQL de migración"""
    if not os.path.exists(sql_file_path):
        print(f"❌ Error: No se encuentra el archivo {sql_file_path}")
        return False
    
    db.init_app()
    
    if not db.engine:
        print("❌ Error: No se pudo conectar a la base de datos")
        print("   Verifica que DATABASE_URL esté configurado en .env")
        return False
    
    print(f"📂 Leyendo migración: {sql_file_path}")
    
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
        
        with db.engine.connect() as conn:
            for i, statement in enumerate(statements, 1):
                if statement:
                    print(f"  Ejecutando statement {i}...")
                    result = conn.execute(text(statement))
                    conn.commit()
                    
                    try:
                        rows = result.fetchall()
                        if rows:
                            for row in rows:
                                print(f"    ✓ {dict(row)}")
                    except:
                        pass
        
        print(f"✅ Migración completada exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error ejecutando migración: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("  MIGRACIÓN: Crear tabla simulation_variables")
    print("=" * 60)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_file = os.path.join(script_dir, "add_simulation_variables_table.sql")
    
    print(f"\n🔍 Buscando archivo: {sql_file}")
    
    if not os.path.exists(sql_file):
        print(f"❌ No se encuentra el archivo de migración")
        sys.exit(1)
    
    print("\n⚠️  Esta migración creará la tabla 'simulation_variables' con:")
    print("   - id (PRIMARY KEY)")
    print("   - descripcion (VARCHAR)")
    print("   - cuenta_id (FOREIGN KEY a accounts)")
    print("   - importe (DECIMAL)")
    print("   - frecuencia (VARCHAR)")
    print("   - activo (INTEGER, default 1)")
    
    respuesta = input("\n¿Continuar con la migración? (s/n): ").lower()
    
    if respuesta != 's':
        print("❌ Migración cancelada")
        sys.exit(0)
    
    print("\n🚀 Ejecutando migración...\n")
    
    success = run_migration(sql_file)
    
    if success:
        print("\n" + "=" * 60)
        print("  ✅ MIGRACIÓN COMPLETADA")
        print("=" * 60)
        print("\n💡 Ahora puedes usar la funcionalidad de simulación")
    else:
        print("\n" + "=" * 60)
        print("  ❌ MIGRACIÓN FALLIDA")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
