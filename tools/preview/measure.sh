#!/bin/zsh
# CPU used by headless Chrome drawing one scene: CPU-seconds per second, summed over its processes.
# usage: measure.sh "level=2&agents=1" [seconds]
Q="$1"; SECS=${2:-8}
DIR=$(mktemp -d)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --user-data-dir="$DIR" \
  --window-size=1728,1117 --force-device-scale-factor=2 --no-first-run --disable-extensions \
  "http://localhost:8765/${PAGE:-}?bare&${GLASS:-glass}&$Q" >/dev/null 2>&1 &
PID=$!
sleep 4
tree() { local p=$1; echo $p; for c in $(pgrep -P $p); do tree $c; done }
cpu() { local t=0; for p in $(tree $PID); do s=$(ps -o time= -p $p 2>/dev/null | awk -F: '{ if (NF==3) print $1*3600+$2*60+$3; else print $1*60+$2 }'); t=$(echo "$t + ${s:-0}" | bc); done; echo $t; }
A=$(cpu); sleep $SECS; B=$(cpu)
kill $PID 2>/dev/null; sleep 0.5; pkill -f "$DIR" 2>/dev/null; rm -rf "$DIR"
printf "%-28s %5.0f%% of one core\n" "$Q" $(echo "($B - $A) * 100 / $SECS" | bc -l)
