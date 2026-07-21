# Guia de Deploy no PythonAnywhere

## Passo 1: Clonar o repositório no PythonAnywhere

1. Acesse https://www.pythonanywhere.com/
2. Faça login na sua conta
3. Vá para **Consoles** → **Bash**
4. Execute os comandos:

```bash
cd /home/adaianecatapan
git clone https://github.com/adaianecatapan-del/ALUGUEIS.git
cd ALUGUEIS
pip install -r requirements.txt
```

## Passo 2: Configurar a Web App

1. Vá para **Web** no menu lateral
2. Clique em **Add a new web app**
3. Escolha **Manual configuration**
4. Selecione **Python 3.10** (ou a versão mais recente disponível)

## Passo 3: Configurar o WSGI

1. Na página da Web App, localize **WSGI configuration file**
2. Clique no arquivo (algo como `/var/www/adaianecatapan_pythonanywhere_com_wsgi.py`)
3. Substitua o conteúdo pelo seguinte:

```python
import sys
import os

# Adicione o caminho do projeto
path = '/home/adaianecatapan/ALUGUEIS'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

## Passo 4: Configurar variáveis estáticas

1. Na página da Web App, procure por **Static files**
2. Configure:
   - URL: `/static/`
   - Directory: `/home/adaianecatapan/ALUGUEIS/static`

(Se não tiver pasta static, pode deixar como está)

## Passo 5: Recarregar a aplicação

1. Na página da Web App, clique em **Reload** (botão verde no topo)
2. Aguarde alguns segundos

## Passo 6: Verificar banco de dados

1. No Bash console, navegue até o diretório:
```bash
cd /home/adaianecatapan/ALUGUEIS
python -c "from database import init_db, migrate_db; init_db(); migrate_db(); print('Banco de dados inicializado!')"
```

## Passo 7: Atualizações futuras

Para atualizar o código após fazer commits no GitHub:

```bash
cd /home/adaianecatapan/ALUGUEIS
git pull origin main
pip install -r requirements.txt  # se houver novas dependências
```

Depois recarregue a web app no painel do PythonAnywhere.

## Acessar a aplicação

Sua aplicação estará disponível em:
- https://adaianecatapan.pythonanywhere.com/

## Relatório Mensal

O relatório de pagamentos estará disponível em:
- https://adaianecatapan.pythonanywhere.com/relatorios/mensal
- https://adaianecatapan.pythonanywhere.com/relatorios/mensal?mes=2026-06

## Troubleshooting

Se houver erro 500, verifique o arquivo de log:
- Vá para **Web** → **Log files** → **Error log**

Para ver logs detalhados, execute no Bash:
```bash
cd /home/adaianecatapan/ALUGUEIS
python app.py
```

## Suporte

Para mais informações, consulte a documentação do PythonAnywhere:
https://www.pythonanywhere.com/help/
