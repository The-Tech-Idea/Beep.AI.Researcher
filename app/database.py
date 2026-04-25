"""Database — SQLAlchemy init. Uses config_manager paths."""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from app.config_manager import config_manager


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base, session_options={"expire_on_commit": False})


def init_db(app):
    db.init_app(app)


def get_db_uri(provider, **kwargs):
    """Construct DB URI. SQLite uses config_manager.db_path."""
    if provider == 'sqlite':
        path = kwargs.get('path')
        if not path:
            path = str(config_manager.db_path)
        elif not str(path).startswith('/') and ':\\' not in str(path):
            path = str(config_manager.base_path / path)
        return f"sqlite:///{path.replace(chr(92), '/')}"
    elif provider == 'postgresql':
        u, p = kwargs.get('user'), kwargs.get('password')
        h, pt = kwargs.get('host', 'localhost'), kwargs.get('port', 5432)
        dbn = kwargs.get('dbname')
        ssl = kwargs.get('sslmode', '')
        uri = f"postgresql://{u}:{p}@{h}:{pt}/{dbn}"
        return uri + f"?sslmode={ssl}" if ssl else uri
    elif provider == 'mysql':
        u, p = kwargs.get('user'), kwargs.get('password')
        h, pt = kwargs.get('host', 'localhost'), kwargs.get('port', 3306)
        dbn = kwargs.get('dbname')
        return f"mysql+pymysql://{u}:{p}@{h}:{pt}/{dbn}"
    elif provider == 'sqlserver':
        u, p = kwargs.get('user'), kwargs.get('password')
        h, pt = kwargs.get('host'), kwargs.get('port', 1433)
        dbn = kwargs.get('dbname')
        driver = kwargs.get('driver', 'ODBC Driver 17 for SQL Server')
        import urllib.parse
        enc = urllib.parse.quote_plus(driver)
        return f"mssql+pyodbc://{u}:{p}@{h}:{pt}/{dbn}?driver={enc}"
    elif provider == 'cosmosdb':
        u, p = kwargs.get('user'), kwargs.get('password')
        h, pt = kwargs.get('host'), kwargs.get('port', 5432)
        dbn = kwargs.get('dbname', 'citus')
        return f"postgresql://{u}:{p}@{h}:{pt}/{dbn}?sslmode=require"
    return None
