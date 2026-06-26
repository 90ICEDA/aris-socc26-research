#!/usr/bin/env bash
set -euo pipefail

echo "[T11 probe] This script will NOT kill any existing GPU process."
echo "[T11 probe] It only checks free VRAM and tries a low-memory vLLM server if possible."
echo

GPU_ID="${GPU_ID:-0}"
MODEL="${MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"
PORT="${PORT:-8000}"
WORKDIR="${WORKDIR:-$HOME/socc26_vllm_probe}"
MIN_FREE_MB="${MIN_FREE_MB:-2600}"

echo "[1/6] GPU status:"
nvidia-smi || {
  echo "[FAIL] nvidia-smi failed. WSL GPU is not ready."
  exit 2
}

FREE_MB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$GPU_ID" | tr -d ' ')
USED_MB=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU_ID" | tr -d ' ')
TOTAL_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits -i "$GPU_ID" | tr -d ' ')

echo
echo "[2/6] VRAM: used=${USED_MB}MiB free=${FREE_MB}MiB total=${TOTAL_MB}MiB"
echo "[2/6] Minimum free VRAM required by this low-memory probe: ${MIN_FREE_MB}MiB"

if [ "$FREE_MB" -lt "$MIN_FREE_MB" ]; then
  echo
  echo "[DEFER_GPU_BUSY] Free VRAM is too low. Another project is using the GPU."
  echo "Do NOT kill it. Wait for it to finish, or rerun later:"
  echo "  bash tracks/T11_llm_cache_isolation/scripts/probe_vllm_4060_lowmem.sh"
  exit 3
fi

echo
echo "[3/6] Prepare vLLM venv in $WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -U pip

if ! python -c "import vllm" >/dev/null 2>&1; then
  echo "[3/6] Installing vLLM. This may take a while."
  python -m pip install vllm
else
  echo "[3/6] vLLM already installed."
fi

echo
echo "[4/6] Check whether port $PORT is already used"
if command -v ss >/dev/null 2>&1; then
  if ss -ltn | grep -q ":$PORT "; then
    echo "[FAIL] Port $PORT already in use. Stop the old server or set PORT=8001."
    exit 4
  fi
fi

echo
echo "[5/6] Starting low-memory vLLM server"
echo "Model: $MODEL"
echo "Port: $PORT"
echo

LOG="$WORKDIR/vllm_probe_${PORT}.log"

CUDA_VISIBLE_DEVICES="$GPU_ID" vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --enable-prefix-caching \
  --gpu-memory-utilization 0.25 \
  --max-model-len 1024 \
  --max-num-seqs 1 \
  --max-num-batched-tokens 1024 \
  --enforce-eager \
  > "$LOG" 2>&1 &

SERVER_PID=$!
echo "$SERVER_PID" > "$WORKDIR/vllm_probe_${PORT}.pid"
echo "[5/6] vLLM PID: $SERVER_PID"
echo "[5/6] Log: $LOG"

echo
echo "[6/6] Waiting for /v1/models ..."
READY=0
for i in $(seq 1 120); do
  if curl -s "http://127.0.0.1:${PORT}/v1/models" >/tmp/t11_vllm_models.json 2>/dev/null; then
    READY=1
    break
  fi

  if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    echo "[FAIL] vLLM server exited early. Last 80 log lines:"
    tail -n 80 "$LOG" || true
    exit 5
  fi

  sleep 2
done

if [ "$READY" -ne 1 ]; then
  echo "[FAIL] vLLM did not become ready in time. Last 80 log lines:"
  tail -n 80 "$LOG" || true
  exit 6
fi

echo
echo "[OK] vLLM server is ready."
cat /tmp/t11_vllm_models.json
echo
echo
echo "Keep this WSL terminal open."
echo "Now go to Windows PowerShell and run the T11 real smoke script."
echo
echo "To stop this probe server later:"
echo "  kill \$(cat $WORKDIR/vllm_probe_${PORT}.pid)"
