from sqlalchemy import Column, Integer, String, Float, Date
from database import db


class Mortgage(db.Base):
    __tablename__ = "mortgage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(20), nullable=False)  # fijo o variable
    fecha_inicio = Column(Date, nullable=False)
    capital_inicial = Column(Float, nullable=False)
    cuotas_totales = Column(Integer, nullable=False)
    valor_actual_propiedad = Column(Float, nullable=True)  # 💰 nuevo campo

    def __repr__(self):
        return (f"<Mortgage id={self.id} nombre={self.nombre} tipo={self.tipo} "
                f"capital={self.capital_inicial} cuotas={self.cuotas_totales} "
                f"valor_actual_propiedad={self.valor_actual_propiedad}>")