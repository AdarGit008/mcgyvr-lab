# Source me (bash): STATE, HUB and the requester's REQ_TOKEN for chat.py / tryit.py.
_demo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export STATE="${STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/mcgyvr-demo}"
export HUB="${HUB:-$(cat "$STATE/hub.url" 2>/dev/null || echo http://127.0.0.1:18765)}"
export REQ_TOKEN=$(python3 "$_demo/hubctl.py" user-token requester)
