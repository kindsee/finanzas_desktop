#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de prueba para la funcionalidad de simulación
Muestra cómo usar las funciones de simulación programáticamente
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from database import db
from models.account import Account
from models.simulation_variable import SimulationVariable
from utils.reconciler import calcular_balance_cuenta
from decimal import Decimal

def test_simulation():
    """Prueba la funcionalidad de simulación"""
    
    # Inicializar base de datos
    db.init_app()
    
    if not db.engine:
        print("❌ Error: No se pudo conectar a la base de datos")
        return
    
    session = db.session()
    
    try:
        print("=" * 70)
        print("  PRUEBA DE SIMULACIÓN")
        print("=" * 70)
        
        # 1. Mostrar cuentas disponibles
        print("\n📊 Cuentas disponibles:")
        cuentas = session.query(Account).order_by(Account.nombre).all()
        for i, cuenta in enumerate(cuentas, 1):
            saldo_actual = calcular_balance_cuenta(session, cuenta.id, date.today())
            print(f"  {i}. {cuenta.nombre}: {saldo_actual:,.2f} €")
        
        if not cuentas:
            print("  ⚠️ No hay cuentas registradas")
            return
        
        # 2. Mostrar variables activas
        print("\n🎯 Variables de simulación activas:")
        variables = session.query(SimulationVariable).filter_by(activo=1).all()
        if variables:
            for var in variables:
                cuenta_nombre = var.cuenta.nombre if var.cuenta else "N/A"
                signo = "+" if var.importe >= 0 else ""
                print(f"  • {var.descripcion}")
                print(f"    Cuenta: {cuenta_nombre} | Importe: {signo}{var.importe} € | Frecuencia: {var.frecuencia}")
        else:
            print("  ⚠️ No hay variables activas")
            print("  💡 Crea variables desde la UI o añádelas directamente:")
            print("     var = SimulationVariable(")
            print("         descripcion='Mi variable',")
            print("         cuenta_id=1,")
            print("         importe=500.0,")
            print("         frecuencia='mensual',")
            print("         activo=1")
            print("     )")
            print("     session.add(var)")
            print("     session.commit()")
        
        # 3. Simular para los próximos 6 meses
        print("\n🔮 Simulación para los próximos 6 meses (mensual):")
        print("-" * 70)
        
        fecha_inicio = date.today()
        fecha_fin = fecha_inicio + relativedelta(months=6)
        intervalo = 30  # días
        
        # Preparar encabezado de tabla
        headers = ["Fecha"]
        cuenta_ids = []
        for cuenta in cuentas[:3]:  # Máximo 3 cuentas para que quepa en pantalla
            headers.append(cuenta.nombre[:15])  # Truncar nombre largo
            cuenta_ids.append(cuenta.id)
        headers.append("TOTAL")
        
        # Formatear encabezado
        col_widths = [12] + [18] * len(cuenta_ids) + [18]
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        print(header_line)
        print("-" * len(header_line))
        
        # Pre-calcular efectos de variables
        efectos_variables = {cid: {} for cid in cuenta_ids}
        for variable in variables:
            if variable.cuenta_id not in efectos_variables:
                continue
            
            fecha_var = fecha_inicio
            while fecha_var <= fecha_fin:
                if fecha_var not in efectos_variables[variable.cuenta_id]:
                    efectos_variables[variable.cuenta_id][fecha_var] = Decimal('0')
                
                efectos_variables[variable.cuenta_id][fecha_var] += Decimal(str(variable.importe))
                
                # Siguiente fecha según frecuencia
                if variable.frecuencia == 'semanal':
                    fecha_var += timedelta(days=7)
                elif variable.frecuencia == 'mensual':
                    fecha_var += relativedelta(months=1)
                elif variable.frecuencia == 'trimestral':
                    fecha_var += relativedelta(months=3)
                elif variable.frecuencia == 'semestral':
                    fecha_var += relativedelta(months=6)
                elif variable.frecuencia == 'anual':
                    fecha_var += relativedelta(years=1)
                else:
                    break
        
        # Calcular y mostrar simulación
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            row = [fecha_actual.strftime("%d/%m/%Y")]
            total = 0.0
            
            for cuenta_id in cuenta_ids:
                # Saldo base
                saldo_base = calcular_balance_cuenta(session, cuenta_id, fecha_actual)
                
                # Aplicar efectos de variables
                efecto_total = Decimal('0')
                for fecha_efecto, importe in efectos_variables[cuenta_id].items():
                    if fecha_efecto <= fecha_actual:
                        efecto_total += importe
                
                saldo_final = float(Decimal(str(saldo_base)) + efecto_total)
                total += saldo_final
                
                row.append(f"{saldo_final:,.2f} €")
            
            row.append(f"{total:,.2f} €")
            
            # Formatear fila
            row_line = " | ".join(str(val).ljust(w) for val, w in zip(row, col_widths))
            print(row_line)
            
            fecha_actual += timedelta(days=intervalo)
        
        print("-" * 70)
        print("\n✅ Simulación completada")
        
        if not variables:
            print("\n💡 Para ver resultados más interesantes, crea variables de simulación")
            print("   desde la ventana de Simulación en la aplicación principal.")
        
    except Exception as e:
        print(f"\n❌ Error en la simulación: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_simulation()
