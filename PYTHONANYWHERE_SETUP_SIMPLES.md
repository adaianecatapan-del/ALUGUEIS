# Setup PythonAnywhere - Passo a Passo Simples

## 📋 Checklist

- [ ] Acessar https://www.pythonanywhere.com/
- [ ] Login na conta adaianecatapan
- [ ] Abrir Bash Console
- [ ] Clonar projeto
- [ ] Criar Web App
- [ ] Configurar WSGI
- [ ] Recarregar app

---

## 1️⃣ Abrir Bash Console

1. Clique em **Consoles** (menu lateral esquerdo)
2. Clique em **Bash** (verde)
3. Aguarde abrir o terminal

---

## 2️⃣ Clonar o Projeto

Cole estes comandos no terminal (um de cada vez, pressione Enter):

```bash
cd ~
git clone https://github.com/adaianecatapan-del/ALUGUEIS.git
cd ALUGUEIS
pip install flask
```

Aguarde terminar completamente.

---

## 3️⃣ Criar Web App

1. Clique em **Web** (menu lateral)
2. Clique em **Add a new web app**
3. Escolha **Manual configuration**
4. Selecione **Python 3.10** ou **3.11**
5. Aguarde a página recarregar

---

## 4️⃣ Configurar o Arquivo WSGI

Na página da Web App (ainda em **Web**):

1. Procure por **WSGI configuration file**
2. Você verá algo como: `/var/www/adaianecatapan_pythonanywhere_com_wsgi.py`
3. **Clique no arquivo** (é um link azul)
4. Apague **TUDO** e copie isto:

```python
import sys
import os

path = os.path.expanduser('~/ALUGUEIS')
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

5. Clique em **Save** (Ctrl+S)

---

## 5️⃣ Recarregar a App

De volta na página **Web**:

1. Procure por um botão **Reload** (verde, no topo)
2. Clique nele
3. Aguarde 10 segundos
4. Pronto!

---

## 6️⃣ Testar

Acesse uma destas URLs:

- https://adaianecatapan.pythonanywhere.com/
- https://adaianecatapan.pythonanywhere.com/relatorios/mensal
- https://adaianecatapan.pythonanywhere.com/relatorios/mensal/json

---

## ❌ Se não funcionar

### Ver o erro

Na página **Web** → **Log files** → **Error log**

Procure por mensagens de erro em vermelho.

### Erro comum: módulo não encontrado

Se vir `ModuleNotFoundError: No module named...`, execute no Bash:

```bash
cd ~/ALUGUEIS
pip install -r requirements.txt
```

### Erro: banco de dados

Se vir erro sobre banco de dados, execute:

```bash
cd ~/ALUGUEIS
python -c "from database import init_db, migrate_db; init_db(); migrate_db(); print('OK')"
```

---

## 🔄 Atualizar depois

Se fizer mudanças no GitHub, no Bash execute:

```bash
cd ~/ALUGUEIS
git pull origin main
```

Depois clique em **Reload** na página Web App novamente.

---

## 📞 Suporte

Se ainda não funcionar, me mostre:

1. A URL exata que você está tentando
2. O erro que aparece
3. Conteúdo do **Error log** (Web → Log files → Error log)
