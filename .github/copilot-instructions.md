# Finanzas Desktop - AI Agent Instructions

## Project Overview
Desktop personal finance application built with PySide6 (Qt) and SQLAlchemy. Manages accounts, transactions, recurring expenses, mortgages, and investment holdings with forecasting capabilities.

## Architecture & Components

### Core Structure
- **main.py**: Application entry point with PyInstaller bootstrap logic (lines 1-60), MainWindow UI, ConfigDialog for DB setup, and account balance visualization with matplotlib
- **database/**: SQLAlchemy setup with lazy initialization (supports DB-less startup for config dialog). Engine uses `pool_pre_ping=True` for connection health checks
- **models/**: ORM entities - Account, Transaction, Adjustment, FixedExpense, Mortgage, MortgagePeriod, Holding (with `cantidad`, `last_price`, `last_update` columns), HoldingPlan, HoldingPurchase (DECIMAL(24,8) precision for crypto/stocks)
- **ui/**: Complex PySide6 widgets - AdminWindow (CRUD forms with QDialog+QFormLayout pattern), DashboardWidget (4-panel matplotlib grid: balance bars, mortgage amortization, top expenses, investments)
- **utils/**: Business logic - **reconciler.py** contains ALL balance calculation functions, market.py/market_holdings.py for yfinance ticker price fetching

### Critical Data Flow Pattern
**Always use `utils/reconciler.py` functions for balance calculations** - NEVER reimplement:
- `calcular_balance_cuenta(session, cuenta_id, fecha_objetivo)` → `float` - snapshot balance at date
- `calcular_detalle_cuenta(session, cuenta_id, fecha_objetivo)` → `(List[Dict], float)` - detailed movements with running balance
- `calcular_detalle_acumulado(session, cuenta_id, fecha_inicio, fecha_fin)` → `Dict` - range audit with aggregates (saldo_inicial, detalle, saldo_final)
- `obtener_gastos_top(session, cuenta_id, meses, limite)` → top expenses analysis

These handle complex logic: recurring expenses (FixedExpense with frequency calculations via `dateutil.relativedelta`), one-time transactions, adjustments, and proper date range filtering. **Pass the same session instance** - don't open new sessions mid-calculation.

## Development Patterns

### Database Session Management
```python
session = db.session()
try:
    # All queries/commits here
    session.commit()
except Exception:
    session.rollback()
finally:
    session.close()
```
**CRITICAL**: Pass the same session to reconciler functions - don't open new sessions mid-calculation.

### Transferencias entre cuentas
Transaction y FixedExpense tienen un campo `es_transferencia` (Integer: 0/1) para marcar movimientos que son transferencias entre cuentas:
- **No afecta la lógica de reconciler**: Los balances se calculan igual (las transferencias ya están con sus signos +/-)
- **Uso en UI**: Checkbox "Es transferencia entre cuentas" en los diálogos de edición
- **Filtrado opcional**: Puedes filtrar por `es_transferencia=0` para análisis de gastos/ingresos reales excluyendo transferencias
- Las transferencias creadas al "fijar periodos" de gastos recurrentes heredan este campo

### Recurring Expense Frequency
FixedExpense model supports: `semanal`, `mensual`, `trimestral`, `semestral`, `anual`. Use `dateutil.relativedelta` for month-based frequencies:
```python
from dateutil.relativedelta import relativedelta
if freq == 'mensual':
    next_date += relativedelta(months=1)
```
Date filtering: Check both `fecha_inicio` and `fecha_fin` (nullable) to determine if expense is active in a date range.

### Decimal Precision
Always convert to Decimal for financial calculations:
```python
from decimal import Decimal
saldo = Decimal(str(cuenta.saldo_inicial or 0))
```
Return `float` only for UI/charts. HoldingPurchase uses DECIMAL(24,8) for crypto/stock precision.

### UI Widget Pattern
PySide6 dialogs follow this structure (see [ui/admin_ui.py](ui/admin_ui.py)):
- Inherit from QDialog
- Use QFormLayout for form fields (QLineEdit, QDateEdit, QDoubleSpinBox)
- QDialogButtonBox with accepted/rejected signals
- Refresh parent table after modal closes: `self.refresh()`

### PyInstaller Distribution
**Critical bootstrap logic** in [main.py](main.py#L1-L60):
- Detects `sys.frozen` for bundled mode (checks `sys._MEIPASS` for --onefile, `sys.executable` for --onedir)
- Sets working directory to exe location via `os.chdir(base_dir)`
- Configures QT_QPA_PLATFORM_PLUGIN_PATH for PySide6 plugins (tries `PySide6/plugins/platforms` then `platforms`)
- Loads `.env` from dist folder using `dotenv.load_dotenv(os.path.join(base_dir, ".env"))`
- Adds base_dir and PySide6 subdirs to PATH on Windows

Build command:
```powershell
pyinstaller finanzas_desktop.spec
```
The `.spec` file includes `.env` in datas: `datas=[('.env', '.')]`

## Testing & Debugging

### Manual Test Scripts
- [test_calculo_cuenta.py](test_calculo_cuenta.py) - demonstrates reconciler usage pattern with `calcular_detalle_cuenta()`
- [audit_by_date.py](audit_by_date.py) - CLI tool for date-range auditing: `python audit_by_date.py --cuenta 2 --desde 2025-01-01 --hasta 2025-12-31`

Example test pattern:
```python
session = db.session()
movimientos, saldo = calcular_detalle_cuenta(session, cuenta_id, fecha)
for m in movimientos:
    print(f"{m['fecha']} {m['tipo']} {m['descripcion']} {m['monto']:.2f} → {m['saldo']:.2f}")
```

### DB Configuration Dialog
App launches without DATABASE_URL - shows ConfigDialog (see [main.py](main.py#L233-L298)). 
- Uses `db.check_connection(url, timeout=5)` to validate before persisting
- Saves to `.env` with `python-dotenv.set_key()`
- Creates temporary engine to test connection without altering main `db.engine`
- After successful config, app reinitializes with `db.init_app(new_url)`

## Key Integration Points

### Stock Market Data
- Use `yfinance` for ticker prices (see [models/holding.py](models/holding.py) and [utils/market_holdings.py](utils/market_holdings.py))
- `update_price_for_holding(session, holding)` - updates `last_price` and `last_update` fields (calls `fetch_price_yfinance_float()`)
- Holdings track purchases with DECIMAL(24,8) precision for crypto/stocks
- Price caching via `get_cached_price(session, ticker, refresh=False)` stores in PriceSnapshot table
- Ticker format supports exchange suffixes: `'SAN.MC'`, `'BBVA.MC'`, `'AAPL'`
- HoldingPurchase model includes `comisiones` (commissions) field for transaction costs

### Mortgage Amortization
- Mortgage model has `capital_inicial`, `cuotas_totales`, `tipo` (fijo/variable)
- MortgagePeriod tracks per-period interest/principal/balance with columns: `numero_cuota`, `fecha`, `interes`, `principal`, `saldo_restante`
- DashboardWidget renders amortization charts in 2x2 grid layout
- Calculate amortization: iterate cuotas, apply interest rate, track remaining balance

### Chart Rendering
Matplotlib embedded via `FigureCanvasQTAgg` (see [ui/dashboard_widget.py](ui/dashboard_widget.py)):
```python
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
self.figure = Figure(figsize=(6, 4))
self.canvas = FigureCanvas(self.figure)
self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
```
Clear and redraw: `self.figure.clear()` then `self.canvas.draw()`
DashboardWidget uses QGridLayout with 4 canvases: balance bars, loan amortization, top expenses, investments

## Common Pitfalls

1. **Don't create duplicate balance calculation logic** - always import from reconciler.py
2. **FixedExpense date ranges**: Check both `fecha_inicio` and `fecha_fin` (nullable)
3. **Session lifecycle**: Close sessions in finally blocks to avoid connection leaks
4. **PyInstaller paths**: Use `base_dir` from bootstrap for resource files, not `__file__`
5. **Qt plugin issues**: If "platform plugin not found" error, verify PATH modifications in main.py lines 25-50

## File Reference
- Account balance logic: [utils/reconciler.py](utils/reconciler.py)
- Main UI: [main.py](main.py)
- CRUD operations: [ui/admin_ui.py](ui/admin_ui.py)
- DB setup: [database/__init__.py](database/__init__.py)
- Models: [models/](models/)
- Dashboard: [ui/dashboard_widget.py](ui/dashboard_widget.py)
