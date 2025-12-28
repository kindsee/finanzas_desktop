from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import db

class Adjustment(db.Base):
    __tablename__ = "adjustment"

    id = Column(Integer, primary_key=True)
    cuenta_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    monto_ajuste = Column(Float, nullable=False)
    descripcion = Column(String(255), nullable=True)

    cuenta = relationship("Account", back_populates="ajustes")

    def __repr__(self):
        return f"<Adjustment id={self.id} cuenta_id={self.cuenta_id} monto={self.monto_ajuste}>"
