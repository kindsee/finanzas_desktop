from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.orm import relationship
from database import db

class Account(db.Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False)
    saldo_inicial = Column(Numeric(12,2), nullable=False)
    visible = Column(Integer, default=1)  # 1=visible, 0=oculta en UI

    # Relaciones
    ajustes = relationship("Adjustment", back_populates="cuenta", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account id={self.id} nombre={self.nombre} saldo={self.saldo_inicial}>"
