# utils/market_holdings.py
import yfinance as yf
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from database import db
from models.holding import HoldingPlan, Holding, HoldingPurchase, PriceSnapshot

CACHE_TTL = timedelta(minutes=5)  # tiempo de cache

def fetch_price_yfinance(ticker: str) -> Decimal:
    """Consulta yfinance y devuelve precio como Decimal."""
    t = yf.Ticker(ticker)
    # intentamos regularMarketPrice o el close del día
    try:
        info = t.history(period="1d", interval="1d")
        if not info.empty:
            last = info['Close'].iloc[-1]
            return Decimal(str(float(last)))
    except Exception:
        pass
    try:
        info2 = t.info
        price = info2.get("regularMarketPrice") or info2.get("currentPrice")
        if price is not None:
            return Decimal(str(price))
    except Exception:
        pass
    raise RuntimeError(f"No se pudo obtener precio para {ticker}")


def get_cached_price(session, ticker: str, refresh: bool = False) -> (Decimal | None, datetime | None):
    """
    Devuelve (price, updated_at). Si existe snapshot y no caducó y refresh==False,
    devuelve el cache; si no, consulta provider y actualiza snapshot.
    """
    ticker_u = ticker.upper()
    snap = session.query(PriceSnapshot).filter_by(ticker=ticker_u).one_or_none()
    now = datetime.now(timezone.utc)

    if snap and snap.price is not None and not refresh:
        if snap.updated_at and (now - snap.updated_at) < CACHE_TTL:
            return Decimal(str(snap.price)), snap.updated_at

    # obtener precio y guardar/actualizar snapshot
    price = fetch_price_yfinance(ticker_u)
    if snap is None:
        snap = PriceSnapshot(ticker=ticker_u, price=float(price), updated_at=now)
        session.add(snap)
    else:
        snap.price = float(price)
        snap.updated_at = now
    session.commit()
    return price, now


def add_plan(session, nombre: str, descripcion: str | None = None) -> HoldingPlan:
    p = HoldingPlan(nombre=nombre, descripcion=descripcion)
    session.add(p)
    session.commit()
    return p


def add_holding(session, plan_id: int, ticker: str, exchange: str | None = None, moneda: str = "USD") -> Holding:
    h = Holding(plan_id=plan_id, ticker=ticker.upper(), exchange=exchange, moneda=moneda)
    session.add(h)
    session.commit()
    return h


def add_purchase(session, holding_id: int, fecha, cantidad, precio_unitario, nota: str | None = None) -> HoldingPurchase:
    p = HoldingPurchase(
        holding_id=holding_id,
        fecha=fecha,
        cantidad=Decimal(str(cantidad)),
        precio_unitario=Decimal(str(precio_unitario)),
        nota=nota
    )
    session.add(p)
    session.commit()
    return p


def compute_plan_value(session, plan_id: int, refresh_prices: bool = False):
    """
    Devuelve detalle por ticker y valor agregado del plan:
    {
      'plan': {...},
      'by_ticker': [
         { 'ticker': 'AAPL', 'cantidad_total': Decimal, 'precio_actual': Decimal, 'valor_actual': Decimal, 'compras': [ ... ] }
      ],
      'valor_total': Decimal
    }
    """
    plan = session.get(HoldingPlan, plan_id)
    if not plan:
        raise ValueError("Plan no encontrado")

    result = {'plan': plan, 'by_ticker': [], 'valor_total': Decimal('0')}
    for h in plan.holdings:
        # sumar cantidad total comprada
        cantidad_total = Decimal('0')
        compras = []
        for pu in h.purchases:
            cantidad_total += Decimal(str(pu.cantidad))
            compras.append({
                'id': pu.id,
                'fecha': pu.fecha,
                'cantidad': Decimal(str(pu.cantidad)),
                'precio_unitario': Decimal(str(pu.precio_unitario)),
                'valor_compra': (Decimal(str(pu.cantidad)) * Decimal(str(pu.precio_unitario)))
            })

        # obtener precio actual (cacheado)
        try:
            precio_actual, when = get_cached_price(session, h.ticker, refresh=refresh_prices)
        except Exception as e:
            precio_actual = None
            when = None

        valor_actual = (cantidad_total * precio_actual) if (precio_actual is not None) else None
        if valor_actual is not None:
            result['valor_total'] += valor_actual

        result['by_ticker'].append({
            'holding_id': h.id,
            'ticker': h.ticker,
            'exchange': h.exchange,
            'moneda': h.moneda,
            'cantidad_total': cantidad_total,
            'precio_actual': precio_actual,
            'precio_updated_at': when,
            'valor_actual': valor_actual,
            'compras': compras
        })

    return result
ⁿ