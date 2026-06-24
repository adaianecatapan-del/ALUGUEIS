import sqlite3
from datetime import date, timedelta
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alugueis.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS imoveis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endereco TEXT NOT NULL,
        complemento TEXT,
        bairro TEXT,
        cidade TEXT,
        descricao TEXT,
        created_at TEXT DEFAULT (date('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inquilinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cpf TEXT,
        telefone TEXT,
        email TEXT,
        imovel_id INTEGER REFERENCES imoveis(id),
        data_inicio TEXT,
        data_fim TEXT,
        aluguel REAL DEFAULT 0,
        taxa_pintura REAL DEFAULT 0,
        iptu REAL DEFAULT 0,
        taxa_lixo REAL DEFAULT 0,
        dia_vencimento INTEGER DEFAULT 5,
        ativo INTEGER DEFAULT 1,
        observacao TEXT,
        created_at TEXT DEFAULT (date('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquilino_id INTEGER NOT NULL REFERENCES inquilinos(id),
        mes_referencia TEXT NOT NULL,
        aluguel REAL DEFAULT 0,
        taxa_pintura REAL DEFAULT 0,
        iptu REAL DEFAULT 0,
        taxa_lixo REAL DEFAULT 0,
        total REAL DEFAULT 0,
        data_vencimento TEXT,
        data_pagamento TEXT,
        status TEXT DEFAULT 'pendente',
        observacao TEXT,
        created_at TEXT DEFAULT (date('now'))
    )''')

    conn.commit()
    conn.close()


def migrate_db():
    conn = get_db()
    for col, defn in [
        ('iptu_tipo', "TEXT DEFAULT 'mensal'"),
        ('iptu_mes', 'INTEGER DEFAULT 1'),
        ('taxa_lixo_tipo', "TEXT DEFAULT 'mensal'"),
        ('taxa_lixo_mes', 'INTEGER DEFAULT 1'),
        ('iptu_n_parcelas', 'INTEGER DEFAULT 12'),
        ('taxa_lixo_n_parcelas', 'INTEGER DEFAULT 12'),
        ('contrato_arquivo', 'TEXT'),
        ('data_ultimo_reajuste', 'TEXT'),
        ('gas', 'REAL DEFAULT 0'),
        ('gas_n_parcelas', 'INTEGER DEFAULT 12'),
        ('gas_mes', 'INTEGER DEFAULT 1'),
        ('internet', 'REAL DEFAULT 0'),
        ('internet_n_parcelas', 'INTEGER DEFAULT 12'),
        ('internet_mes', 'INTEGER DEFAULT 1'),
        ('taxa_agua', 'REAL DEFAULT 0'),
        ('taxa_agua_n_parcelas', 'INTEGER DEFAULT 12'),
        ('taxa_agua_mes', 'INTEGER DEFAULT 1'),
        ('taxa_administracao', 'REAL DEFAULT 0'),
        ('taxa_administracao_n_parcelas', 'INTEGER DEFAULT 12'),
        ('taxa_administracao_mes', 'INTEGER DEFAULT 1'),
        ('taxa_administracao_pct', 'REAL DEFAULT 0'),
        ('taxa_administracao_valor_fixo', 'REAL DEFAULT 0'),
    ]:
        try:
            conn.execute(f'ALTER TABLE inquilinos ADD COLUMN {col} {defn}')
        except Exception:
            pass
    for col, defn in [
        ('iptu_parcela', 'TEXT'),
        ('lixo_parcela', 'TEXT'),
        ('forma_pagamento', 'TEXT'),
        ('gas', 'REAL DEFAULT 0'),
        ('gas_parcela', 'TEXT'),
        ('internet', 'REAL DEFAULT 0'),
        ('internet_parcela', 'TEXT'),
        ('taxa_agua', 'REAL DEFAULT 0'),
        ('taxa_agua_parcela', 'TEXT'),
        ('taxa_administracao', 'REAL DEFAULT 0'),
        ('taxa_administracao_parcela', 'TEXT'),
        ('valor_liquido', 'REAL'),
        ('desconto_administracao', 'REAL DEFAULT 0'),
    ]:
        try:
            conn.execute(f'ALTER TABLE pagamentos ADD COLUMN {col} {defn}')
        except Exception:
            pass
    conn.commit()
    conn.close()


def atualizar_status_pagamentos():
    """Marca como atrasado pagamentos vencidos e não pagos."""
    conn = get_db()
    hoje = date.today().isoformat()
    conn.execute(
        "UPDATE pagamentos SET status='atrasado' WHERE status='pendente' AND data_vencimento < ?",
        (hoje,)
    )
    conn.commit()
    conn.close()
