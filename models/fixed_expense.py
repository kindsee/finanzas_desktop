# models/fixed_expense.py
from sqlalchemy import Column, Integer, String, Numeric, Date, Enum, ForeignKey
from sqlalchemy.orm import relationship
from database import db


class FixedExpense(db.Base):
    __tablename__ = "fixed_expense"

    id = Column(Integer, primary_key=True)
    cuenta_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    descripcion = Column(String(100), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    frecuencia = Column(Enum("semanal", "mensual", "trimestral", "semestral", "anual", name="frecuencia_enum"), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=True)
    es_transferencia = Column(Integer, default=0)  # 0=no, 1=sí (Boolean como Integer para compatibilidad)

    # Relación con la cuenta
    cuenta = relationship("Account", backref="fixed_expenses")

    def __repr__(self):
        return f"<FixedExpense id={self.id} cuenta={self.cuenta_id} desc={self.descripcion} monto={self.monto} frecuencia={self.frecuencia}>"

    def to_dict(self):
        return {
            "id": self.id,
            "cuenta_id": self.cuenta_id,
            "descripcion": self.descripcion,
            "monto": float(self.monto),
            "frecuencia": self.frecuencia,
            "fecha_inicio": self.fecha_inicio.isoformat(),
            "fecha_fin": self.fecha_fin.isoformat() if self.fecha_fin else None,
            "es_transferencia": bool(getattr(self, "es_transferencia", 0))
        }
