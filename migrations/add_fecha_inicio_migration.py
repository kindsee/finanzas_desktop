"""
Script de migración para agregar el campo fecha_inicio a simulation_variables

Ejecutar: python migrations/add_fecha_inicio_migration.py
"""

import os
import sys
from datetime import date

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from database import db
from sqlalchemy import text

def run_migration():
    """Ejecutar la migración para agregar fecha_inicio"""
    print("Iniciando migración: agregar campo fecha_inicio a simulation_variables...")
    
    db.init_app()
    session = db.session()
    
    try:
        # Verificar si la columna ya existe
        result = session.execute(text("""
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'simulation_variables' 
            AND COLUMN_NAME = 'fecha_inicio'
        """))
        
        count = result.fetchone()[0]
        
        if count > 0:
            print("✓ El campo 'fecha_inicio' ya existe en la tabla 'simulation_variables'")
            return
        
        # Agregar la columna
        print("Agregando columna fecha_inicio...")
        session.execute(text("""
            ALTER TABLE simulation_variables 
            ADD COLUMN fecha_inicio DATE NULL COMMENT 'Fecha de inicio de aplicación de la variable'
        """))
        
        # Crear índice
        print("Creando índice...")
        session.execute(text("""
            CREATE INDEX idx_simulation_variables_fecha_inicio 
            ON simulation_variables(fecha_inicio)
        """))
        
        session.commit()
        print("✓ Migración completada exitosamente")
        print("  - Campo 'fecha_inicio' agregado a 'simulation_variables'")
        print("  - Índice creado")
        
    except Exception as e:
        session.rollback()
        print(f"✗ Error durante la migración: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
