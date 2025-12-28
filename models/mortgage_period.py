# models/mortgage_period.py
from sqlalchemy import Column, Integer, Float, Date, ForeignKey,DECIMAL
from sqlalchemy.orm import relationship
from database import db


class MortgagePeriod(db.Base):
    __tablename__ = "mortgage_interest"

    id = Column(Integer, primary_key=True)
    mortgage_id = Column(Integer, ForeignKey("mortgage.id"), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    capital_inicio = Column(Float, nullable=False)
    capital_fin = Column(Float, nullable=False)
    interes = Column(Float, nullable=False)
    # 👇 Nuevos campos persistentes
    interes_total = Column(DECIMAL(15, 2), default=0)
    amortizacion_total = Column(DECIMAL(15, 2), default=0)

    mortgage = relationship("Mortgage", backref="periodos")

    def __repr__(self):
        return f"<MortgagePeriod id={self.id} mortgage={self.mortgage_id} inicio={self.fecha_inicio} fin={self.fecha_fin} interes={self.interes} interes_total={self.interes_total} amortizacion_total={self.amortizacion_total}>"
