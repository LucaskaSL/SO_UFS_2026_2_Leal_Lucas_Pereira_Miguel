import os
import requests
import json
import time
import uuid
import matplotlib.pyplot as plt
import threading as thd
import psutil
import numpy as np

# CONFIGURAÇÕES DA BATERIA DE TESTES
AMBIENTE = "nativo"  
URL = "http://localhost:11434/api/generate"

MODELOS_QUANTIZADOS = [
    #"mistral:latest",
   # "mistral:7b-instruct-q4_K_M",
    "mistral:7b-instruct-q8_0"
]
MODOS_CACHE = ["sem_cache", "com_cache"]
LISTA_THREADS = [4, 6, 8, 12, 16]
NUM_REPETICOES = 3
NUM_CORES = psutil.cpu_count(logical=True)

# DEFINIÇÃO DOS CENÁRIOS DE CONTEXTO 
CONTEXTO_CURTO = """
Você é um assistente de triagem de incidentes de TI.
Analise o log a seguir e extraia apenas os campos no formato JSON contendo: "servico", "erro" e "prioridade".

Log: [2026-09-14 18:30:12] CRITICAL [database-cluster-02] DeadlockDetected: Connection pool exhausted while executing query on table 'orders'. Transaction aborted by lock manager after 10000ms timeout.
"""

SECAO_ARQUITETURA = """
[SEÇÃO 1: ARQUITETURA DISTRIBUÍDA E PERSISTÊNCIA]
A consistência em sistemas distribuídos é regida pelo Teorema CAP. Em arquiteturas microprocessadas, o uso de bancos de dados relacionais exige estratégias avançadas de replicação streaming via Write-Ahead Logging (WAL). O gargalo em operações de alta gravação reside na latência de sincronização no disco (fsync).
"""

SECAO_REDES = """
[SEÇÃO 2: PROTOCOLOS DE REDE E DESEMPENHO DE TRANSPORTE]
A comunicação de baixa latência em microsserviços migrou do tradicional HTTP/1.1 para gRPC baseado em HTTP/2 e HTTP/3 (QUIC). O protocolo QUIC elimina o Head-of-Line Blocking na camada de transporte usando UDP como base.
"""

SECAO_LLM = """
[SEÇÃO 3: ENGENHARIA DE COMPUTAÇÃO E INFERÊNCIA DE LLMs]
A fase de prefill na arquitetura Transformer processa todos os tokens de entrada simultaneamente para construir a matriz de atenção Key-Value (KV Cache). Essa fase é Compute-Bound. A fase de geração (decode) é Memory-Bandwidth Bound.
"""

SECAO_SEGURANCA = """
[SEÇÃO 4: SEGURANÇA E GERENCIAMENTO DE IDENTIDADE]
A implementação de controle de acesso baseado em funções (RBAC) em ambientes distribuídos requer o uso de tokens assinados criptograficamente (JWT). A validação com algoritmos assimétricos reduz chamadas de rede.
"""

TEXTO_DIVERSIFICADO = "\n\n".join([
    SECAO_ARQUITETURA, SECAO_REDES, SECAO_LLM, SECAO_SEGURANCA
] * 6)

CONTEXTO_LONGO = f"Analise o relatório de infraestrutura a seguir e elabore um resumo técnico dos riscos operacionais identificados:\n\n{TEXTO_DIVERSIFICADO}"

CENARIOS_ENTRADA = {
   # "Contexto_Curto": CONTEXTO_CURTO,
    "Contexto_Longo": CONTEXTO_LONGO
}

# FUNÇÕES AUXILIARES
def encontrar_processo_ollama():
    nomes_alvo = ['ollama', 'ollama_llama_server', 'ollama-runner']
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            p_name = proc.info['name'].lower() if proc.info['name'] else ''
            if any(alvo in p_name for alvo in nomes_alvo):
                return psutil.Process(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

proc_ollama = encontrar_processo_ollama()

def preparar_prompt(modo_cache, prompt_base):
    if modo_cache == "sem_cache":
        return f"[ID_{uuid.uuid4().hex[:8]}]\n{prompt_base}"
    return prompt_base

def enviar_requisicao(modelo, prompt_texto, num_threads):
    payload = {
        "model": modelo,
        "prompt": prompt_texto,
        "stream": False,
        "options": {
            "num_ctx": 4096,
            "num_thread": num_threads,
            "temperature": 0.0,
            "num_predict": 200
        }
    }
    inicio_req = time.time()
    try:
        resp = requests.post(URL, json=payload, timeout=600)
        fim_req = time.time()

        if resp.status_code != 200:
            print(f"\n[ERRO API HTTP {resp.status_code}]: {resp.text}")
            return None

        dados = resp.json()
        ns_to_s = 1e9
        return {
            "latencia_total": fim_req - inicio_req,
            "tokens": dados.get('eval_count', 0),
            "tempo_geracao": dados.get('eval_duration', 0) / ns_to_s,
            "tempo_prompt": dados.get('prompt_eval_duration', 0) / ns_to_s,
            "tempo_carga": dados.get('load_duration', 0) / ns_to_s,
            "resposta_texto": dados.get('response', '')
        }
    except Exception as e:
        print(f"\n[FALHA DE CONEXÃO COM OLLAMA]: {e}")
        return None

# LAÇO PRINCIPAL
for modelo in MODELOS_QUANTIZADOS:
    modelo_tag = modelo.replace(":", "_").replace("/", "_")
    
    for nome_cenario, prompt_base in CENARIOS_ENTRADA.items():
        for modo_cache in MODOS_CACHE:
            for num_threads_usadas in LISTA_THREADS:
                
                print(f"\n Executando: Modelo={modelo} | Cenário={nome_cenario} | Cache={modo_cache} | Threads={num_threads_usadas}")

                acum_vazao, acum_latencia, acum_tempo_prompt, acum_tempo_geracao, acum_respostas = [], [], [], [], []
                acum_media_ollama_proc, acum_media_total_cpu = [], []
                acum_media_ram_ollama_mb, acum_media_ram_percent = [], []

                runs_tempos, runs_uso_total, runs_uso_ollama = [], [], []
                runs_uso_cores = {i: [] for i in range(NUM_CORES)}

                if modo_cache == "com_cache":
                    enviar_requisicao(modelo, prompt_base, num_threads_usadas)

                for rep in range(1, NUM_REPETICOES + 1):
                    INTERVALO_AMOSTRAGEM = 0.2
                    tempos_cpu, uso_total, uso_processo_ollama = [], [], []
                    uso_ram_percent, uso_ram_ollama_mb = [], []
                    uso_cores_rep = {i: [] for i in range(NUM_CORES)}
                    parar_monitoramento = False

                    def coletar_uso_hardware():
                        inicio_monitor = time.time()
                        psutil.cpu_percent(percpu=True)
                        if proc_ollama:
                            try: proc_ollama.cpu_percent()
                            except: pass

                        while not parar_monitoramento:
                            t = round(time.time() - inicio_monitor, 2)
                            percpu = psutil.cpu_percent(percpu=True)
                            media_total = sum(percpu) / len(percpu) if percpu else 0
                            
                            mem_sys = psutil.virtual_memory()
                            cpu_ollama, ram_ollama_mb = 0, 0
                            if proc_ollama:
                                try:
                                    cpu_ollama = proc_ollama.cpu_percent()
                                    ram_ollama_mb = proc_ollama.memory_info().rss / (1024 * 1024)
                                except: pass

                            tempos_cpu.append(t)
                            uso_total.append(media_total)
                            uso_processo_ollama.append(cpu_ollama)
                            uso_ram_percent.append(mem_sys.percent)
                            uso_ram_ollama_mb.append(ram_ollama_mb)
                            
                            for i, val in enumerate(percpu):
                                uso_cores_rep[i].append(val)
                                
                            time.sleep(INTERVALO_AMOSTRAGEM)

                    thread_monitor = thd.Thread(target=coletar_uso_hardware)
                    thread_monitor.start()

                    prompt_execucao = preparar_prompt(modo_cache, prompt_base)
                    res_req = enviar_requisicao(modelo, prompt_execucao, num_threads_usadas)

                    parar_monitoramento = True
                    thread_monitor.join()

                    if res_req is None:
                        continue

                    vazao = res_req['tokens'] / res_req['latencia_total'] if res_req['latencia_total'] > 0 else 0

                    acum_vazao.append(vazao)
                    acum_latencia.append(res_req['latencia_total'])
                    acum_tempo_prompt.append(res_req['tempo_prompt'])
                    acum_tempo_geracao.append(res_req['tempo_geracao'])
                    acum_respostas.append(res_req['resposta_texto'])

                    acum_media_ram_ollama_mb.append(np.mean(uso_ram_ollama_mb) if uso_ram_ollama_mb else 0)
                    acum_media_ram_percent.append(np.mean(uso_ram_percent) if uso_ram_percent else 0)
                    acum_media_total_cpu.append(np.mean(uso_total) if uso_total else 0)
                    acum_media_ollama_proc.append(np.mean(uso_processo_ollama) if uso_processo_ollama else 0)

                    runs_tempos.append(tempos_cpu)
                    runs_uso_total.append(uso_total)
                    runs_uso_ollama.append(uso_processo_ollama)
                    for i in range(NUM_CORES):
                        runs_uso_cores[i].append(uso_cores_rep[i])

                    time.sleep(0.5)

                if not acum_vazao:
                    continue

                # ALINHAMENTO TEMPORAL DOS GRÁFICOS
                max_tempo = max(t[-1] for t in runs_tempos if len(t) > 0)
                grid_tempo = np.arange(0, max_tempo + INTERVALO_AMOSTRAGEM, INTERVALO_AMOSTRAGEM)

                interp_uso_total = [np.interp(grid_tempo, t, u) for t, u in zip(runs_tempos, runs_uso_total)]
                grid_uso_total_medio = np.mean(interp_uso_total, axis=0)

                interp_uso_ollama = [np.interp(grid_tempo, t, u) for t, u in zip(runs_tempos, runs_uso_ollama)]
                grid_uso_ollama_medio = np.mean(interp_uso_ollama, axis=0)

                grid_uso_cores_medio = {
                    c: np.mean([np.interp(grid_tempo, runs_tempos[r], runs_uso_cores[c][r]) for r in range(len(runs_tempos))], axis=0)
                    for c in range(NUM_CORES)
                }

                # CONSOLIDAÇÃO DO RELATÓRIO COM USO INDIVIDUAL DOS CORES E RAM TOTAL
                linhas_cores = []
                for core_id, valores in grid_uso_cores_medio.items():
                    media_core = np.mean(valores)
                    linhas_cores.append(f"Core {core_id:02d}                  : {media_core:.2f} %")

                texto_cores_relatorio = "\n".join(linhas_cores)

                pasta_base = os.path.join("bateria_resultados", AMBIENTE, modelo_tag, nome_cenario, modo_cache, f"threads_{num_threads_usadas}")
                os.makedirs(pasta_base, exist_ok=True)

                relatorio = f"""{"="*55}
MÉTRICAS DE BENCHMARK DE MODELO, CONTEXTO E CACHE
{"="*55}
Ambiente de Execução      : {AMBIENTE}
Modelo / Quantização      : {modelo}
Cenário de Contexto       : {nome_cenario}
Modo de KV Cache          : {modo_cache}
Threads Ollama (Núcleos)  : {num_threads_usadas}
{"-" * 55}
Vazão Média (Decode)      : {np.mean(acum_vazao):.2f} tokens/s
Latência Total E2E        : {np.mean(acum_latencia):.4f} s
Tempo TTFT (Prompt Eval)  : {np.mean(acum_tempo_prompt):.4f} s
Tempo Decode (Geração)    : {np.mean(acum_tempo_geracao):.4f} s
{"-" * 55}
Consumo Médio RAM Ollama  : {np.mean(acum_media_ram_ollama_mb):.2f} MB
Uso Médio RAM Total       : {np.mean(acum_media_ram_percent):.2f} %
Uso Médio CPU Processo    : {np.mean(acum_media_ollama_proc):.2f} %
Uso Médio CPU Total       : {np.mean(acum_media_total_cpu):.2f} %
{"-" * 55}
USO MÉDIO INDIVIDUAL DOS NÚCLEOS (CPU CORES)
{texto_cores_relatorio}
{"-" * 55}
RESPOSTA AMOSTRA:
{acum_respostas[0].strip() if acum_respostas else 'N/A'}
{"="*55}
"""
                with open(os.path.join(pasta_base, "relatorio_execucao.txt"), "w", encoding="utf-8") as f:
                    f.write(relatorio)

                plt.figure(figsize=(11, 6))
                for core_id, valores in grid_uso_cores_medio.items():
                    if np.mean(valores) >= 15.0:
                        plt.plot(grid_tempo, valores, linewidth=1.5, alpha=0.7, label=f"Core {core_id}")

                plt.plot(grid_tempo, grid_uso_total_medio, color="black", linewidth=2.2, linestyle="--", label="CPU Total")
                if proc_ollama and np.any(grid_uso_ollama_medio):
                    plt.plot(grid_tempo, grid_uso_ollama_medio, color="#d62728", linewidth=1.8, label="Ollama Proc")

                plt.title(f"[{AMBIENTE.upper()}] {modelo} | {nome_cenario} | Cache: {modo_cache} | Threads: {num_threads_usadas}", fontsize=10, fontweight='bold')
                plt.xlabel("Tempo (s)")
                plt.ylabel("Uso de CPU (%)")
                plt.ylim(0, 105)
                plt.grid(True, linestyle=":", alpha=0.5)
                plt.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
                plt.tight_layout()
                plt.savefig(os.path.join(pasta_base, "perfil_cpu.png"), dpi=300, bbox_inches="tight")
                plt.close()

                cores_ativos = [
                    f"C{c:02d}: {np.mean(v):.1f}%" 
                    for c, v in grid_uso_cores_medio.items() 
                    if np.mean(v) >= 15.0
                ]
                print(f"[OK] Gravação em {pasta_base} | RAM Total: {np.mean(acum_media_ram_percent):.1f}% | Cores Ativos: {', '.join(cores_ativos)}")