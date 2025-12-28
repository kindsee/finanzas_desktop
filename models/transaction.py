# models/transaction.py
from sqlalchemy import Column, Integer, ForeignKey, Date, String, Numeric, func, select
from sqlalchemy.orm import relationship
from database import db
from datetime import date
from dateutil.relativedelta import relativedelta


class Transaction(db.Base):
    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True)
    cuenta_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    descripcion = Column(String(255), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    es_transferencia = Column(Integer, default=0)  # 0=no, 1=sí (Boolean como Integer para compatibilidad)

    # Relación con la cuenta
    cuenta = relationship("Account", backref="transactions")

    def __repr__(self):
        return f"<Transaction id={self.id} cuenta={self.cuenta_id} fecha={self.fecha} monto={self.monto}>"

    def to_dict(self):
        return {
            "id": self.id,
            "cuenta_id": self.cuenta_id,
            "descripcion": self.descripcion,
            "monto": float(self.monto),
            "fecha": self.fecha.strftime("%Y-%m-%d"),
            "es_transferencia": bool(getattr(self, "es_transferencia", 0))
        }


# -------------------------------------------------------------
# Helper: obtener saldos de -2, -1, 0, +1 meses respecto a una fecha
# -------------------------------------------------------------
def get_saldos_por_mes(session, cuenta_id: int, fecha_central: date):
    """Devuelve lista [(fecha_inicio_mes, saldo)] para -2, -1, 0, +1 meses."""
    meses = [(fecha_central + relativedelta(months=i)).replace(day=1) for i in (-2, -1, 0, 1)]

    # Obtener saldo inicial de la cuenta
    acc_table = db.Base.metadata.tables["account"]
    saldo_inicial_row = session.execute(
        select(acc_table.c.saldo_inicial).where(acc_table.c.id == cuenta_id)
    ).first()
    saldo_inicial = float(saldo_inicial_row[0]) if saldo_inicial_row else 0.0

    result = []
    for m in meses:
        first_of_next = (m + relativedelta(months=1)).replace(day=1)
        # Total de transacciones hasta fin de ese mes
        total_transacciones = session.execute(
            select(func.coalesce(func.sum(Transaction.monto), 0))
            .where(Transaction.cuenta_id == cuenta_id)
            .where(Transaction.fecha < first_of_next)
        ).scalar_one()

        saldo_mes = saldo_inicial + float(total_transacciones or 0)
        result.append((m, saldo_mes))

    return result
