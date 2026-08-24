from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, session
import pandas as pd
import openpyxl
import xlwings as xw
import random
import string
import json
import sys
import os
import datetime
import calendar
import holidays
import uuid
import hashlib
import threading
import pythoncom  # Necessário para o xlwings funcionar em background

if getattr(sys, 'frozen', False):
    caminho_templates = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=caminho_templates)
else:
    app = Flask(__name__)

app.secret_key = "chave_super_secreta_para_sessao_2026"

# =========================================================
# BANCO DE DADOS EM JSON (Histórico e Máquinas)
# =========================================================
DB_MAQUINAS = "maquinas.json"
DB_HISTORICO = "historico.json"

def carregar_json(caminho):
    if not os.path.exists(caminho):
        return [] if caminho == DB_HISTORICO else {}
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_json(caminho, dados):
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def registrar_historico(codigo_pc, acao, detalhes):
    hist = carregar_json(DB_HISTORICO)
    agora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    hist.insert(0, {
        "data_hora": agora,
        "codigo_pc": codigo_pc,
        "acao": acao,
        "detalhes": detalhes
    })
    salvar_json(DB_HISTORICO, hist[:500])

# =========================================================
# SEGURANÇA: TRAVA POR MÁQUINA (HARDWARE ID)
# =========================================================
def obter_codigo_pc():
    mac = uuid.getnode()
    hash_mac = hashlib.md5(str(mac).encode()).hexdigest().upper()
    return hash_mac[:6]

def gerar_codigo_liberacao(codigo_pc):
    SEGREDO = "SISTEMA_PRODUTIVIDADE_2026_PRO"
    hash_lib = hashlib.sha256((codigo_pc + SEGREDO).encode()).hexdigest()
    numeros = ''.join(filter(str.isdigit, hash_lib)).ljust(6, '0')
    return numeros[:6]

codigo_pc_atual = obter_codigo_pc()
codigo_liberacao_correto = gerar_codigo_liberacao(codigo_pc_atual)

def carregar_senhas():
    try:
        with open("senhas.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"admin_senha": "admin"} 

# =========================================================
# ROTAS DO SISTEMA
# =========================================================

@app.route('/', methods=['GET'])
def home():
    return render_template('login.html', codigo_pc=codigo_pc_atual)

@app.route('/verificar', methods=['POST'])
def verificar():
    nome_usuario = request.form.get('nome_usuario')
    codigo_digitado = request.form.get('codigo_acesso')
    ip = request.remote_addr
    
    maquinas = carregar_json(DB_MAQUINAS)
    maq_info = maquinas.get(codigo_pc_atual)
    if maq_info and maq_info.get('status') == 'bloqueado':
        registrar_historico(codigo_pc_atual, "Acesso Negado", f"Tentativa de login de PC bloqueado via IP {ip}")
        return render_template('login.html', codigo_pc=codigo_pc_atual, erro="Este PC foi bloqueado pelo Administrador.")

    if codigo_digitado == codigo_liberacao_correto:
        session['autenticado'] = True
        session['codigo_pc'] = codigo_pc_atual
        session['nome_usuario'] = nome_usuario
        
        maquinas[codigo_pc_atual] = {
            "codigo_pc": codigo_pc_atual,
            "nome_usuario": nome_usuario,
            "status": "ativo",
            "ip_cadastrado": ip,
            "ultimo_acesso": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        salvar_json(DB_MAQUINAS, maquinas)
        
        detalhes = f"{nome_usuario} acessou o sistema pelo IP {ip}"
        registrar_historico(codigo_pc_atual, "Login", detalhes)
        
        return redirect(url_for('menu'))
    else:
        registrar_historico(codigo_pc_atual, "Acesso Negado", "Código de acesso inválido.")
        return render_template('login.html', codigo_pc=codigo_pc_atual, erro="Código Inválido! Peça liberação ao ADM.")

@app.route('/sair', methods=['GET'])
def sair():
    session.clear()
    registrar_historico(codigo_pc_atual, "Logout", "Saiu do sistema voluntariamente")
    return redirect(url_for('home'))

@app.route('/menu', methods=['GET'])
def menu():
    if not session.get('autenticado'): return redirect(url_for('home'))
    
    hist_geral = carregar_json(DB_HISTORICO)
    hist_pc = []
    for item in hist_geral:
        if item['codigo_pc'] == codigo_pc_atual:
            item_copia = item.copy()
            item_copia['data_hora'] = datetime.datetime.strptime(item['data_hora'], '%Y-%m-%d %H:%M:%S')
            hist_pc.append(item_copia)
            
    return render_template('menu.html', codigo_pc=codigo_pc_atual, historico=hist_pc)

@app.route('/painel', methods=['GET'])
def painel():
    if not session.get('autenticado'): return redirect(url_for('home'))
    return render_template('dashboard.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    erro = None
    codigo_gerado = None
    if request.method == 'POST':
        senha_digitada = request.form.get('senha_adm')
        codigo_cliente = request.form.get('codigo_cliente')
        
        senhas = carregar_senhas()
        if senha_digitada == senhas.get("admin_senha"):
            if codigo_cliente:
                codigo_gerado = gerar_codigo_liberacao(codigo_cliente.strip().upper())
            else:
                codigo_gerado = codigo_liberacao_correto
        else:
            erro = "Senha de Administrador incorreta!"
    return render_template('admin.html', erro=erro, codigo_gerado=codigo_gerado, codigo_pc_atual=codigo_pc_atual)

@app.route('/acesso_comando', methods=['GET', 'POST'])
def acesso_comando():
    if request.method == 'POST':
        senha_digitada = request.form.get('senha_adm')
        senhas = carregar_senhas()
        if senha_digitada == senhas.get("admin_senha"):
            session['is_admin'] = True
            return redirect(url_for('admin_painel'))
        else:
            return render_template('acesso_comando.html', erro="Senha Incorreta!")
    return render_template('acesso_comando.html')

@app.route('/admin_painel', methods=['GET'])
def admin_painel():
    if not session.get('is_admin'): return redirect(url_for('acesso_comando'))
    
    maquinas = list(carregar_json(DB_MAQUINAS).values())
    hist_raw = carregar_json(DB_HISTORICO)
    
    for m in maquinas:
        if m.get('ultimo_acesso'): m['ultimo_acesso'] = datetime.datetime.strptime(m['ultimo_acesso'], '%Y-%m-%d %H:%M:%S')
    
    hist_formatado = []
    for h in hist_raw:
        h_copy = h.copy()
        h_copy['data_hora'] = datetime.datetime.strptime(h['data_hora'], '%Y-%m-%d %H:%M:%S')
        hist_formatado.append(h_copy)
        
    return render_template('admin_painel.html', maquinas=maquinas, historico=hist_formatado)

@app.route('/admin/<acao>/<pc>', methods=['POST'])
def acao_maquina(acao, pc):
    if not session.get('is_admin'): return "Não autorizado", 403
    maquinas = carregar_json(DB_MAQUINAS)
    if pc in maquinas:
        if acao == 'bloquear': maquinas[pc]['status'] = 'bloqueado'
        elif acao == 'desbloquear': maquinas[pc]['status'] = 'ativo'
        salvar_json(DB_MAQUINAS, maquinas)
        registrar_historico(codigo_pc_atual, f"Ação ADM: PC {acao}", f"Status do PC {pc} alterado")
        return "OK", 200
    return "PC não encontrado", 404

# =========================================================
# MOTOR ASSÍNCRONO DE PROCESSAMENTO (BACKGROUND THREAD)
# =========================================================
tarefas = {} 

def executar_excel_background(task_id, pasta_atual, cam_listagem, cam_base, cam_soli, acao, mes_referencia, pc_req, agora_str):
    pythoncom.CoInitialize()
    
    try:
        tarefas[task_id] = {"progresso": 10, "status": "Lendo planilha de listagem...", "concluido": False}
        
        df_bruto = pd.read_excel(cam_listagem, header=None, skiprows=1, engine='openpyxl')
        df_bruto.dropna(how='all', inplace=True)

        tarefas[task_id] = {"progresso": 30, "status": "Limpando e formatando Base (Protegendo Fórmulas)...", "concluido": False}
        wb_base = openpyxl.load_workbook(cam_base, keep_vba=True)
        ws_bd = wb_base["BD"]
        
        # Mapeamento estrito recebido
        mapa_colunas = {
            1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9,
            11: 10, 12: 11, 13: 12, 14: 13, 15: 14, 16: 15, 17: 16, 18: 17, 19: 18, 20: 19,
            21: 20, 22: 21, 23: 22, 24: 23, 25: 24, 26: 25, 27: 26, 28: 27, 29: 28, 30: 29,
            31: 30, 32: 31, 33: 32, 34: 33, 35: 34, 36: 35
        }
        
        # Colunas totalmente blindadas na ABA BD: D(4), G(7), H(8) e AK(37)
        # AK(37) agora é a EQUIPE_FINAL (fórmula) - a coluna AJ(36) é a nova
        # "StatusRetorno" e deve ser preenchida normalmente com dados do relatório.
        colunas_protegidas_bd = [4, 7, 8, 37]

        colunas_alvo_excel = []
        for base_idx in mapa_colunas.values():
            col_excel = base_idx + 1 
            if col_excel in colunas_protegidas_bd: 
                continue 
            colunas_alvo_excel.append(col_excel)

        max_linhas_limpar = max(ws_bd.max_row, len(df_bruto) + 100)
        for r in range(2, max_linhas_limpar + 1):
            for c in colunas_alvo_excel:
                ws_bd.cell(row=r, column=c).value = None

        tarefas[task_id] = {"progresso": 45, "status": "Transferindo dados para a Base Excel...", "concluido": False}
        dados_lista = df_bruto.values.tolist()
        num_cols = df_bruto.shape[1]

        for r_idx, row_values in enumerate(dados_lista, start=2):
            for report_idx, base_idx in mapa_colunas.items():
                col_excel = base_idx + 1 
                if col_excel in colunas_protegidas_bd: 
                    continue
                if report_idx < num_cols:
                    val = row_values[report_idx]
                    if pd.notna(val):
                        ws_bd.cell(row=r_idx, column=col_excel, value=val)

        caminho_base_temporaria = os.path.join(pasta_atual, "Acompanhamento_BD_Tratado.xlsm")
        wb_base.save(caminho_base_temporaria)
        wb_base.close() 

        if acao == 'debug':
            tarefas[task_id] = {"progresso": 100, "status": "Diagnóstico Excel concluído!", "concluido": True, "file_id": agora_str, "acao": acao}
            return

        tarefas[task_id] = {"progresso": 60, "status": "Lendo cálculos originais da Base...", "concluido": False}
        
        # Lendo os dados DIRETAMENTE DA BASE já calculada para respeitar suas fórmulas!
        app_xl = xw.App(visible=False)
        try:
            wb_base_calc = app_xl.books.open(caminho_base_temporaria)
            app_xl.calculate() 
            
            ws_bd_calc = wb_base_calc.sheets["BD"]
            ult_linha = ws_bd_calc.range('A' + str(ws_bd_calc.cells.last_cell.row)).end('up').row
            
            # Puxa tudo da linha 2 até a última preenchida da coluna A até AK (índice 0 a 36)
            # AK inclui agora a EQUIPE_FINAL, que foi deslocada pela nova coluna StatusRetorno (AJ)
            if ult_linha > 1:
                dados_calculados = ws_bd_calc.range(f'A2:AK{ult_linha}').value
                if not isinstance(dados_calculados[0], list): dados_calculados = [dados_calculados]
            else:
                dados_calculados = []
                
            df_manipular = pd.DataFrame(dados_calculados)
            
            # Filtra e renomeia apenas as colunas que importam pra Tabela Dinâmica
            # Indice 1 = Coluna B (Tipo)
            # Indice 22 = Coluna W (Codigo da Equipe)
            # Indice 27 = Coluna AB (DataExecFim)
            # Indice 33 = Coluna AH (Valor)
            # Indice 36 = Coluna AK (EQUIPE_FINAL com fórmula, deslocada pela nova StatusRetorno em AJ)
            if df_manipular.shape[1] >= 37:
                df_manipular = df_manipular[[1, 22, 27, 33, 36]]
                df_manipular.columns = ['Tipo', 'Codigo', 'DataExecFim', 'Valor', 'EQUIPE_FINAL']
            else:
                raise Exception("A Base lida não possui as 37 colunas necessárias.")

            tarefas[task_id] = {"progresso": 70, "status": "Montando Tabela Dinâmica de Produção...", "concluido": False}
            
            df_manipular['Valor'] = df_manipular['Valor'].astype(str).str.replace('R$', '', regex=False).str.replace(' ', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df_manipular['Valor'] = pd.to_numeric(df_manipular['Valor'], errors='coerce').fillna(0)
            df_manipular['DataExecFim_Limpa'] = pd.to_datetime(df_manipular['DataExecFim'], errors='coerce', dayfirst=True)
            df_manipular['DataStr'] = df_manipular['DataExecFim_Limpa'].dt.strftime('%Y-%m-%d')
            
            df_filtrado = df_manipular[df_manipular['Tipo'].astype(str).str.strip().str.upper() != 'OCORRÊNCIAS DE PLANTÃO'].copy()
            
            # Agrupa exatamente como sairá na planilha: Código (Col B) e EQUIPE_FINAL (Col C)
            tabela_dinamica = pd.pivot_table(df_filtrado, values='Valor', index=['Codigo', 'EQUIPE_FINAL'], columns=['DataStr'], aggfunc='sum')

            # Calendário
            ano, mes = map(int, mes_referencia.split('-'))
            feriados_br = holidays.Brazil(years=ano)
            _, num_dias = calendar.monthrange(ano, mes)
            # Retira apenas domingos (6) e feriados. Sábados entram normais!
            dias_validos = [datetime.date(ano, mes, d) for d in range(1, num_dias + 1) if datetime.date(ano, mes, d).weekday() != 6 and datetime.date(ano, mes, d) not in feriados_br]
            dias_semana_pt = {0: 'seg', 1: 'ter', 2: 'qua', 3: 'qui', 4: 'sex', 5: 'sáb'}

            tarefas[task_id] = {"progresso": 85, "status": "Injetando matriz final de datas e valores...", "concluido": False}
            
            wb_base_calc.save()
            wb_base_calc.close()

            wb_xl = app_xl.books.open(cam_soli)
            ws_equipes = wb_xl.sheets["BASE DE EQUIPES"]
            
            # Colunas consecutivas para as datas a partir da Coluna E (5) - sem pular G e H!
            col_seguras_base = list(range(5, 5 + len(dias_validos)))
            
            for r in range(5, 2000):
                 if not ws_equipes.range((r, 3)).merge_cells:
                     ws_equipes.range((r, 2)).value = None
                     ws_equipes.range((r, 3)).value = None 
                 for c in col_seguras_base:
                     ws_equipes.range((r, c)).value = None

            mapa_datas_colunas = {}
            for idx, col in enumerate(col_seguras_base):
                dt_valida = dias_validos[idx]
                c_date = ws_equipes.range((4, col))
                c_date.value = dt_valida
                c_date.number_format = 'dd/mm/yyyy'
                mapa_datas_colunas[dt_valida.strftime('%Y-%m-%d')] = col

            linha_atual = 5
            for tuple_equipe in tabela_dinamica.index:
                codigo_equipe, equipe_nome = tuple_equipe
                if str(codigo_equipe).lower() in ['nan', 'none', ''] or not codigo_equipe: continue
                
                trava = 0
                while ws_equipes.range((linha_atual, 3)).value is not None or ws_equipes.range((linha_atual, 3)).merge_cells: 
                    linha_atual += 1
                    trava += 1
                    if trava > 2000: break 
                    
                ws_equipes.range((linha_atual, 2)).value = codigo_equipe 
                ws_equipes.range((linha_atual, 3)).value = equipe_nome   
                
                for data_str in tabela_dinamica.columns:
                    if data_str in mapa_datas_colunas:
                        col_destino = mapa_datas_colunas[data_str]
                        valor_produzido = tabela_dinamica.at[tuple_equipe, data_str]
                        if pd.notna(valor_produzido) and valor_produzido > 0:
                            ws_equipes.range((linha_atual, col_destino)).value = float(valor_produzido)

                linha_atual += 1

            app_xl.calculate()
            caminho_saida = os.path.join(pasta_atual, "Resultado_Acompanhamento_Preenchido.xlsm")
            wb_xl.save(caminho_saida)
            wb_xl.close()
        finally:
            app_xl.quit()

        tarefas[task_id] = {"progresso": 100, "status": "Processamento CONCLUÍDO com sucesso!", "concluido": True, "file_id": agora_str, "acao": acao}
        registrar_historico(pc_req, "Processamento Concluído", f"ID_PASTA:{agora_str}")

    except Exception as e:
        erro_msg = str(e)
        tarefas[task_id] = {"erro": erro_msg}
        registrar_historico(pc_req, "Erro", erro_msg)
    finally:
        pythoncom.CoUninitialize()

@app.route('/processar', methods=['POST'])
def processar():
    if not session.get('autenticado'):
        return jsonify({"status": "error", "message": "Sessão expirada."}), 403

    acao = request.form.get('acao') 
    mes_referencia = request.form.get('mes_referencia') 
    
    arquivo_listagem = request.files.get('listagem_file')
    if not arquivo_listagem:
        arquivo_listagem = request.files.get('csv_file') 
        
    arquivo_base = request.files.get('base_file')
    arquivo_soli = request.files.get('soli_file')

    pasta_principal = "Processamentos"
    agora = datetime.datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    pasta_atual = os.path.join(pasta_principal, agora)
    os.makedirs(pasta_atual, exist_ok=True)

    cam_listagem = os.path.join(pasta_atual, "temp_listagem.xlsm")
    cam_base = os.path.join(pasta_atual, "temp_base.xlsm")
    cam_soli = os.path.join(pasta_atual, "temp_soli.xlsm")
    
    arquivo_listagem.save(cam_listagem)
    arquivo_base.save(cam_base)
    arquivo_soli.save(cam_soli)

    task_id = str(uuid.uuid4())
    tarefas[task_id] = {"progresso": 0, "status": "Iniciando processo na fila...", "concluido": False}
    
    pc_requisitante = session.get('codigo_pc', codigo_pc_atual)

    thread = threading.Thread(
        target=executar_excel_background, 
        args=(task_id, pasta_atual, cam_listagem, cam_base, cam_soli, acao, mes_referencia, pc_requisitante, agora)
    )
    thread.start()

    return jsonify({"status": "processing", "task_id": task_id})

@app.route('/status_tarefa/<task_id>', methods=['GET'])
def status_tarefa(task_id):
    if task_id in tarefas:
        return jsonify(tarefas[task_id])
    return jsonify({"erro": "Tarefa não encontrada"}), 404

@app.route('/download/<tipo>/<pasta_id>', methods=['GET'])
def baixar_arquivo(tipo, pasta_id):
    if ".." in pasta_id or "/" in pasta_id or "\\" in pasta_id:
        return "ID de pasta inválido", 400
        
    pasta_alvo = os.path.join("Processamentos", pasta_id)
        
    if tipo == 'base':
        filename = os.path.join(pasta_alvo, "Acompanhamento_BD_Tratado.xlsm")
        download_name = "Acompanhamento_BD_Tratado.xlsm"
    elif tipo == 'soli':
        filename = os.path.join(pasta_alvo, "Resultado_Acompanhamento_Preenchido.xlsm")
        download_name = "Resultado_Acompanhamento_Preenchido.xlsm"
    else:
        return "Tipo de download inválido", 400

    if os.path.exists(filename):
        return send_file(filename, as_attachment=True, download_name=download_name)
    else:
        return "O arquivo solicitado expirou ou não foi encontrado!", 404

if __name__ == '__main__':
    print("Iniciando Aplicação Excel Segura na porta 5002...", flush=True)
    app.run(debug=True, use_reloader=False, port=5002)
