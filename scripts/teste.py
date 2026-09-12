import requests
import json
import time
import matplotlib.pyplot as plt
import threading as thd

url = "http://localhost:11434/api/generate"

payload = {
    "model": "mistral",
    "prompt": "Quantas copas do mundo já aconteceram?",
    "stream": False,
    "options": {
        "num_ctx": 4096,     # Tamanho da janela de contexto (teste com 512, 1024, 4096)
        "num_thread": 4,     # Limita a inferência a 4 núcleos de CPU
        "temperature": 0.0,  # 0.0 tira a aleatoriedade (bom para testes replicáveis)
        "num_predict": 2000   # Força o modelo a parar após gerar 200 tokens
    }
}


print("Enviando requisição ao Ollama (Aguarde)...")
inicio = time.time()
response = requests.post(url, json=payload)
fim = time.time()

dados = response.json()

# O Ollama devolve os tempos em nanosegundos. Essa constante converte para segundos.
ns_to_s = 1e9

# Extração de métricas
tempo_total = dados.get('total_duration', 0) / ns_to_s
tempo_carga = dados.get('load_duration', 0) / ns_to_s
tempo_prompt = dados.get('prompt_eval_duration', 0) / ns_to_s
tempo_geracao = dados.get('eval_duration', 0) / ns_to_s
tokens_gerados = dados.get('eval_count', 0)

if tempo_geracao > 0:
    vazao = tokens_gerados / tempo_geracao
else:
    vazao = 0

print("\n" + "="*40)
print("   RESULTADOS DA INFERÊNCIA (RAIO-X)")
print("="*40)
print(f"Total de Tokens gerados : {tokens_gerados}")
print(f"Latência Total          : {tempo_total:.4f} s")
print("-" * 40)
print(f"Tempo de I/O (Load)     : {tempo_carga:.4f} s  <- Tempo lendo o modelo do disco/RAM")
print(f"Tempo de TTFT (Prompt)  : {tempo_prompt:.4f} s  <- Tempo para entender a pergunta")
print(f"Tempo de CPU (Geração)  : {tempo_geracao:.4f} s  <- Tempo efetivo gerando o texto")
print("-" * 40)
print(f"Vazão (Throughput)      : {vazao:.2f} tokens/s")
print("="*40)