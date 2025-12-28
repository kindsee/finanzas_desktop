# test_calculo_cuenta.py
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from database import db
from models.account import Account
from models.transaction import Transaction
from models.adjustment import Adjustment
from models.fixed_expense import FixedExpense
from utils.reconciler import calcular_detalle_cuenta
from database import db

# Inicializa DB (usa DATABASE_URL en .env o el que hayas configurado)
db.init_app()


def main():
    # Inicializamos sesión
    session = db.session()
    try:
        # Crear cuenta de test si no existe
        cuenta_id = 2
        cuenta = session.get(Account, cuenta_id)
        if not cuenta:
            cuenta = Account(id=cuenta_id, nombre="TestCuenta", saldo_inicial=391.64)
            session.merge(cuenta)
            session.commit()

        # Fecha de inicio de la cuenta para el cálculo
        fecha_inicio_cuenta = date(2025, 1, 1)

        # Fecha objetivo para calcular saldo
        fecha_objetivo = date(2025, 11, 4)

        # Calcular detalle de movimientos y saldo final
        movimientos, saldo_final = calcular_detalle_cuenta(session, cuenta_id, fecha_objetivo)

        # Mostrar resultados
        print("==== DETALLE DE CUENTA ====")
        print(f"{'Fecha':<15}{'Tipo':<15}{'Concepto':<25}{'Importe':>10} {'Saldo':>10}")
        for m in movimientos:
            fecha = m["fecha"]
            tipo = m["tipo"]
            concepto = m["descripcion"]
            importe = float(m["monto"]) if m["monto"] is not None else 0
            saldo = float(m["saldo"]) if m["saldo"] is not None else 0
            print(f"{fecha} {tipo:<15} {concepto:<25} {importe:10.2f} {saldo:10.2f}")

        print(f"\nSaldo final a {fecha_objetivo}: {saldo_final:.2f} €")

    finally:
        session.close()


if __name__ == "__main__":
    main()
