from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import get_db, init_db, atualizar_status_pagamentos
from datetime import date, datetime
import calendar

app = Flask(__name__)
app.secret_key = 'alugueis-secret-2024'


@app.context_processor
def inject_globals():
    return {'hoje': date.today().isoformat(), 'ano_atual': date.today().year}


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

    conn.close()
    return render_template('index.html',
        total_imoveis=total_imoveis,
        total_inquilinos=total_inquilinos,
        pendentes=pendentes,
        valor_pendente=valor_pendente,
        alertas=alertas,
        atrasados=atrasados,
        ultimos_pagos=ultimos_pagos
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
        conn.execute('''
            INSERT INTO inquilinos
            (nome, cpf, telefone, email, imovel_id, data_inicio, data_fim,
             aluguel, taxa_pintura, iptu, taxa_lixo, dia_vencimento, observacao)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            request.form['nome'], request.form.get('cpf'), request.form.get('telefone'),
            request.form.get('email'), request.form.get('imovel_id') or None,
            request.form.get('data_inicio'), request.form.get('data_fim'),
            float(request.form.get('aluguel') or 0),
            float(request.form.get('taxa_pintura') or 0),
            float(request.form.get('iptu') or 0),
            float(request.form.get('taxa_lixo') or 0),
            int(request.form.get('dia_vencimento') or 5),
            request.form.get('observacao')
        ))
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
        conn.execute('''
            UPDATE inquilinos SET nome=?, cpf=?, telefone=?, email=?, imovel_id=?,
            data_inicio=?, data_fim=?, aluguel=?, taxa_pintura=?, iptu=?, taxa_lixo=?,
            dia_vencimento=?, ativo=?, observacao=? WHERE id=?
        ''', (
            request.form['nome'], request.form.get('cpf'), request.form.get('telefone'),
            request.form.get('email'), request.form.get('imovel_id') or None,
            request.form.get('data_inicio'), request.form.get('data_fim'),
            float(request.form.get('aluguel') or 0),
            float(request.form.get('taxa_pintura') or 0),
            float(request.form.get('iptu') or 0),
            float(request.form.get('taxa_lixo') or 0),
            int(request.form.get('dia_vencimento') or 5),
            1 if request.form.get('ativo') else 0,
            request.form.get('observacao'), id
        ))
        conn.commit()
        conn.close()
        flash('Inquilino atualizado!', 'success')
        return redirect(url_for('inquilinos'))
    conn.close()
    return render_template('inquilino_form.html', inquilino=inquilino, imoveis=imoveis)


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
    query += ' ORDER BY p.data_vencimento DESC'

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
                total = (inq['aluguel'] + inq['taxa_pintura'] +
                         inq['iptu'] + inq['taxa_lixo'])
                status = 'atrasado' if data_venc < date.today().isoformat() else 'pendente'
                conn.execute('''
                    INSERT INTO pagamentos
                    (inquilino_id, mes_referencia, aluguel, taxa_pintura, iptu, taxa_lixo,
                     total, data_vencimento, status)
                    VALUES (?,?,?,?,?,?,?,?,?)
                ''', (iid, mes_ref, inq['aluguel'], inq['taxa_pintura'],
                      inq['iptu'], inq['taxa_lixo'], total, data_venc, status))
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
        iptu = float(request.form.get('iptu') or 0)
        taxa_lixo = float(request.form.get('taxa_lixo') or 0)
        total = aluguel + taxa_pintura + iptu + taxa_lixo
        data_venc = request.form.get('data_vencimento')
        status = 'atrasado' if data_venc and data_venc < date.today().isoformat() else 'pendente'
        conn.execute('''
            INSERT INTO pagamentos
            (inquilino_id, mes_referencia, aluguel, taxa_pintura, iptu, taxa_lixo,
             total, data_vencimento, status, observacao)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', (
            request.form['inquilino_id'], request.form['mes_referencia'],
            aluguel, taxa_pintura, iptu, taxa_lixo, total, data_venc,
            status, request.form.get('observacao')
        ))
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
    conn = get_db()
    conn.execute(
        "UPDATE pagamentos SET status='pago', data_pagamento=? WHERE id=?",
        (data_pag, id)
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
        iptu = float(request.form.get('iptu') or 0)
        taxa_lixo = float(request.form.get('taxa_lixo') or 0)
        total = aluguel + taxa_pintura + iptu + taxa_lixo
        data_pag = request.form.get('data_pagamento') or None
        status = request.form.get('status', 'pendente')
        conn.execute('''
            UPDATE pagamentos SET inquilino_id=?, mes_referencia=?, aluguel=?,
            taxa_pintura=?, iptu=?, taxa_lixo=?, total=?, data_vencimento=?,
            data_pagamento=?, status=?, observacao=? WHERE id=?
        ''', (
            request.form['inquilino_id'], request.form['mes_referencia'],
            aluguel, taxa_pintura, iptu, taxa_lixo, total,
            request.form.get('data_vencimento'), data_pag, status,
            request.form.get('observacao'), id
        ))
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
