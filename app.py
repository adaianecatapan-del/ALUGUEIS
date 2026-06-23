from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from database import get_db, init_db, migrate_db, atualizar_status_pagamentos
from datetime import date, datetime, timedelta
import calendar
import os
import json
import urllib.request

app = Flask(__name__)
app.secret_key = 'alugueis-secret-2024'

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.context_processor
def inject_globals():
    return {'hoje': date.today().isoformat(), 'ano_atual': date.today().year}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

# Encargos que seguem o padrão "valor total + nº de parcelas + mês de início"
ENCARGOS = ['iptu', 'taxa_lixo', 'gas', 'internet', 'taxa_agua', 'taxa_administracao']
PARCELA_COL = {
    'iptu': 'iptu_parcela',
    'taxa_lixo': 'lixo_parcela',
    'gas': 'gas_parcela',
    'internet': 'internet_parcela',
    'taxa_agua': 'taxa_agua_parcela',
    'taxa_administracao': 'taxa_administracao_parcela',
}


def _get_parcela(valor_total, n_parcelas, mes_inicio, mes_atual):
    """Retorna (valor_parcela, num, total) se mes_atual é mês de parcela, senão None."""
    if not valor_total or valor_total <= 0:
        return None
    n = n_parcelas or 12
    mi = mes_inicio or 1
    offset = (mes_atual - mi) % 12
    if offset < n:
        return (round(valor_total / n, 2), offset + 1, n)
    return None


def _encargo_cols():
    """Nomes das colunas (valor, parcelas, mês) de todos os encargos, para inquilinos."""
    cols = []
    for e in ENCARGOS:
        cols += [e, f'{e}_n_parcelas', f'{e}_mes']
    return cols


def _encargo_form_values():
    """Lê do formulário os valores de cada encargo, na mesma ordem de _encargo_cols()."""
    vals = []
    for e in ENCARGOS:
        vals.append(float(request.form.get(e) or 0))
        vals.append(int(request.form.get(f'{e}_n_parcelas') or 12))
        vals.append(int(request.form.get(f'{e}_mes') or 1))
    return vals


# ─── HELPER PINTURA ───────────────────────────────────────────────────────────

def _criar_pintura_payments(conn, inq_id, taxa_pintura, data_inicio, data_fim):
    if not taxa_pintura or taxa_pintura <= 0:
        return
    hoje = date.today().isoformat()
    metade = round(taxa_pintura / 2, 2)
    for data, obs in [(data_inicio, 'pintura-inicio'), (data_fim, 'pintura-fim')]:
        if not data:
            continue
        existe = conn.execute(
            "SELECT id FROM pagamentos WHERE inquilino_id=? AND observacao=?",
            (inq_id, obs)
        ).fetchone()
        if not existe:
            status = 'atrasado' if data < hoje else 'pendente'
            conn.execute('''
                INSERT INTO pagamentos
                (inquilino_id, mes_referencia, taxa_pintura, total,
                 data_vencimento, status, observacao)
                VALUES (?,?,?,?,?,?,?)
            ''', (inq_id, data[:7], metade, metade, data, status, obs))


def _salvar_contrato(inq_id):
    file = request.files.get('contrato_arquivo')
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1]
        filename = secure_filename(f"contrato_{inq_id}{ext}")
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return filename
    return None


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    atualizar_status_pagamentos()
    conn = get_db()
    total_imoveis = conn.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0]
    total_inquilinos = conn.execute("SELECT COUNT(*) FROM inquilinos WHERE ativo=1").fetchone()[0]
    pendentes = conn.execute(
        "SELECT COUNT(*) FROM pagamentos WHERE status IN ('pendente','atrasado')"
    ).fetchone()[0]
    valor_pendente = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM pagamentos WHERE status IN ('pendente','atrasado')"
    ).fetchone()[0]

    hoje = date.today()
    em_7_dias = (hoje.replace(day=hoje.day + 7) if hoje.day <= 24
                 else date(hoje.year if hoje.month < 12 else hoje.year + 1,
                           hoje.month + 1 if hoje.month < 12 else 1, 7)).isoformat()

    alertas = conn.execute('''
        SELECT p.*, i.nome, im.endereco
        FROM pagamentos p
        JOIN inquilinos i ON p.inquilino_id = i.id
        JOIN imoveis im ON i.imovel_id = im.id
        WHERE p.status = 'pendente' AND p.data_vencimento <= ?
        ORDER BY p.data_vencimento
    ''', (em_7_dias,)).fetchall()

    atrasados = conn.execute('''
        SELECT p.*, i.nome, im.endereco
        FROM pagamentos p
        JOIN inquilinos i ON p.inquilino_id = i.id
        JOIN imoveis im ON i.imovel_id = im.id
        WHERE p.status = 'atrasado'
        ORDER BY p.data_vencimento
    ''').fetchall()

    ultimos_pagos = conn.execute('''
        SELECT p.*, i.nome
        FROM pagamentos p
        JOIN inquilinos i ON p.inquilino_id = i.id
        WHERE p.status = 'pago'
        ORDER BY p.data_pagamento DESC
        LIMIT 5
    ''').fetchall()

    em_60_dias = (hoje + timedelta(days=60)).isoformat()
    contratos_vencendo = conn.execute('''
        SELECT i.*, im.endereco
        FROM inquilinos i
        LEFT JOIN imoveis im ON i.imovel_id = im.id
        WHERE i.ativo = 1 AND i.data_fim IS NOT NULL AND i.data_fim != ''
              AND i.data_fim <= ?
        ORDER BY i.data_fim
    ''', (em_60_dias,)).fetchall()

    conn.close()
    return render_template('index.html',
        total_imoveis=total_imoveis,
        total_inquilinos=total_inquilinos,
        pendentes=pendentes,
        valor_pendente=valor_pendente,
        alertas=alertas,
        atrasados=atrasados,
        ultimos_pagos=ultimos_pagos,
        contratos_vencendo=contratos_vencendo
    )


# ─── IMÓVEIS ──────────────────────────────────────────────────────────────────

@app.route('/imoveis')
def imoveis():
    conn = get_db()
    lista = conn.execute('''
        SELECT im.*, COUNT(i.id) as total_inquilinos
        FROM imoveis im
        LEFT JOIN inquilinos i ON im.id = i.imovel_id AND i.ativo = 1
        GROUP BY im.id ORDER BY im.endereco
    ''').fetchall()
    conn.close()
    return render_template('imoveis.html', imoveis=lista)


@app.route('/imoveis/novo', methods=['GET', 'POST'])
def imovel_novo():
    if request.method == 'POST':
        conn = get_db()
        conn.execute(
            'INSERT INTO imoveis (endereco, complemento, bairro, cidade, descricao) VALUES (?,?,?,?,?)',
            (request.form['endereco'], request.form.get('complemento'),
             request.form.get('bairro'), request.form.get('cidade'),
             request.form.get('descricao'))
        )
        conn.commit()
        conn.close()
        flash('Imóvel cadastrado com sucesso!', 'success')
        return redirect(url_for('imoveis'))
    return render_template('imovel_form.html', imovel=None)


@app.route('/imoveis/<int:id>/editar', methods=['GET', 'POST'])
def imovel_editar(id):
    conn = get_db()
    imovel = conn.execute('SELECT * FROM imoveis WHERE id=?', (id,)).fetchone()
    if request.method == 'POST':
        conn.execute(
            'UPDATE imoveis SET endereco=?, complemento=?, bairro=?, cidade=?, descricao=? WHERE id=?',
            (request.form['endereco'], request.form.get('complemento'),
             request.form.get('bairro'), request.form.get('cidade'),
             request.form.get('descricao'), id)
        )
        conn.commit()
        conn.close()
        flash('Imóvel atualizado!', 'success')
        return redirect(url_for('imoveis'))
    conn.close()
    return render_template('imovel_form.html', imovel=imovel)


@app.route('/imoveis/<int:id>/excluir', methods=['POST'])
def imovel_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM imoveis WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Imóvel excluído.', 'warning')
    return redirect(url_for('imoveis'))


# ─── INQUILINOS ───────────────────────────────────────────────────────────────

@app.route('/inquilinos')
def inquilinos():
    conn = get_db()
    lista = conn.execute('''
        SELECT i.*, im.endereco as imovel_endereco
        FROM inquilinos i
        LEFT JOIN imoveis im ON i.imovel_id = im.id
        ORDER BY i.ativo DESC, i.nome
    ''').fetchall()
    conn.close()
    return render_template('inquilinos.html', inquilinos=lista)


@app.route('/inquilinos/novo', methods=['GET', 'POST'])
def inquilino_novo():
    conn = get_db()
    imoveis = conn.execute('SELECT * FROM imoveis ORDER BY endereco').fetchall()
    if request.method == 'POST':
        data_inicio = request.form.get('data_inicio') or None
        data_fim = request.form.get('data_fim') or None
        taxa_pintura = float(request.form.get('taxa_pintura') or 0)

        cols = (['nome', 'cpf', 'telefone', 'email', 'imovel_id', 'data_inicio', 'data_fim',
                  'aluguel', 'taxa_pintura', 'dia_vencimento'] +
                _encargo_cols() + ['data_ultimo_reajuste', 'observacao'])
        vals = ([request.form['nome'], request.form.get('cpf'), request.form.get('telefone'),
                  request.form.get('email'), request.form.get('imovel_id') or None,
                  data_inicio, data_fim,
                  float(request.form.get('aluguel') or 0), taxa_pintura,
                  int(request.form.get('dia_vencimento') or 5)] +
                _encargo_form_values() + [data_inicio, request.form.get('observacao')])
        placeholders = ','.join(['?'] * len(cols))
        cursor = conn.execute(
            f"INSERT INTO inquilinos ({','.join(cols)}) VALUES ({placeholders})", vals
        )
        inq_id = cursor.lastrowid
        contrato_arquivo = _salvar_contrato(inq_id)
        if contrato_arquivo:
            conn.execute('UPDATE inquilinos SET contrato_arquivo=? WHERE id=?', (contrato_arquivo, inq_id))
        _criar_pintura_payments(conn, inq_id, taxa_pintura, data_inicio, data_fim)
        conn.commit()
        conn.close()
        flash('Inquilino cadastrado com sucesso!', 'success')
        return redirect(url_for('inquilinos'))
    conn.close()
    return render_template('inquilino_form.html', inquilino=None, imoveis=imoveis)


@app.route('/inquilinos/<int:id>/editar', methods=['GET', 'POST'])
def inquilino_editar(id):
    conn = get_db()
    inquilino = conn.execute('SELECT * FROM inquilinos WHERE id=?', (id,)).fetchone()
    imoveis = conn.execute('SELECT * FROM imoveis ORDER BY endereco').fetchall()
    if request.method == 'POST':
        data_inicio = request.form.get('data_inicio') or None
        data_fim = request.form.get('data_fim') or None
        taxa_pintura = float(request.form.get('taxa_pintura') or 0)
        novo_aluguel = float(request.form.get('aluguel') or 0)
        data_ultimo_reajuste = inquilino['data_ultimo_reajuste'] or data_inicio
        if request.form.get('aplicar_reajuste') == '1':
            data_ultimo_reajuste = date.today().isoformat()

        cols = (['nome', 'cpf', 'telefone', 'email', 'imovel_id', 'data_inicio', 'data_fim',
                  'aluguel', 'taxa_pintura', 'dia_vencimento'] +
                _encargo_cols() + ['data_ultimo_reajuste', 'ativo', 'observacao'])
        vals = ([request.form['nome'], request.form.get('cpf'), request.form.get('telefone'),
                  request.form.get('email'), request.form.get('imovel_id') or None,
                  data_inicio, data_fim, novo_aluguel, taxa_pintura,
                  int(request.form.get('dia_vencimento') or 5)] +
                _encargo_form_values() +
                [data_ultimo_reajuste, 1 if request.form.get('ativo') else 0,
                 request.form.get('observacao')])
        set_clause = ', '.join(f'{c}=?' for c in cols)
        conn.execute(f"UPDATE inquilinos SET {set_clause} WHERE id=?", vals + [id])
        contrato_arquivo = _salvar_contrato(id)
        if contrato_arquivo:
            conn.execute('UPDATE inquilinos SET contrato_arquivo=? WHERE id=?', (contrato_arquivo, id))
        _criar_pintura_payments(conn, id, taxa_pintura, data_inicio, data_fim)
        conn.commit()
        conn.close()
        flash('Inquilino atualizado!', 'success')
        return redirect(url_for('inquilinos'))
    conn.close()
    return render_template('inquilino_form.html', inquilino=inquilino, imoveis=imoveis)


@app.route('/contratos/<filename>')
def contrato_download(filename):
    return send_from_directory(UPLOAD_FOLDER, secure_filename(filename))


@app.route('/inquilinos/<int:id>/excluir', methods=['POST'])
def inquilino_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM inquilinos WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Inquilino excluído.', 'warning')
    return redirect(url_for('inquilinos'))


# ─── PAGAMENTOS ───────────────────────────────────────────────────────────────

@app.route('/pagamentos')
def pagamentos():
    atualizar_status_pagamentos()
    filtro_inquilino = request.args.get('inquilino_id', '')
    filtro_mes = request.args.get('mes', '')
    filtro_status = request.args.get('status', '')

    query = '''
        SELECT p.*, i.nome, i.dia_vencimento, im.endereco
        FROM pagamentos p
        JOIN inquilinos i ON p.inquilino_id = i.id
        JOIN imoveis im ON i.imovel_id = im.id
        WHERE 1=1
    '''
    params = []
    if filtro_inquilino:
        query += ' AND p.inquilino_id = ?'
        params.append(filtro_inquilino)
    if filtro_mes:
        query += ' AND p.mes_referencia = ?'
        params.append(filtro_mes)
    if filtro_status:
        query += ' AND p.status = ?'
        params.append(filtro_status)
    query += '''
        ORDER BY
            CASE p.status WHEN 'atrasado' THEN 0 WHEN 'pendente' THEN 1 ELSE 2 END,
            p.data_vencimento
    '''

    conn = get_db()
    lista = conn.execute(query, params).fetchall()
    todos_inquilinos = conn.execute(
        'SELECT id, nome FROM inquilinos WHERE ativo=1 ORDER BY nome'
    ).fetchall()
    conn.close()
    return render_template('pagamentos.html',
        pagamentos=lista,
        inquilinos=todos_inquilinos,
        filtro_inquilino=filtro_inquilino,
        filtro_mes=filtro_mes,
        filtro_status=filtro_status
    )


@app.route('/pagamentos/gerar', methods=['GET', 'POST'])
def pagamento_gerar():
    conn = get_db()
    inquilinos_ativos = conn.execute(
        'SELECT * FROM inquilinos WHERE ativo=1 ORDER BY nome'
    ).fetchall()

    if request.method == 'POST':
        mes_ref = request.form['mes_referencia']
        inquilino_ids = request.form.getlist('inquilino_ids')
        ano, mes = map(int, mes_ref.split('-'))
        gerados = 0
        for iid in inquilino_ids:
            inq = conn.execute('SELECT * FROM inquilinos WHERE id=?', (iid,)).fetchone()
            existe = conn.execute(
                'SELECT id FROM pagamentos WHERE inquilino_id=? AND mes_referencia=?',
                (iid, mes_ref)
            ).fetchone()
            if not existe and inq:
                ultimo_dia = calendar.monthrange(ano, mes)[1]
                dia_venc = min(inq['dia_vencimento'], ultimo_dia)
                data_venc = f"{ano:04d}-{mes:02d}-{dia_venc:02d}"

                total = inq['aluguel'] or 0
                pag_cols = ['inquilino_id', 'mes_referencia', 'aluguel', 'taxa_pintura',
                            'data_vencimento']
                pag_vals = [iid, mes_ref, inq['aluguel'] or 0, 0, data_venc]
                for e in ENCARGOS:
                    info = _get_parcela(
                        inq[e] or 0, inq[f'{e}_n_parcelas'] or 12, inq[f'{e}_mes'] or 1, mes
                    )
                    val = info[0] if info else 0
                    parcela = f"{info[1]}/{info[2]}" if info else None
                    total += val
                    pag_cols += [e, PARCELA_COL[e]]
                    pag_vals += [val, parcela]

                status = 'atrasado' if data_venc < date.today().isoformat() else 'pendente'
                pag_cols += ['total', 'status']
                pag_vals += [total, status]
                placeholders = ','.join(['?'] * len(pag_cols))
                conn.execute(
                    f"INSERT INTO pagamentos ({','.join(pag_cols)}) VALUES ({placeholders})",
                    pag_vals
                )
                gerados += 1
        conn.commit()
        conn.close()
        flash(f'{gerados} pagamento(s) gerado(s) para {mes_ref}.', 'success')
        return redirect(url_for('pagamentos'))

    conn.close()
    mes_atual = date.today().strftime('%Y-%m')
    return render_template('pagamento_gerar.html',
        inquilinos=inquilinos_ativos, mes_atual=mes_atual)


@app.route('/pagamentos/novo', methods=['GET', 'POST'])
def pagamento_novo():
    conn = get_db()
    inquilinos_ativos = conn.execute(
        'SELECT i.*, im.endereco FROM inquilinos i LEFT JOIN imoveis im ON i.imovel_id=im.id WHERE i.ativo=1 ORDER BY i.nome'
    ).fetchall()
    if request.method == 'POST':
        aluguel = float(request.form.get('aluguel') or 0)
        taxa_pintura = float(request.form.get('taxa_pintura') or 0)
        encargos_vals = {e: float(request.form.get(e) or 0) for e in ENCARGOS}
        total = aluguel + taxa_pintura + sum(encargos_vals.values())
        data_venc = request.form.get('data_vencimento')
        status = 'atrasado' if data_venc and data_venc < date.today().isoformat() else 'pendente'

        cols = (['inquilino_id', 'mes_referencia', 'aluguel', 'taxa_pintura'] + ENCARGOS +
                ['total', 'data_vencimento', 'status', 'observacao', 'forma_pagamento'])
        vals = ([request.form['inquilino_id'], request.form['mes_referencia'],
                  aluguel, taxa_pintura] + [encargos_vals[e] for e in ENCARGOS] +
                [total, data_venc, status, request.form.get('observacao'),
                 request.form.get('forma_pagamento')])
        placeholders = ','.join(['?'] * len(cols))
        conn.execute(f"INSERT INTO pagamentos ({','.join(cols)}) VALUES ({placeholders})", vals)
        conn.commit()
        conn.close()
        flash('Pagamento lançado!', 'success')
        return redirect(url_for('pagamentos'))
    conn.close()
    return render_template('pagamento_form.html', pagamento=None,
                           inquilinos=inquilinos_ativos,
                           mes_atual=date.today().strftime('%Y-%m'))


@app.route('/pagamentos/<int:id>/pagar', methods=['POST'])
def pagamento_pagar(id):
    data_pag = request.form.get('data_pagamento') or date.today().isoformat()
    forma_pagamento = request.form.get('forma_pagamento') or None
    conn = get_db()
    conn.execute(
        "UPDATE pagamentos SET status='pago', data_pagamento=?, forma_pagamento=? WHERE id=?",
        (data_pag, forma_pagamento, id)
    )
    conn.commit()
    conn.close()
    flash('Pagamento registrado como PAGO!', 'success')
    return redirect(request.referrer or url_for('pagamentos'))


@app.route('/pagamentos/<int:id>/editar', methods=['GET', 'POST'])
def pagamento_editar(id):
    conn = get_db()
    pagamento = conn.execute('SELECT * FROM pagamentos WHERE id=?', (id,)).fetchone()
    inquilinos_ativos = conn.execute(
        'SELECT i.*, im.endereco FROM inquilinos i LEFT JOIN imoveis im ON i.imovel_id=im.id WHERE i.ativo=1 ORDER BY i.nome'
    ).fetchall()
    if request.method == 'POST':
        aluguel = float(request.form.get('aluguel') or 0)
        taxa_pintura = float(request.form.get('taxa_pintura') or 0)
        encargos_vals = {e: float(request.form.get(e) or 0) for e in ENCARGOS}
        total = aluguel + taxa_pintura + sum(encargos_vals.values())
        data_pag = request.form.get('data_pagamento') or None
        status = request.form.get('status', 'pendente')

        cols = (['inquilino_id', 'mes_referencia', 'aluguel', 'taxa_pintura'] + ENCARGOS +
                ['total', 'data_vencimento', 'data_pagamento', 'status', 'observacao',
                 'forma_pagamento'])
        vals = ([request.form['inquilino_id'], request.form['mes_referencia'],
                  aluguel, taxa_pintura] + [encargos_vals[e] for e in ENCARGOS] +
                [total, request.form.get('data_vencimento'), data_pag, status,
                 request.form.get('observacao'), request.form.get('forma_pagamento')])
        set_clause = ', '.join(f'{c}=?' for c in cols)
        conn.execute(f"UPDATE pagamentos SET {set_clause} WHERE id=?", vals + [id])
        conn.commit()
        conn.close()
        flash('Pagamento atualizado!', 'success')
        return redirect(url_for('pagamentos'))
    conn.close()
    return render_template('pagamento_form.html', pagamento=pagamento,
                           inquilinos=inquilinos_ativos,
                           mes_atual=date.today().strftime('%Y-%m'))


@app.route('/pagamentos/<int:id>/excluir', methods=['POST'])
def pagamento_excluir(id):
    conn = get_db()
    conn.execute('DELETE FROM pagamentos WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Pagamento excluído.', 'warning')
    return redirect(url_for('pagamentos'))


# ─── RELATÓRIOS ───────────────────────────────────────────────────────────────

@app.route('/relatorios')
def relatorios():
    ano = request.args.get('ano', date.today().year)
    conn = get_db()

    resumo_mensal = conn.execute('''
        SELECT mes_referencia,
               COUNT(*) as total,
               SUM(CASE WHEN status='pago' THEN 1 ELSE 0 END) as pagos,
               SUM(CASE WHEN status='atrasado' THEN 1 ELSE 0 END) as atrasados,
               SUM(CASE WHEN status='pendente' THEN 1 ELSE 0 END) as pendentes,
               SUM(total) as valor_total,
               SUM(CASE WHEN status='pago' THEN total ELSE 0 END) as valor_pago
        FROM pagamentos
        WHERE mes_referencia LIKE ?
        GROUP BY mes_referencia
        ORDER BY mes_referencia
    ''', (f'{ano}%',)).fetchall()

    inadimplentes = conn.execute('''
        SELECT i.nome, i.telefone, im.endereco,
               COUNT(p.id) as qtd_atraso,
               SUM(p.total) as valor_total
        FROM pagamentos p
        JOIN inquilinos i ON p.inquilino_id = i.id
        JOIN imoveis im ON i.imovel_id = im.id
        WHERE p.status = 'atrasado'
        GROUP BY i.id
        ORDER BY valor_total DESC
    ''').fetchall()

    anos_disponiveis = conn.execute(
        "SELECT DISTINCT substr(mes_referencia,1,4) as ano FROM pagamentos ORDER BY ano DESC"
    ).fetchall()

    conn.close()
    return render_template('relatorios.html',
        resumo_mensal=resumo_mensal,
        inadimplentes=inadimplentes,
        anos_disponiveis=[r['ano'] for r in anos_disponiveis],
        ano_selecionado=str(ano)
    )


# ─── API para preencher valores do inquilino ──────────────────────────────────

@app.route('/api/igpm')
def api_igpm():
    data_inicio_str = request.args.get('data_inicio')
    try:
        if data_inicio_str:
            d_ini = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        else:
            d_ini = date.today().replace(year=date.today().year - 1)
        d_fim = date.today()
        url = (
            'https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados'
            f"?formato=json&dataInicial={d_ini.strftime('%d/%m/%Y')}&dataFinal={d_fim.strftime('%d/%m/%Y')}"
        )
        with urllib.request.urlopen(url, timeout=10) as resp:
            dados = json.loads(resp.read().decode('utf-8'))
        if not dados:
            return jsonify({'ok': False, 'erro': 'Sem dados retornados para o período.'})
        acumulado = 1.0
        for item in dados:
            valor = float(str(item['valor']).replace(',', '.'))
            acumulado *= (1 + valor / 100)
        percentual = (acumulado - 1) * 100
        return jsonify({'ok': True, 'percentual': round(percentual, 2), 'meses': len(dados)})
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)})


@app.route('/api/inquilino/<int:id>')
def api_inquilino(id):
    conn = get_db()
    inq = conn.execute('SELECT * FROM inquilinos WHERE id=?', (id,)).fetchone()
    conn.close()
    if inq:
        return jsonify(dict(inq))
    return jsonify({}), 404


if __name__ == '__main__':
    init_db()
    migrate_db()
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n{'='*50}")
    print(f"  SISTEMA DE CONTROLE DE ALUGUEIS")
    print(f"{'='*50}")
    print(f"  Acesso no computador: http://localhost:5000")
    print(f"  Acesso no celular:    http://{local_ip}:5000")
    print(f"{'='*50}\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
