# utils/reconciler.py
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from models.account import Account
from models.transaction import Transaction
from models.adjustment import Adjustment
from models.fixed_expense import FixedExpense
from database import db
from typing import Dict, List
from sqlalchemy import select, or_, func
from decimal import Decimal
from collections import defaultdict

def calcular_balance_cuenta(session, cuenta_id: int, fecha_objetivo: date) -> float:
    """
    Calcula el balance de la cuenta hasta `fecha_objetivo`.
    Tiene en cuenta:
      - saldo inicial desde la fecha de inicio de la cuenta
      - transacciones
      - ajustes
      - gastos o ingresos fijos recurrentes
    """
    cuenta = session.get(Account, cuenta_id)
    if not cuenta:
        raise ValueError(f"Cuenta {cuenta_id} no encontrada")

    saldo = Decimal(str(cuenta.saldo_inicial or 0))

    # Definir fecha de inicio de la cuenta (por defecto 01/01/2024 si no existe)
    fecha_inicio_cuenta = getattr(cuenta, "fecha_inicio", date(2024, 1, 1))

    # --- 1) Ajustes ---
    ajustes = session.scalars(
        select(Adjustment)
        .where(
            Adjustment.cuenta_id == cuenta_id,
            Adjustment.fecha <= fecha_objetivo
        )
    ).all()
    for adj in ajustes:
        saldo += Decimal(str(adj.monto_ajuste))

    # --- 2) Transacciones ---
    transacciones = session.scalars(
        select(Transaction)
        .where(
            Transaction.cuenta_id == cuenta_id,
            Transaction.fecha <= fecha_objetivo
        )
    ).all()
    for t in transacciones:
        saldo += Decimal(str(t.monto))

    # --- 3) Gastos fijos ---
    fijos = session.scalars(
        select(FixedExpense)
        .where(
            FixedExpense.cuenta_id == cuenta_id,
            FixedExpense.fecha_inicio <= fecha_objetivo,
            or_(
                FixedExpense.fecha_fin == None,
                FixedExpense.fecha_fin >= fecha_inicio_cuenta
            )
        )
    ).all()

    for f in fijos:
        # fecha de inicio efectiva
        inicio = max(f.fecha_inicio, fecha_inicio_cuenta)
        # fecha de fin efectiva
        fin = f.fecha_fin if f.fecha_fin and f.fecha_fin < fecha_objetivo else fecha_objetivo

        ocurrencia = inicio
        while ocurrencia <= fin:
            saldo += Decimal(str(f.monto))

            # calcular siguiente ocurrencia según frecuencia
            if f.frecuencia == "semanal":
                ocurrencia += timedelta(weeks=1)
            elif f.frecuencia == "mensual":
                ocurrencia += relativedelta(months=1)
            elif f.frecuencia == "trimestral":
                ocurrencia += relativedelta(months=3)
            elif f.frecuencia == "semestral":
                ocurrencia += relativedelta(months=6)
            elif f.frecuencia == "anual":
                ocurrencia += relativedelta(years=1)
            else:
                break

    return float(saldo)
def calcular_detalle_acumulado(session, cuenta_id: int, fecha_inicio: date, fecha_fin: date) -> Dict:
    """
    Devuelve el detalle de movimientos entre fecha_inicio y fecha_fin (inclusive)
    y sumas agregadas (ingresos/gastos/neto) para la cuenta indicada.

    Retorna diccionario con keys: 'detalle' (lista de dicts), 'ingresos', 'gastos', 'neto', 'cantidad_movimientos'.
    """
    # Importar modelos localmente para evitar problemas circulares al importar el módulo
    from models.transaction import Transaction
    from models.adjustment import Adjustment
    from models.fixed_expense import FixedExpense
    from models.account import Account

    # seguridad: fechas coherentes
    if fecha_fin < fecha_inicio:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    movimientos: List[dict] = []
    ingresos = Decimal("0")
    gastos = Decimal("0")

    # --- Ajustes en rango ---
    ajustes = session.scalars(
        select(Adjustment)
        .where(
            Adjustment.cuenta_id == cuenta_id,
            Adjustment.fecha >= fecha_inicio,
            Adjustment.fecha <= fecha_fin
        )
    ).all()
    for adj in ajustes:
        monto = Decimal(str(adj.monto_ajuste))
        movimientos.append({
            "fecha": adj.fecha,
            "descripcion": adj.descripcion or "Ajuste",
            "monto": monto,
            "tipo": "adjustment"
        })
        if monto >= 0:
            ingresos += monto
        else:
            gastos += monto

    # --- Transacciones puntuales en rango ---
    transacciones = session.scalars(
        select(Transaction)
        .where(
            Transaction.cuenta_id == cuenta_id,
            Transaction.fecha >= fecha_inicio,
            Transaction.fecha <= fecha_fin
        )
    ).all()
    for t in transacciones:
        monto = Decimal(str(t.monto))
        movimientos.append({
            "fecha": t.fecha,
            "descripcion": t.descripcion or "",
            "monto": monto,
            "tipo": "transaction"
        })
        if monto >= 0:
            ingresos += monto
        else:
            gastos += monto

    # --- Gastos/ingresos fijos: generar ocurrencias dentro del rango ---
    fijos = session.scalars(
        select(FixedExpense)
        .where(
            FixedExpense.cuenta_id == cuenta_id,
            FixedExpense.fecha_inicio <= fecha_fin,
            or_(
                FixedExpense.fecha_fin == None,
                FixedExpense.fecha_fin >= fecha_inicio
            )
        )
    ).all()

    for f in fijos:
        # determinar intervalo efectivo del fijo limitado al rango pedido
        inicio = max(f.fecha_inicio, fecha_inicio)
        fin = f.fecha_fin if f.fecha_fin is not None else fecha_fin
        fin = min(fin, fecha_fin)

        ocurrencia = inicio
        while ocurrencia <= fin:
            monto = Decimal(str(f.monto))
            movimientos.append({
                "fecha": ocurrencia,
                "descripcion": f.descripcion or "Gasto/Recurso Fijo",
                "monto": monto,
                "tipo": "fixed_expense"
            })
            if monto >= 0:
                ingresos += monto
            else:
                gastos += monto

            # avanzar según frecuencia
            if f.frecuencia == "semanal":
                ocurrencia += timedelta(weeks=1)
            elif f.frecuencia == "mensual":
                ocurrencia += relativedelta(months=1)
            elif f.frecuencia == "trimestral":
                ocurrencia += relativedelta(months=3)
            elif f.frecuencia == "semestral":
                ocurrencia += relativedelta(months=6)
            elif f.frecuencia == "anual":
                ocurrencia += relativedelta(years=1)
            else:
                # si frecuencia desconocida, evitar loop infinito
                break

    # --- ordenar por fecha y tipo (opcional: mantener mismo criterio que calcular_detalle_cuenta) ---
    tipo_orden = {"fixed_expense": 1, "adjustment": 2, "transaction": 3}
    movimientos.sort(key=lambda m: (m["fecha"], tipo_orden.get(m["tipo"], 99)))

    neto = ingresos + gastos  # recuerda: gastos es negativo
    return {
        "detalle": movimientos,
        "ingresos": ingresos,
        "gastos": gastos,
        "neto": neto,
        "cantidad_movimientos": len(movimientos)
    }

def calcular_detalle_cuenta(session, cuenta_id: int, fecha_objetivo: date):
    """
    Devuelve el listado de movimientos ordenados cronológicamente y el saldo final
    calculado correctamente en base a:
    - saldo inicial de la cuenta
    - ajustes
    - transacciones
    - gastos o ingresos fijos recurrentes
    """
    cuenta = session.get(Account, cuenta_id)
    if not cuenta:
        raise ValueError(f"Cuenta {cuenta_id} no encontrada")

    movimientos = []
    saldo = Decimal(cuenta.saldo_inicial or 0)

    # 1. Agregar saldo inicial
    fecha_inicio = date(2024, 1, 1)  # usamos fecha de inicio por defecto 01/01/2024
    movimientos.append({
        "fecha": fecha_inicio,
        "descripcion": "Inicio",
        "monto": Decimal(0),
        "saldo": saldo,
        "tipo": "account"
    })

    # 2. Obtener ajustes
    ajustes = session.scalars(
        select(Adjustment)
        .where(
            Adjustment.cuenta_id == cuenta_id,
            Adjustment.fecha <= fecha_objetivo
        )
    ).all()

    for adj in ajustes:
        movimientos.append({
            "fecha": adj.fecha,
            "descripcion": adj.descripcion or "Ajuste",
            "monto": Decimal(adj.monto_ajuste),
            "saldo": None,
            "tipo": "adjustment"
        })

    # 3. Obtener transacciones puntuales
    transacciones = session.scalars(
        select(Transaction)
        .where(
            Transaction.cuenta_id == cuenta_id,
            Transaction.fecha <= fecha_objetivo
        )
    ).all()

    for t in transacciones:
        movimientos.append({
            "fecha": t.fecha,
            "descripcion": t.descripcion,
            "monto": Decimal(t.monto),
            "saldo": None,
            "tipo": "transaction"
        })

    # 4. Calcular gastos/ingresos fijos
    fijos = session.scalars(
        select(FixedExpense)
        .where(
            FixedExpense.cuenta_id == cuenta_id,
            FixedExpense.fecha_inicio <= fecha_objetivo,
            or_(
                FixedExpense.fecha_fin == None,
                FixedExpense.fecha_fin >= FixedExpense.fecha_inicio
            )
        )
    ).all()

    for f in fijos:
        ocurrencia = f.fecha_inicio
        fin = f.fecha_fin or fecha_objetivo

        while ocurrencia <= fecha_objetivo and ocurrencia <= fin:
            movimientos.append({
                "fecha": ocurrencia,
                "descripcion": f.descripcion,
                "monto": Decimal(f.monto),
                "saldo": None,
                "tipo": "fixed_expense"
            })

            # Avanzar según frecuencia
            if f.frecuencia == "semanal":
                ocurrencia += timedelta(weeks=1)
            elif f.frecuencia == "mensual":
                ocurrencia += relativedelta(months=1)
            elif f.frecuencia == "trimestral":
                ocurrencia += relativedelta(months=3)
            elif f.frecuencia == "semestral":
                ocurrencia += relativedelta(months=6)
            elif f.frecuencia == "anual":
                ocurrencia += relativedelta(years=1)
            else:
                break

    # 5. Ordenar movimientos por fecha y tipo
    #    Fijo primero, luego ajuste, luego transacción para fechas iguales
    tipo_orden = {"account": 0, "fixed_expense": 1, "adjustment": 2, "transaction": 3}
    movimientos.sort(key=lambda m: (m["fecha"], tipo_orden.get(m["tipo"], 99)))

    # 6. Calcular saldo acumulado
    saldo_actual = saldo
    for m in movimientos:
        if m["tipo"] != "account":  # el saldo inicial ya está fijado
            saldo_actual += Decimal(m["monto"])
            m["saldo"] = saldo_actual

    return movimientos, float(saldo_actual)
def reconciliar_cuenta(session, cuenta_id: int, fecha_reconciliacion: date, saldo_objetivo: float, descripcion: str = "Reconciliación"):
    """
    Crea un ajuste de reconciliación para que la cuenta tenga el saldo indicado en la fecha.
    
    session: sesión SQLAlchemy abierta
    cuenta_id: id de la cuenta a reconciliar
    fecha_reconciliacion: fecha en que se aplica la reconciliación
    saldo_objetivo: saldo que queremos que tenga la cuenta en esa fecha
    descripcion: descripción opcional del ajuste
    """
    from models.account import Account

    # Obtener saldo actual hasta la fecha
    cuenta = session.get(Account, cuenta_id)
    if not cuenta:
        raise ValueError(f"Cuenta {cuenta_id} no encontrada")

    from utils.reconciler import calcular_balance_cuenta
    saldo_actual = Decimal(str(calcular_balance_cuenta(session, cuenta_id, fecha_reconciliacion)))

    # Diferencia que hay que ajustar
    monto_ajuste = Decimal(str(saldo_objetivo)) - saldo_actual

    # Crear el ajuste
    ajuste = Adjustment(
        cuenta_id=cuenta_id,
        fecha=fecha_reconciliacion,
        monto_ajuste=monto_ajuste,
        descripcion=descripcion
    )

    session.add(ajuste)
    session.commit()
    return ajuste

def obtener_gastos_top(session, cuenta_id: int | None = None, meses: int = 6, limite: int = 10):
    """
    Devuelve los gastos (fijos + puntuales) más altos de los últimos `meses` meses.
    Si `cuenta_id` es None, suma los gastos de todas las cuentas.

    Retorna lista de tuplas: [(descripcion, total_gasto, tipo)]
    tipo puede ser 'fijo' o 'puntual'
    """

    hoy = date.today()
    fecha_inicio = hoy - relativedelta(months=meses)

    # Si no se especifica cuenta, las buscamos todas
    if cuenta_id is None:
        cuentas = [c.id for c in session.query(Account.id).all()]
    else:
        cuentas = [cuenta_id]

    # Acumuladores globales (usamos Decimal para evitar mezclas)
    gastos_puntuales_global = defaultdict(Decimal)
    gastos_fijos_global = defaultdict(Decimal)

    for cid in cuentas:
        # ------------------------
        # 1️⃣ Transacciones puntuales (excluyendo transferencias)
        # ------------------------
        transacciones = session.execute(
            select(Transaction.descripcion, func.sum(Transaction.monto))
            .where(
                Transaction.cuenta_id == cid,
                Transaction.fecha >= fecha_inicio,
                Transaction.fecha <= hoy,
                Transaction.monto < 0,
                Transaction.es_transferencia == 0  # Excluir transferencias
            )
            .group_by(Transaction.descripcion)
        ).all()

        for desc, total in transacciones:
            if total is None:
                continue
            gastos_puntuales_global[desc] += Decimal(str(total))

        # ------------------------
        # 2️⃣ Gastos fijos recurrentes (excluyendo transferencias)
        # ------------------------
        fijos = session.scalars(
            select(FixedExpense)
            .where(
                FixedExpense.cuenta_id == cid,
                FixedExpense.fecha_inicio <= hoy,
                FixedExpense.es_transferencia == 0,  # Excluir transferencias
                or_(
                    FixedExpense.fecha_fin == None,
                    FixedExpense.fecha_fin >= fecha_inicio
                )
            )
        ).all()

        for f in fijos:
            ocurrencia = max(f.fecha_inicio, fecha_inicio)
            fin = f.fecha_fin or hoy

            while ocurrencia <= hoy and ocurrencia <= fin:
                monto = Decimal(str(f.monto))
                if monto < 0:
                    gastos_fijos_global[f.descripcion] += monto

                # avanzar según frecuencia
                if f.frecuencia == "semanal":
                    ocurrencia += timedelta(weeks=1)
                elif f.frecuencia == "mensual":
                    ocurrencia += relativedelta(months=1)
                elif f.frecuencia == "trimestral":
                    ocurrencia += relativedelta(months=3)
                elif f.frecuencia == "semestral":
                    ocurrencia += relativedelta(months=6)
                elif f.frecuencia == "anual":
                    ocurrencia += relativedelta(years=1)
                else:
                    break

    # Combinar resultados
    gastos_puntuales_lista = [(d, float(v), "puntual") for d, v in gastos_puntuales_global.items()]
    gastos_fijos_lista = [(d, float(v), "fijo") for d, v in gastos_fijos_global.items()]

    todos = gastos_puntuales_lista + gastos_fijos_lista
    todos.sort(key=lambda x: x[1])  # más negativos primero (más gasto)
    return todos[:limite]