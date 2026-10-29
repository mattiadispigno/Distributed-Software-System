#!/usr/bin/env bash
# Usage: ./set_fault.sh [ok | delay <sec> | hang | down]
mkdir -p control
MODE="${1:-ok}"

case "$MODE" in
  ok)
    echo "ok" > control/fault.txt
    echo "-> Server set to mode: NORMAL (immediate response)"
    ;;
  hang)
    echo "hang" > control/fault.txt
    echo "-> Server set to mode: HANG (never responds, hangs request)"
    ;;
  down)
    echo "down" > control/fault.txt
    echo "-> Server set to mode: DOWN (simulates unreachable server: UNAVAILABLE)"
    ;;
  delay)
    SEC="${2:-3}"
    echo "delay $SEC" > control/fault.txt
    echo "-> Server set to mode: SLOW (waits ${SEC}s before responding)"
    ;;
  *)
    echo "Usage: ./set_fault.sh [ok | delay <sec> | hang | down]"
    exit 1
    ;;
esac
