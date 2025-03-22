import streamlit as st
import pandas as pd
import time
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide", page_title="8U Soccer Tracker")

# -------------------------------
# CONFIGURATION
# -------------------------------
PLAYERS = [
    "Mia", "Cameron", "Charlotte", "Sophia",
    "Joel", "Leo", "Elijah", "Talon",
    "Thomas", "Bryan", "Julian", "Royal", "Sam"
]

FORMATIONS = {
    "3-1-2": {"Defender": 3, "Midfielder": 1, "Striker": 2},
    "2-2-2": {"Defender": 2, "Midfielder": 2, "Striker": 2},
    "2-1-3": {"Defender": 2, "Midfielder": 1, "Striker": 3},
    "1-2-3": {"Defender": 1, "Midfielder": 2, "Striker": 3},
    "3-2-1": {"Defender": 3, "Midfielder": 2, "Striker": 1}
}

STAT_CATEGORIES = ["Goals", "Assists", "Blocks", "Saves"]
HIGHLIGHT_TYPES = ["Goal", "Save", "Foul", "Big Play", "Injury"]

# -------------------------------
# SESSION STATE INITIALIZATION
# -------------------------------
def init_state():
    for key, value in {
        "formation": "3-1-2",
        "positions": {},
        "bench": PLAYERS.copy(),
        "minutes": {p: 0.0 for p in PLAYERS},
        "start_times": {},
        "game_running": False,
        "game_start_time": None,
        "pause_offset": 0,
        "quarter_start_time": None,
        "quarter_offset": 0,
        "current_quarter": 1,
        "score": {"us": 0, "them": 0},
        "goal_log": [],
        "highlights": [],
        "stats": {p: {s: 0 for s in STAT_CATEGORIES} for p in PLAYERS},
        "selecting_position": None,
        "sub_queue": {},
        "undo_stack": [],
        "fatigue_threshold": 12,
        "dark_mode": False,
        "swap_mode": [],
    }.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

def format_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

if st.session_state.game_running:
    st_autorefresh(interval=1000, key="autorefresh")
# -------------------------------
# HEADER BAR
# -------------------------------
st.markdown("## 🏟️ 8U Soccer Game Dashboard")
header_cols = st.columns([2, 2, 2, 2])

with header_cols[0]:
    st.markdown("### ⏱ Game Time")
    if st.session_state.game_start_time:
        elapsed = time.time() - st.session_state.game_start_time - st.session_state.pause_offset
        st.metric("Total", format_time(elapsed))
    else:
        st.metric("Total", "00:00")

with header_cols[1]:
    st.markdown("### 🕐 Quarter")
    st.metric("Now", f"Q{st.session_state.current_quarter}")

with header_cols[2]:
    st.markdown("### 🔢 Score")
    st.metric("Us vs Them", f"{st.session_state.score['us']} - {st.session_state.score['them']}")

with header_cols[3]:
    st.markdown("### 🚨 Fatigue")
    fatigued = []
    for player in st.session_state.start_times:
        total_time = st.session_state.minutes[player]
        if st.session_state.game_running:
            total_time += (time.time() - st.session_state.start_times[player]) / 60.0
        if total_time >= st.session_state.fatigue_threshold:
            fatigued.append(player)
    if fatigued:
        st.error("⚠️ " + ", ".join(fatigued))
    else:
        st.success("✅ All players OK")

st.markdown("---")

# -------------------------------
# GAME CONTROLS
# -------------------------------
game_cols = st.columns([2, 2, 2])
with game_cols[0]:
    if not st.session_state.game_running:
        if st.button("▶️ Start Game"):
            now = time.time()
            if not st.session_state.game_start_time:
                st.session_state.game_start_time = now
                st.session_state.quarter_start_time = now
            else:
                # Resume logic
                paused_duration = now - (st.session_state.game_start_time + st.session_state.pause_offset)
                st.session_state.pause_offset += paused_duration
                st.session_state.quarter_offset += now - (st.session_state.quarter_start_time + st.session_state.quarter_offset)
            for pos, player in st.session_state.positions.items():
                if player:
                    st.session_state.start_times[player] = now
            st.session_state.game_running = True
            st.rerun()
    else:
        if st.button("⏸ Pause Game"):
            now = time.time()
            for player, start in st.session_state.start_times.items():
                st.session_state.minutes[player] += (now - start) / 60.0
            st.session_state.start_times = {}
            st.session_state.game_running = False

with game_cols[1]:
    if st.button("🔚 End Quarter"):
        now = time.time()
        for player, start in st.session_state.start_times.items():
            st.session_state.minutes[player] += (now - start) / 60.0
        st.session_state.start_times = {}
        st.session_state.positions = {}  # clear field
        st.session_state.game_running = False
        st.session_state.current_quarter += 1

with game_cols[2]:
    if st.button("↩️ Undo Last Action"):
        if st.session_state.undo_stack:
            exec(st.session_state.undo_stack.pop())
# -------------------------------
# BUILD FIELD LAYOUT
# -------------------------------
def build_field_layout():
    layout = {"Goalie": ["Goalie"]}
    formation = FORMATIONS[st.session_state.formation]
    for role in ["Defender", "Midfielder", "Striker"]:
        count = formation.get(role, 0)
        layout[role] = [f"{role} {i+1}" if count > 1 else role for i in range(count)]
    return layout

# -------------------------------
# FIELD DISPLAY
# -------------------------------
st.markdown("### 🟢 On-Field Lineup")
layout = build_field_layout()

for line in layout:
    st.markdown(f"#### {line}")
    row = layout[line]
    row_cols = st.columns(len(row))
    for i, pos in enumerate(row):
        with row_cols[i]:
            current = st.session_state.positions.get(pos)
            label = f"{pos}: {current}" if current else f"{pos}: (empty)"
            is_selected = (pos in st.session_state.swap_mode)
            button_style = f"**{label}**" if is_selected else label

            if st.button(button_style, key=f"pos_{pos}"):
                if current:
                    st.session_state.swap_mode.append(pos)
                    if len(st.session_state.swap_mode) == 2:
                        pos1, pos2 = st.session_state.swap_mode
                        player1 = st.session_state.positions[pos1]
                        player2 = st.session_state.positions[pos2]
                        st.session_state.positions[pos1], st.session_state.positions[pos2] = player2, player1
                        st.session_state.swap_mode = []
                        st.session_state.undo_stack.append(
                            f"st.session_state.positions['{pos1}'], st.session_state.positions['{pos2}'] = '{player1}', '{player2}'"
                        )
                        st.rerun()
                else:
                    st.session_state.selecting_position = pos

            # Stat icons under field player
            if current:
                icon_cols = st.columns(len(STAT_CATEGORIES))
                for j, stat in enumerate(STAT_CATEGORIES):
                    with icon_cols[j]:
                        icon = { "Goals": "⚽", "Assists": "🎯", "Blocks": "🛡️", "Saves": "🧤" }[stat]
                        if st.button(f"{icon} ({st.session_state.stats[current][stat]})", key=f"{current}_{stat}"):
                            st.session_state.stats[current][stat] += 1
                            st.session_state.undo_stack.append(
                                f"st.session_state.stats['{current}']['{stat}'] -= 1"
                            )
                            st.rerun()
# -------------------------------
# BENCH + ASSIGN / SUBS
# -------------------------------
st.markdown("### 🪑 Bench")
bench_cols = st.columns(5)
for i, p in enumerate(st.session_state.bench):
    with bench_cols[i % 5]:
        if st.button(p, key=f"bench_{p}"):
            pos = st.session_state.selecting_position
            if pos:
                # Pre-game assign
                if not st.session_state.game_running:
                    previous = st.session_state.positions.get(pos)
                    if previous:
                        st.session_state.bench.append(previous)
                    st.session_state.positions[pos] = p
                    st.session_state.bench.remove(p)
                    st.session_state.selecting_position = None
                    st.rerun()
                else:
                    # Queue sub
                    st.session_state.sub_queue[pos] = p
                    st.session_state.selecting_position = None

# -------------------------------
# APPLY SUBSTITUTIONS
# -------------------------------
if st.session_state.sub_queue:
    st.markdown("### 🔁 Substitution Queue")
    for pos, new_p in st.session_state.sub_queue.items():
        old_p = st.session_state.positions.get(pos)
        st.write(f"{old_p} → {new_p}")
    if st.button("✅ Apply Subs"):
        now = time.time()
        for pos, new_p in st.session_state.sub_queue.items():
            old_p = st.session_state.positions.get(pos)
            if old_p in st.session_state.start_times:
                st.session_state.minutes[old_p] += (now - st.session_state.start_times[old_p]) / 60.0
                del st.session_state.start_times[old_p]
                st.session_state.bench.append(old_p)
            if new_p in st.session_state.bench:
                st.session_state.bench.remove(new_p)
            st.session_state.positions[pos] = new_p
            st.session_state.start_times[new_p] = now
        st.session_state.sub_queue = {}
        st.rerun()

# -------------------------------
# GOAL LOG
# -------------------------------
st.markdown("### 📜 Goal Log")
for entry in reversed(st.session_state.goal_log):
    team = "Us" if entry["team"] == "us" else "Them"
    st.write(f"{entry['time']} - Q{entry['quarter']} - {team} Goal by {entry['player'] or 'N/A'}")

# -------------------------------
# HIGHLIGHTS
# -------------------------------
st.markdown("### 📝 Highlights")
if st.checkbox("➕ Add Highlight"):
    with st.form("highlight_form"):
        type = st.selectbox("Highlight Type", HIGHLIGHT_TYPES)
        note = st.text_input("Notes")
        submitted = st.form_submit_button("Save Highlight")
        if submitted:
            st.session_state.highlights.append({
                "quarter": st.session_state.current_quarter,
                "type": type,
                "note": note,
                "time": datetime.now().strftime("%H:%M:%S")
            })
            st.rerun()

for h in reversed(st.session_state.highlights):
    st.write(f"Q{h['quarter']} - {h['time']} - {h['type']}: {h['note']}")

# -------------------------------
# MINUTES & STATS SUMMARY
# -------------------------------
st.markdown("### 📊 Player Stats Summary")
data = []
now = time.time()
for p in PLAYERS:
    mins = st.session_state.minutes[p]
    if p in st.session_state.start_times:
        mins += (now - st.session_state.start_times[p]) / 60.0
    row = {
        "Player": p,
        "Minutes": round(mins, 1),
    }
    row.update(st.session_state.stats[p])
    data.append(row)

df = pd.DataFrame(data)
st.dataframe(df, hide_index=True)

csv = df.to_csv(index=False).encode("utf-8")
st.download_button("📥 Export CSV", data=csv, file_name="player_stats.csv")

# -------------------------------
# RESET + SETTINGS
# -------------------------------
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    if st.button("🔁 Reset Game"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

with col2:
    with st.expander("⚙️ Settings", expanded=False):
        st.session_state.fatigue_threshold = st.slider(
            "Fatigue Warning Threshold (min)", 5, 30, st.session_state.fatigue_threshold
        )
        st.session_state.dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode)
