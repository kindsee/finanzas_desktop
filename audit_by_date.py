# test_audit_using_existing.py
import argparse
from datetime import datetime, date
from decimal import Decimal

from database import db
from utils.reconciler import calcular_detalle_cuenta, calcular_balance_cuenta

def parse_args():
    p = argparse.ArgumentParser(description="Simular auditoría usando calcular_detalle_cuenta (sin crear nuevos métodos).")
    p.add_argument("--cuenta", "-c", type=int, default=2, help="ID de la cuenta (por defecto 8)")
    p.add_argument("--desde", "-d", type=str, required=True, help="Fecha desde (YYYY-MM-DD)")
    p.add_argument("--hasta", "-a", type=str, required=True, help="Fecha hasta (YYYY-MM-DD)")
    return p.parse_args()

def to_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

def main():
    args = parse_args()
    cuenta_id = args.cuenta
    fecha_desde = to_date(args.desde)
    fecha_hasta = to_date(args.hasta)

    # inicializar DB (ajusta si tu init_app necesita parámetros)
    try:
        db.init_app()
    except Exception:
        pass

    session = db.session()
    try:
        # 1) Obtenemos TODOS los movimientos hasta fecha_hasta con tu función actual
        movimientos_all, saldo_hasta = calcular_detalle_cuenta(session, cuenta_id, fecha_hasta)

        # normalizar fecha -> date (si vienen datetimes)
        def _to_date(d):
            return d.date() if hasattr(d, "date") else d

        # 2) Determinar saldo justo ANTES de fecha_desde:
        saldo_antes = None
        for m in reversed(movimientos_all):
            mfecha = _to_date(m.get("fecha"))
            if mfecha < fecha_desde:
                saldo_antes = Decimal(str(m.get("saldo", 0)))
                break

        # si no hay movimiento antes, usamos saldo inicial (primer movimiento) o 0
        if saldo_antes is None:
            if movimientos_all:
                saldo_antes = Decimal(str(movimientos_all[0].get("saldo", 0)))
            else:
                # fallback: pedir saldo con calcular_balance_cuenta hasta fecha_desde - 1
                saldo_antes = Decimal(str(calcular_balance_cuenta(session, cuenta_id, fecha_desde)))

        # 3) Filtrar movimientos entre fecha_desde y fecha_hasta (inclusive)
        movimientos_rango = []
        for m in movimientos_all:
            mfecha = _to_date(m.get("fecha"))
            if fecha_desde <= mfecha <= fecha_hasta:
                importe = Decimal(str(m.get("monto", 0)))
                movimientos_rango.append({
                    "fecha": mfecha,
                    "tipo": m.get("tipo"),
                    "descripcion": m.get("descripcion") or m.get("concepto") or "",
                    "monto": importe,
                    "saldo": None
                })

        # 4) Recalcular saldos parciales dentro del rango partiendo de saldo_antes
        saldo_corriente = saldo_antes
        for m in movimientos_rango:
            saldo_corriente += m["monto"]
            m["saldo"] = saldo_corriente

        # 5) Impresión: cabecera y movimientos
        print(f"\n=== Auditoría simulada (cuenta {cuenta_id}) desde {fecha_desde} hasta {fecha_hasta} ===\n")
        print(f"Saldo justo ANTES de {fecha_desde}: {float(saldo_antes):.2f} €")
        print()
        print(f"{'Fecha':<12} {'Tipo':<14} {'Concepto':<30} {'Importe':>10} {'Saldo':>12}")
        print("-" * 84)
        for m in movimientos_rango:
            fecha = m["fecha"]
            tipo = m["tipo"] or ""
            concepto = m["descripcion"]
            importe = float(m["monto"])
            saldo = float(m["saldo"])
            print(f"{fecha!s:<12};{tipo:<14};{concepto:<30};{importe:10.2f};{saldo:12.2f}")
        print("-" * 84)
        print(f"Saldo final a {fecha_hasta}: {float(saldo_corriente):.2f} €")
        # comprobación: calcular_balance_cuenta hasta fecha_hasta
        saldo_check = calcular_balance_cuenta(session, cuenta_id, fecha_hasta)
        print(f"Saldo (calcular_balance_cuenta) a {fecha_hasta}: {saldo_check:.2f} €")
        if abs(float(saldo_corriente) - float(saldo_check)) > 0.01:
            print("\nAVISO: saldo final del rango y calcular_balance_cuenta DIFEREN. Recomendado inspeccionar movimientos_all.")
            # imprime algunos movimientos_all para depuración (opcional)
            print("\n--- Primeros 10 movimientos_all (para depurar) ---")
            for i, mm in enumerate(movimientos_all[:10], start=1):
                print(i, mm)
    except Exception as e:
        print("ERROR durante la simulación:", e)
    finally:
        session.close()

if __name__ == "__main__":
    main()
