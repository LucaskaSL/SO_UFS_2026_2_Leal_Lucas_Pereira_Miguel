import os
import requests
import json
import time
import matplotlib.pyplot as plt
import threading as thd
import psutil

# FUNÇÕES DE SUPORTE 
def encontrar_processo_ollama():
    """Localiza o processo do Ollama no sistema operacional."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                return psutil.Process(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

proc_ollama = encontrar_processo_ollama()

# LAÇO DE AUTOMAÇÃO (DE 1 A 16 THREADS) ---
for num_threads_usadas in range(1, 17):
    # --- CONFIGURAÇÕES DA REQUISIÇÃO ---
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "mistral",
        "prompt": "Gere uma piada sobre um argentino se encontrando com um jacaré no elevador.",
        "stream": False,
        "options": {
            "num_ctx": 4096,     # Tamanho da janela de contexto
            "num_thread": num_threads_usadas,     # Quantidade de threads do teste atual
            "temperature": 0.0,  # 0.0 para respostas determinísticas
            "num_predict": 2000   # Limite de tokens
        }
    }

    # ESTRUTURAS E CONFIGURAÇÕES DE MONITORAMENTO
    LIMIAR_ATIVIDADE = 15.0  # Média de uso em % para considerar um núcleo ativo
    INTERVALO_AMOSTRAGEM = 0.2  # Captura métricas a cada 200ms

    tempos_cpu = []
    uso_total = []
    uso_processo_ollama = []
    uso_ram_percent = []
    uso_ram_ollama_mb = []
    uso_swap = []

    num_cores = psutil.cpu_count(logical=True)
    uso_cores = {i: [] for i in range(num_cores)}

    parar_monitoramento = False

    def coletar_uso_hardware():
        """Função executada em segundo plano para capturar CPU, RAM (Processo vs Sistema) e SWAP."""
        inicio_monitor = time.time()
        
        psutil.cpu_percent(percpu=True)
        if proc_ollama:
            try:
                proc_ollama.cpu_percent()
            except Exception:
                pass

        while not parar_monitoramento:
            t = round(time.time() - inicio_monitor, 2)
            percpu = psutil.cpu_percent(percpu=True)
            media_total = sum(percpu) / len(percpu) if percpu else 0
            
            # Coleta de Memória do Sistema e do Processo Ollama
            mem_sys = psutil.virtual_memory()
            ram_percent = mem_sys.percent
            swap_percent = psutil.swap_memory().percent

            cpu_ollama = 0
            ram_ollama_mb = 0
            if proc_ollama:
                try:
                    cpu_ollama = proc_ollama.cpu_percent()
                    # RSS: Resident Set Size (Memória RAM física real alocada pelo Ollama)
                    ram_ollama_mb = proc_ollama.memory_info().rss / (1024 * 1024)
                except Exception:
                    pass

            tempos_cpu.append(t)
            uso_total.append(media_total)
            uso_processo_ollama.append(cpu_ollama)
            uso_ram_percent.append(ram_percent)
            uso_ram_ollama_mb.append(ram_ollama_mb)
            uso_swap.append(swap_percent)
            
            for i, val in enumerate(percpu):
                uso_cores[i].append(val)
                
            time.sleep(INTERVALO_AMOSTRAGEM)

    # EXECUÇÃO DO MONITORAMENTO E REQUISIÇÃO
    print(f"\n" + "="*50)
    print(f" Iniciando monitoramento de hardware em segundo plano (num_thread = {num_threads_usadas})...")
    thread_monitor = thd.Thread(target=coletar_uso_hardware)
    thread_monitor.start()

    print("Enviando requisição ao Ollama (Aguarde)...")
    inicio = time.time()
    try:
        response = requests.post(url, json=payload)
        fim = time.time()
    finally:
        parar_monitoramento = True
        thread_monitor.join()

    dados = response.json()

    # Conversão dos tempos de nanosegundos para segundos
    ns_to_s = 1e9
    tempo_total = dados.get('total_duration', 0) / ns_to_s
    tempo_carga = dados.get('load_duration', 0) / ns_to_s
    tempo_prompt = dados.get('prompt_eval_duration', 0) / ns_to_s
    tempo_geracao = dados.get('eval_duration', 0) / ns_to_s
    tokens_gerados = dados.get('eval_count', 0)

    vazao = (tokens_gerados / tempo_geracao) if tempo_geracao > 0 else 0
    
    # Médias de hardware
    media_ram_percent = sum(uso_ram_percent) / len(uso_ram_percent) if uso_ram_percent else 0
    media_ram_ollama_mb = sum(uso_ram_ollama_mb) / len(uso_ram_ollama_mb) if uso_ram_ollama_mb else 0
    media_swap = sum(uso_swap) / len(uso_swap) if uso_swap else 0
    media_total_cpu = sum(uso_total) / len(uso_total) if uso_total else 0
    media_ollama_proc = sum(uso_processo_ollama) / len(uso_processo_ollama) if uso_processo_ollama else 0

    # SALVAMENTO DO RELATÓRIO EM ARQUIVO NA PASTA LOG 
    pasta_log = "log"
    os.makedirs(pasta_log, exist_ok=True)

    caminho_log = os.path.join(pasta_log, f"{num_threads_usadas}_log_cpus_ollama.txt")

    relatorio_conteudo = f"""{"="*45}
RESULTADOS DA INFERÊNCIA (RAIO-X)
{"="*45}
CPUs / Threads Usadas   : {num_threads_usadas}
Total de Tokens gerados : {tokens_gerados}
Latência Total          : {tempo_total:.4f} s
{"-" * 45}
Tempo de I/O (Load)     : {tempo_carga:.4f} s  <- Leitura disco/RAM
Tempo de TTFT (Prompt)  : {tempo_prompt:.4f} s  <- Processamento da pergunta
Tempo de CPU (Geração)  : {tempo_geracao:.4f} s  <- Geração do texto
{"-" * 45}
Vazão (Throughput)      : {vazao:.2f} tokens/s
{"-" * 45}
MÉTRICAS DE HARDWARE
Uso Médio CPU (Processo Ollama) : {media_ollama_proc:.2f} %
Uso Médio CPU Total (Sistema)   : {media_total_cpu:.2f} %
Uso Médio RAM (Processo Ollama) : {media_ram_ollama_mb:.2f} MB
Uso Médio RAM Total (Sistema)   : {media_ram_percent:.2f} %
Uso Médio SWAP                 : {media_swap:.2f} %
{"="*45}
"""

    with open(caminho_log, "w", encoding="utf-8") as f:
        f.write(relatorio_conteudo)

    print(f"\n[SUCESSO] Relatório de inferência salvo em: {caminho_log}")

    # PASTA DE IMAGENS
    pasta_img = "img"
    os.makedirs(pasta_img, exist_ok=True)

    # GRÁFICO DE CPU
    plt.figure(figsize=(11, 6))

    cores_ativos_count = 0

    for core_id, valores in uso_cores.items():
        media_uso = sum(valores) / len(valores) if valores else 0
        if media_uso >= LIMIAR_ATIVIDADE:
            plt.plot(
                tempos_cpu, 
                valores, 
                linewidth=2.2, 
                label=f"Core {core_id} (Média: {media_uso:.1f}%)"
            )
            cores_ativos_count += 1

    plt.plot(
        tempos_cpu, 
        uso_total, 
        color="black", 
        linewidth=2, 
        linestyle="--", 
        label=f"CPU Total (Média Geral: {media_total_cpu:.1f}%)"
    )

    if proc_ollama and any(uso_processo_ollama):
        plt.plot(
            tempos_cpu,
            uso_processo_ollama,
            color="#d62728",
            linewidth=1.8,
            linestyle="-.",
            label=f"Processo Ollama (Média: {media_ollama_proc:.1f}%)"
        )

    plt.title(f"Consumo de CPU — Exibindo Apenas os {cores_ativos_count} Cores Usados pelo Ollama", fontsize=12, fontweight='bold')
    plt.xlabel("Tempo de Execução (segundos)")
    plt.ylabel("Uso de CPU (%)")
    plt.ylim(0, 105)
    plt.grid(True, linestyle=":", alpha=0.5)
    plt.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize="medium")
    plt.tight_layout()

    caminho_cpu = os.path.join(pasta_img, f"{num_threads_usadas}_cpus_ollama.png")
    plt.savefig(caminho_cpu, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"[SUCESSO] Gráfico e log salvos para {num_threads_usadas} thread(s).")

    # Pausa iterações
    time.sleep(1)