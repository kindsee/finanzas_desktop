from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class SimulationVariable(Base):
    __tablename__ = 'simulation_variables'
    
    id = Column(Integer, primary_key=True)
    descripcion = Column(String(255), nullable=False)
    cuenta_id = Column(Integer, ForeignKey('account.id'), nullable=False)
    importe = Column(Numeric(15, 2), nullable=False)
    frecuencia = Column(String(50), nullable=False)  # semanal, mensual, trimestral, semestral, anual
    activo = Column(Integer, default=1)  # 0=inactivo, 1=activo
    
    # Relationship
    cuenta = relationship("Account", backref="simulation_variables")
    
    def __repr__(self):
        return f"<SimulationVariable(id={self.id}, descripcion='{self.descripcion}', activo={self.activo})>"
