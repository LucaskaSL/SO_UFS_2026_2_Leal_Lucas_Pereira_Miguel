import requests
import csv
import os

URL = "http://localhost:11434/api/generate"
MODELO = "mistral:latest"
ARQUIVO_CSV = "sequencialDanielSaidaComplexa"

# criando variáveis de média
media_dur_total = 0
media_dur_load = 0
media_tokens = 0
media_tokens_ps = 0

#criando cabeçalho inicial
cabecalho = not os.path.exists(ARQUIVO_CSV)
with open(ARQUIVO_CSV, mode="a", newline="") as f:
    writer = csv.writer(f)
    if cabecalho:
        writer.writerow(["Prompt", "Id tentativa","Total_Duration_s", "Load_Duration_s", "Tokens", "Tokens_por_Segundo", "Resposta"])

# prompt simples

PROMPT = "Escreva uma história engraçada de cinco parágrafos envolvendo a criação do suco de manga."

payload = {
    "model": MODELO,
    "prompt": PROMPT,
    "stream": False,
    "options": {
        "temperature": 0.0
    }
}
# roda 10 vezes
for i in range(1, 11) :
    print(f"Enviando requisição complexa #{i} ao Ollama...")
    resposta = requests.post(URL, json=payload)
    dados = resposta.json()

    if "error" in dados:
        print(f"Erro do Ollama: {dados['error']}")
        exit(1)

    nano_para_s = 1e9

    #coleta dados
    total_dur_s = dados.get("total_duration", 0) / nano_para_s
    media_dur_total += total_dur_s

    load_dur_s = dados.get("load_duration", 0) / nano_para_s
    media_dur_load += load_dur_s

    tokens = dados.get("eval_count", 0)
    media_tokens += tokens

    tokens_ps = tokens/total_dur_s
    media_tokens_ps += tokens_ps

    texto_gerado = dados.get("response", "Texto não gerado")
    texto_limpo = texto_gerado.replace('\n', ' ').strip()

    #bora escrever no csv
    with open(ARQUIVO_CSV, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Suco de manga", i, f"{total_dur_s:.2f}", f"{load_dur_s:.2f}", tokens, f"{tokens_ps:.2f}", texto_limpo])

print("Sequência complexa bem sucedida!")

# calcular e escrever média
media_dur_load /= 10
media_dur_total /= 10
media_tokens /= 10
media_tokens_ps /= 10

with open(ARQUIVO_CSV, mode="a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Prompt", "Número de Tentativas", "Duração Média Total", "Duração Load Média", "Número Médio de Tokens", "Tokens p/s Médio", "Resposta"])
    writer.writerow(["Suco de manga", i, f"{media_dur_total:.2f}", f"{media_dur_load:.2f}", f"{media_tokens}", f"{media_tokens_ps:.2f}", texto_limpo])
