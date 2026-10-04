#!/usr/bin/env bash
# Day-3 watcher: waits for the fine-tune to finish, then runs the full
# evaluation chain automatically (test metrics + 84% calibration).
cd "$(dirname "$0")"

LOG=train_run.log
EXP=runs/train/leanlens_exp1
DONE=0; DEAD=0

for i in $(seq 1 560); do                       # 560 x 90 s ~ 14 h max
  if grep -q "Results saved to" "$LOG" 2>/dev/null; then DONE=1; break; fi
  mt=$(stat -c %Y "$LOG" 2>/dev/null || echo 0)
  now=$(date +%s)
  if [ -f "$EXP/weights/best.pt" ] && [ $((now - mt)) -gt 1200 ]; then DEAD=1; break; fi
  sleep 90
done

echo "watcher exit: DONE=$DONE DEAD=$DEAD at $(date)"

W="$EXP/weights/best.pt"
[ -f "$W" ] || W="$EXP/weights/last.pt"
echo "evaluating checkpoint: $W"

python val.py --weights "$W" --split test \
  --out "$EXP/test_metrics.json" > day3_val.log 2>&1 \
  && echo "VAL_OK" || echo "VAL_FAILED"

python calibrate_confidence.py --weights "$W" --split test \
  --out "$EXP/calibration.json" > day3_calib.log 2>&1 \
  && echo "CALIB_OK" || echo "CALIB_FAILED"

echo "DAY3_COMPLETE"
