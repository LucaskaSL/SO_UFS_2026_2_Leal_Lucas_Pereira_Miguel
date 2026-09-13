#!/bin/bash
#
# run_experiment.sh — Coleta métricas de execução do Ollama (AV1 - Sistemas Operacionais)
#
# Uso:
#   ./run_experiment.sh <config_nome> <n_repeticoes> <prompt> [modelo]
#
# Exemplo:
#   ./run_experiment.sh config1_padrao 3 "Olá, tudo bem?"
#   ./run_experiment.sh config1_padrao 5 "Explique o que é um sistema operacional" mistral:7b-instruct-v0.3-q4_0
#
# Saída:
#   Cria (ou adiciona a) logs/resultados.csv com uma linha por execução.

set -euo pipefail

CONFIG_NOME="${1:?Uso: $0 <config_nome> <n_repeticoes> <prompt> [modelo]}"
N_REPETICOES="${2:?Informe o número de repetições}"
PROMPT="${3:?Informe o prompt}"
MODELO="${4:-mistral:7b-instruct-v0.3-q4_0}"

OLLAMA_URL="http://localhost:11434/api/generate"
SAIDA_CSV="logs/resultados.csv"

mkdir -p logs

# Verifica se jq está instalado
if ! command -v jq &> /dev/null; then
    echo "jq não encontrado. Instalando..."
    sudo apt-get update && sudo apt-get install -y jq
fi

# Cria cabeçalho do CSV se o arquivo ainda não existir
if [ ! -f "$SAIDA_CSV" ]; then
    echo "timestamp,config,repeticao,modelo,prompt,real_time_s,total_duration_ms,load_duration_ms,prompt_eval_count,prompt_eval_duration_ms,eval_count,eval_duration_ms,tokens_per_second" > "$SAIDA_CSV"
fi

echo "=== Executando '$CONFIG_NOME' — $N_REPETICOES repetições — modelo: $MODELO ==="
echo "Prompt: $PROMPT"
echo ""

for i in $(seq 1 "$N_REPETICOES"); do
    echo "--- Repetição $i/$N_REPETICOES ---"

    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Mede o tempo real da requisição e captura a resposta JSON
    START=$(date +%s.%N)
    RESPONSE=$(curl -s "$OLLAMA_URL" -d "{
        \"model\": \"$MODELO\",
        \"prompt\": \"$PROMPT\",
        \"stream\": false
    }")
    END=$(date +%s.%N)
    REAL_TIME=$(echo "$END - $START" | bc)

    # Extrai os campos do JSON (valores em nanosegundos, convertidos para ms)
    TOTAL_DURATION=$(echo "$RESPONSE" | jq -r '.total_duration // 0')
    LOAD_DURATION=$(echo "$RESPONSE" | jq -r '.load_duration // 0')
    PROMPT_EVAL_COUNT=$(echo "$RESPONSE" | jq -r '.prompt_eval_count // 0')
    PROMPT_EVAL_DURATION=$(echo "$RESPONSE" | jq -r '.prompt_eval_duration // 0')
    EVAL_COUNT=$(echo "$RESPONSE" | jq -r '.eval_count // 0')
    EVAL_DURATION=$(echo "$RESPONSE" | jq -r '.eval_duration // 0')

    # Converte nanosegundos para milissegundos
    TOTAL_MS=$(echo "$TOTAL_DURATION / 1000000" | bc)
    LOAD_MS=$(echo "$LOAD_DURATION / 1000000" | bc)
    PROMPT_EVAL_MS=$(echo "$PROMPT_EVAL_DURATION / 1000000" | bc)
    EVAL_MS=$(echo "$EVAL_DURATION / 1000000" | bc)

    # Calcula tokens por segundo (evita divisão por zero)
    if [ "$EVAL_DURATION" -gt 0 ]; then
        TOKENS_PER_SEC=$(echo "scale=2; $EVAL_COUNT / ($EVAL_DURATION / 1000000000)" | bc)
    else
        TOKENS_PER_SEC=0
    fi

    echo "  Tempo real: ${REAL_TIME}s | Load: ${LOAD_MS}ms | Eval: ${EVAL_MS}ms | Tokens/s: ${TOKENS_PER_SEC}"

    # Salva no CSV (escapa aspas no prompt para não quebrar o CSV)
    PROMPT_ESCAPED=$(echo "$PROMPT" | sed 's/"/""/g')
    echo "$TIMESTAMP,$CONFIG_NOME,$i,$MODELO,\"$PROMPT_ESCAPED\",$REAL_TIME,$TOTAL_MS,$LOAD_MS,$PROMPT_EVAL_COUNT,$PROMPT_EVAL_MS,$EVAL_COUNT,$EVAL_MS,$TOKENS_PER_SEC" >> "$SAIDA_CSV"

    # Pequena pausa entre repetições
    sleep 2
done

echo ""
echo "=== Concluído. Resultados salvos em $SAIDA_CSV ==="
