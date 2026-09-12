#!/bin/bash
#
# run_concurrency.sh — Testa concorrência/carga no Ollama (AV1 - Sistemas Operacionais, Config. 2)
#
# Dispara N requisições SIMULTÂNEAS (em paralelo) e mede o tempo total do lote,
# além de coletar métricas individuais de cada requisição.
#
# Uso:
#   ./run_concurrency.sh <config_nome> <n_requisicoes_simultaneas> <prompt> [modelo]
#
# Exemplo:
#   ./run_concurrency.sh config2_concorrencia_2 2 "Olá, tudo bem?"
#   ./run_concurrency.sh config2_concorrencia_4 4 "Explique brevemente o que é um processo"
#
# Saída:
#   Cria (ou adiciona a) logs/resultados_concorrencia.csv com uma linha por requisição,
#   além de uma linha de resumo do lote em logs/resumo_lotes.csv

set -uo pipefail   # (sem -e: uma requisição falhar não deve derrubar as outras)

CONFIG_NOME="${1:?Uso: $0 <config_nome> <n_requisicoes_simultaneas> <prompt> [modelo]}"
N_SIMULTANEAS="${2:?Informe o número de requisições simultâneas}"
PROMPT="${3:?Informe o prompt}"
MODELO="${4:-mistral:7b-instruct-v0.3-q4_0}"

OLLAMA_URL="http://localhost:11434/api/generate"
SAIDA_CSV="logs/resultados_concorrencia.csv"
RESUMO_CSV="logs/resumo_lotes.csv"
TMP_DIR=$(mktemp -d)

mkdir -p logs

if ! command -v jq &> /dev/null; then
    echo "jq não encontrado. Instalando..."
    sudo apt-get update && sudo apt-get install -y jq
fi

if [ ! -f "$SAIDA_CSV" ]; then
    echo "timestamp,config,n_simultaneas,worker_id,modelo,prompt,real_time_s,total_duration_ms,load_duration_ms,eval_count,eval_duration_ms,tokens_per_second" > "$SAIDA_CSV"
fi

if [ ! -f "$RESUMO_CSV" ]; then
    echo "timestamp,config,n_simultaneas,modelo,prompt,tempo_total_lote_s,tempo_medio_por_req_s,throughput_req_por_s" > "$RESUMO_CSV"
fi

echo "=== Concorrência: '$CONFIG_NOME' — $N_SIMULTANEAS requisições simultâneas — modelo: $MODELO ==="
echo "Prompt: $PROMPT"
echo ""

# Função executada por cada "worker" em paralelo
executar_worker() {
    local worker_id=$1
    local out_file="$TMP_DIR/worker_${worker_id}.json"
    local time_file="$TMP_DIR/worker_${worker_id}.time"

    START=$(date +%s.%N)
    curl -s "$OLLAMA_URL" -d "{
        \"model\": \"$MODELO\",
        \"prompt\": \"$PROMPT\",
        \"stream\": false
    }" -o "$out_file"
    END=$(date +%s.%N)

    echo "$END - $START" | bc > "$time_file"
}

export -f executar_worker
export TMP_DIR OLLAMA_URL MODELO PROMPT

echo "Disparando $N_SIMULTANEAS requisições em paralelo..."
LOTE_START=$(date +%s.%N)

# Dispara todos os workers em background e espera todos terminarem
PIDS=()
for w in $(seq 1 "$N_SIMULTANEAS"); do
    executar_worker "$w" &
    PIDS+=($!)
done

for pid in "${PIDS[@]}"; do
    wait "$pid"
done

LOTE_END=$(date +%s.%N)
TEMPO_TOTAL_LOTE=$(echo "$LOTE_END - $LOTE_START" | bc)

echo ""
echo "Todas as $N_SIMULTANEAS requisições concluídas. Processando resultados..."
echo ""

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SOMA_TEMPOS=0

for w in $(seq 1 "$N_SIMULTANEAS"); do
    RESPONSE=$(cat "$TMP_DIR/worker_${w}.json")
    REAL_TIME=$(cat "$TMP_DIR/worker_${w}.time")

    TOTAL_DURATION=$(echo "$RESPONSE" | jq -r '.total_duration // 0')
    LOAD_DURATION=$(echo "$RESPONSE" | jq -r '.load_duration // 0')
    EVAL_COUNT=$(echo "$RESPONSE" | jq -r '.eval_count // 0')
    EVAL_DURATION=$(echo "$RESPONSE" | jq -r '.eval_duration // 0')

    TOTAL_MS=$(echo "$TOTAL_DURATION / 1000000" | bc)
    LOAD_MS=$(echo "$LOAD_DURATION / 1000000" | bc)
    EVAL_MS=$(echo "$EVAL_DURATION / 1000000" | bc)

    if [ "$EVAL_DURATION" != "0" ] && [ "$EVAL_DURATION" -gt 0 ]; then
        TOKENS_PER_SEC=$(echo "scale=2; $EVAL_COUNT / ($EVAL_DURATION / 1000000000)" | bc)
    else
        TOKENS_PER_SEC=0
    fi

    echo "  Worker $w: tempo real ${REAL_TIME}s | load ${LOAD_MS}ms | eval ${EVAL_MS}ms | tokens/s ${TOKENS_PER_SEC}"

    PROMPT_ESCAPED=$(echo "$PROMPT" | sed 's/"/""/g')
    echo "$TIMESTAMP,$CONFIG_NOME,$N_SIMULTANEAS,$w,$MODELO,\"$PROMPT_ESCAPED\",$REAL_TIME,$TOTAL_MS,$LOAD_MS,$EVAL_COUNT,$EVAL_MS,$TOKENS_PER_SEC" >> "$SAIDA_CSV"

    SOMA_TEMPOS=$(echo "$SOMA_TEMPOS + $REAL_TIME" | bc)
done

TEMPO_MEDIO=$(echo "scale=3; $SOMA_TEMPOS / $N_SIMULTANEAS" | bc)
THROUGHPUT=$(echo "scale=3; $N_SIMULTANEAS / $TEMPO_TOTAL_LOTE" | bc)

echo ""
echo "=== Resumo do lote ==="
echo "  Tempo total do lote (todas em paralelo): ${TEMPO_TOTAL_LOTE}s"
echo "  Tempo médio por requisição: ${TEMPO_MEDIO}s"
echo "  Throughput: ${THROUGHPUT} requisições/segundo"

PROMPT_ESCAPED=$(echo "$PROMPT" | sed 's/"/""/g')
echo "$TIMESTAMP,$CONFIG_NOME,$N_SIMULTANEAS,$MODELO,\"$PROMPT_ESCAPED\",$TEMPO_TOTAL_LOTE,$TEMPO_MEDIO,$THROUGHPUT" >> "$RESUMO_CSV"

rm -rf "$TMP_DIR"

echo ""
echo "=== Concluído. Resultados em $SAIDA_CSV e $RESUMO_CSV ==="
