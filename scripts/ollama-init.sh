#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
models="${OLLAMA_INIT_MODELS:-qwen3.5:9b bge-m3}"
attempts=0

until ollama list >/dev/null 2>&1; do
  attempts=$((attempts + 1))

  if [ "$attempts" -ge 60 ]; then
    printf 'Timed out waiting for Ollama at %s\n' "$OLLAMA_HOST" >&2
    exit 1
  fi

  sleep 2
done

for model in $models; do
  if ollama show "$model" >/dev/null 2>&1; then
    printf 'Ollama model already available: %s\n' "$model"
    continue
  fi

  printf 'Pulling Ollama model: %s\n' "$model"
  ollama pull "$model"
done
