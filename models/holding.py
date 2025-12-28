# models/holding.py
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import relationship
from database import db
from datetime import datetime, timezone
from decimal import Decimal
import yfinance as yf
from sqlalchemy import func


class HoldingPlan(db.Base):
    __tablename__ = "holding_plan"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(120), nullable=False, unique=True)
    descripcion = Column(String(255), nullable=True)

    # relación: plan -> holdings
    holdings = relationship("Holding", back_populates="plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HoldingPlan id={self.id} nombre={self.nombre}>"


class Holding(db.Base):
    __tablename__ = "holding"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("holding_plan.id"), nullable=True)

    ticker = Column(String(50), nullable=False)         # e.g. 'AAPL', 'BB.MC'
    exchange = Column(String(30), nullable=True)        # 'NASDAQ', 'BME', etc.
    moneda = Column(String(8), nullable=True, default='USD')

    # columnas que en tu BD existen y faltaban en el modelo
    cantidad = Column(Float, nullable=False, default=0.0)   # en BD era DOUBLE NOT NULL DEFAULT 0
    last_price = Column(Float, nullable=True)               # last_price DOUBLE
    last_update = Column(DateTime, nullable=True)           # last_update DATETIME

    plan = relationship("HoldingPlan", back_populates="holdings")
    purchases = relationship("HoldingPurchase", back_populates="holding", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Holding id={self.id} ticker={self.ticker} plan_id={self.plan_id} cantidad={self.cantidad} last_price={self.last_price}>"


class HoldingPurchase(db.Base):
    __tablename__ = "holding_purchase"
    id = Column(Integer, primary_key=True, autoincrement=True)
    holding_id = Column(Integer, ForeignKey("holding.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    cantidad = Column(Numeric(24, 8), nullable=False)         # DECIMAL(24,8) en DB
    precio_unitario = Column(Numeric(24, 8), nullable=False)  # DECIMAL(24,8)
    comisiones = Column(Numeric(12, 2), nullable=True)        # si tienes comisiones en BD
    nota = Column(String(255), nullable=True)

    holding = relationship("Holding", back_populates="purchases")

    def __repr__(self):
        return f"<HoldingPurchase id={self.id} holding_id={self.holding_id} fecha={self.fecha} cantidad={self.cantidad} precio={self.precio_unitario}>"


class PriceSnapshot(db.Base):
    """
    Cache simple del precio actual por ticker (se puede mantener un registro por ticker)
    """
    __tablename__ = "price_snapshot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(50), nullable=False, unique=True)
    price = Column(Numeric(18, 6), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<PriceSnapshot ticker={self.ticker} price={self.price} updated_at={self.updated_at}>"

def fetch_price_yfinance_float(ticker: str) -> float | None:
    """Usar yfinance y devolver float (ya tenías una función parecida)."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1d", interval="1m")
        if hist is None or hist.empty:
            hist = t.history(period="5d")
            if hist is None or hist.empty:
                return None
        last_close = hist['Close'].iloc[-1]
        return float(round(last_close, 6))
    except Exception as e:
        print("fetch_price_yfinance error:", e)
        return None

def update_price_for_holding(session, holding) -> float | None:
    """
    Actualiza holding.last_price y holding.last_update usando yfinance.
    `holding` puede ser un ORM object (con sesión) o un objeto con .ticker y .id.
    Esta función hace session.add(holding) y session.flush(); NO hace commit, lo deja al caller.
    Devuelve el precio (float) o None.
    """
    price = fetch_price_yfinance_float(holding.ticker)
    if price is None:
        return None
    try:
        holding.last_price = price
        holding.last_update = datetime.utcnow()
        session.add(holding)
        session.flush()
        return price
    except Exception as e:
        print(f"update_price_for_holding error para {holding.ticker}: {e}")
        return None

def update_prices_for_all_holdings(session) -> list[tuple[str, float]]:
    """
    Recorre holdings y actualiza su last_price y last_update (llama a update_price_for_holding).
    Hace COMMIT al final para persistir todos los cambios.
    Devuelve lista de (ticker, price).
    """
    holdings = session.query(Holding).order_by(Holding.ticker).all()
    results = []
    for h in holdings:
        try:
            p = update_price_for_holding(session, h)
            if p is not None:
                results.append((h.ticker, float(p)))
        except Exception as e:
            print(f"Error actualizando precio holding id={getattr(h,'id',None)}: {e}")
    try:
        session.commit()
    except Exception as e:
        print("Error en commit de update_prices_for_all_holdings:", e)
        session.rollback()
    return results

def recalc_holding_cantidad(session, holding_id: int) -> float:
    """
    Suma todas las compras (holding_purchase.cantidad) y actualiza holding.cantidad con el total.
    Devuelve la cantidad total (float). Hace commit al final.
    """
    total = session.query(func.coalesce(func.sum(HoldingPurchase.cantidad), 0)).filter(
        HoldingPurchase.holding_id == holding_id
    ).scalar() or 0

    # obtener holding en la misma sesión
    h = session.get(Holding, holding_id)
    if not h:
        raise ValueError(f"Holding {holding_id} no encontrado al recalcular cantidad")
    try:
        h.cantidad = float(total)  # tu columna es DOUBLE en BD
        session.add(h)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return float(total)
    
def get_value_of_holding(session, holding_id: int) -> dict:
    """
    Devuelve resumen de un holding: cantidad total (suma compras), precio actual (snapshot),
    y valor = cantidad * precio.
    """
    print ("DEBUG: Llamamos a get_value_of_holding")
    # sumar cantidad comprada (puedes restar ventas si las implementas)
    total_qty = session.query(func.coalesce(func.sum(HoldingPurchase.cantidad), 0)).filter(
        HoldingPurchase.holding_id == holding_id
    ).scalar() or 0

    # leer snapshot
    h = session.get(Holding, holding_id)
    ticker = h.ticker
    snap = session.query(PriceSnapshot).filter(PriceSnapshot.ticker == ticker).one_or_none()
    price = Decimal(str(snap.price)) if snap and snap.price is not None else None
    value = (Decimal(str(total_qty)) * price) if (price is not None) else None

    return {
        "holding_id": holding_id,
        "ticker": ticker,
        "cantidad": Decimal(str(total_qty)),
        "precio_actual": price,
        "valor": value
    }

def portfolio_value(session, plan_id: int | None = None) -> Decimal:
    """
    Suma el valor de todos los holdings (opcional: por plan_id). Devuelve Decimal.
    Si falta precio para algún holding, intenta actualizarlo (o lo ignora según prefieras).
    """
    q = session.query(Holding)
    if plan_id is not None:
        q = q.filter(Holding.plan_id == plan_id)
    holdings = q.all()

    total = Decimal("0")
    for h in holdings:
        # obtener cantidad total
        qty = session.query(func.coalesce(func.sum(HoldingPurchase.cantidad), 0)).filter(
            HoldingPurchase.holding_id == h.id
        ).scalar() or 0

        # obtener price snapshot
        snap = session.query(PriceSnapshot).filter(PriceSnapshot.ticker == h.ticker).one_or_none()
        price = None
        if snap and snap.price is not None:
            price = Decimal(str(snap.price))
        else:
            # opcional: actualizar on-the-fly si falta el snapshot
            p = fetch_price_yfinance(h.ticker)
            if p is not None:
                price = p
                # guardar snapshot rápido
                ns = PriceSnapshot(ticker=h.ticker, price=p, updated_at=datetime.utcnow())
                session.add(ns)
                session.flush()

        if price is not None:
            total += Decimal(str(qty)) * price

    session.commit()
    return total