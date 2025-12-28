# database/__init__.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

load_dotenv()

# Declarative base disponible desde la importación para evitar problemas
Base = declarative_base()

class _DB:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.url = None
        self.echo = False
        self._initialized = False
        self.connected = False

    def init_app(self, db_url: str | None = None, echo: bool | None = None, **engine_kwargs):
        """
        Inicializa engine y SessionLocal. Si no hay DATABASE_URL no lanza excepción:
        deja la configuración en un estado no inicializado para que la UI pueda
        abrir el diálogo de configuración.
        """
        if db_url is None:
            db_url = os.environ.get("DATABASE_URL")

        if echo is None:
            echo_env = os.environ.get("DB_ECHO", "False")
            echo = echo_env.lower() in ("1", "true", "yes")

        if not db_url:
            # No hay URL: dejamos todo a None pero la app puede seguir funcionando
            self.engine = None
            self.SessionLocal = None
            self.url = None
            self.echo = echo
            self._initialized = True
            self.connected = False
            return

        # Si ya estaba inicializado con la misma URL, no la recreamos
        if self.url == db_url and self.engine is not None:
            self.echo = echo
            self._initialized = True
            return

        # Creamos engine (no intentamos conectar hasta que se haga check_connection)
        self.url = db_url
        self.echo = echo
        # pool_pre_ping ayuda a reconectar conexiones muertas
        self.engine = create_engine(db_url, echo=echo, future=True, pool_pre_ping=True, **engine_kwargs)
        self.SessionLocal = scoped_session(sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False))
        self._initialized = True
        # no asumimos connected hasta que check_connection lo confirme
        self.connected = False

    def session(self):
        if self.SessionLocal is None:
            raise RuntimeError("DB no inicializado. Llama a db.init_app() primero o configura DATABASE_URL.")
        return self.SessionLocal()

    def create_all(self):
        if self.engine is None:
            raise RuntimeError("DB no inicializado. Llama a db.init_app() primero.")
        Base.metadata.create_all(bind=self.engine)

    def check_connection(self, db_url: str | None = None, timeout_seconds: int = 5) -> tuple[bool, str | None]:
        """
        Intenta conectar con la URL (si se pasa) o con self.url.
        Devuelve (True, None) o (False, mensaje_error).
        """
        url = db_url or self.url
        if url is None:
            return False, "No hay DATABASE_URL definida."

        # Crear un engine temporal para probar la conexión sin alterar self.engine
        from sqlalchemy import create_engine, text
        try:
            engine = create_engine(url, future=True, connect_args={"connect_timeout": timeout_seconds})
            with engine.connect() as conn:
                # ejecutar una consulta mínima usando text() para SQLAlchemy 2.0
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return True, None
        except Exception as exc:
            # devolver el mensaje para mostrar en UI (no incluimos credenciales extra)
            return False, str(exc)

    def close_all(self):
        """
        Cierra sesiones y engine (útil para reconfigurar).
        """
        try:
            if self.SessionLocal:
                self.SessionLocal.remove()
        except Exception:
            pass
        try:
            if self.engine:
                self.engine.dispose()
        except Exception:
            pass
        self.engine = None
        self.SessionLocal = None
        self.url = None
        self._initialized = False
        self.connected = False

# exportados por el paquete
db = _DB()
# para compatibilidad con el código anterior que usaba db.Base
db.Base = Base
