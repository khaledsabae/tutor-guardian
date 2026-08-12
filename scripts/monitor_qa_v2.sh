#!/usr/bin/env bash
# Monitor tutor-guardian v2 fine-tune dataset generation.
# Runs from cron every 2h: reports progress, alerts on completion or crash.
# Notifies via desktop notify-send (GUI) + appends to a monitor log.
set -uo pipefail

PROJ="/home/khalednew/projects/tutor-guardian"
DATA="$PROJ/ops/data/qa_dataset_v2.jsonl"
PIDF="$PROJ/ops/data/qa_gen_v2.pid"
GENLOG="$PROJ/ops/data/qa_gen_v2.log"
STATEF="$PROJ/ops/data/.qa_v2_monitor_state"
DONEF="$PROJ/ops/data/.qa_v2_done"
MONLOG="$PROJ/ops/data/qa_v2_monitor.log"
TARGET=4000

# Needed for notify-send to reach the desktop from a cron (no inherited env).
export DISPLAY="${DISPLAY:-:0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"

notify() { # urgency title body
  notify-send -u "$1" "$2" "$3" 2>/dev/null || true
  printf '%s [%s] %s — %s\n' "$(date '+%Y-%m-%d %H:%M')" "$1" "$2" "$3" >> "$MONLOG"
}

# Already finished on a prior run → stay quiet.
[ -f "$DONEF" ] && exit 0

now=$(wc -l < "$DATA" 2>/dev/null || echo 0)
prev=$(cat "$STATEF" 2>/dev/null || echo 0)
echo "$now" > "$STATEF"
delta=$(( now - prev ))
pct=$(( now * 100 / TARGET ))

alive=0
pid=$(cat "$PIDF" 2>/dev/null || echo "")
[ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && alive=1

if [ "$alive" -eq 1 ]; then
  notify normal "📊 المربّي v2: شغّال" "الأمثلة: $now/~$TARGET ($pct%) · +$delta آخر ساعتين"
else
  # Process gone — completed or crashed.
  touch "$DONEF"
  if [ "$now" -ge 3500 ]; then
    notify critical "✅ المربّي v2: خلصت التوليد" "النهائي: $now مثال (~$pct%). الخطوة الجاية: رفع على Kaggle + تشغيل الـfine-tune."
  else
    tailmsg=$(tail -n 1 "$GENLOG" 2>/dev/null | cut -c1-120)
    notify critical "⚠️ المربّي v2: العملية وقفت بدري" "وقفت عند $now/$TARGET ($pct%) — مش مكتملة. آخر سطر: $tailmsg"
  fi
fi
