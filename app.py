import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime as dt
import os
import json

# -------------------- FILES --------------------
LOG_FILE = "study_logs.csv"
TASK_FILE = "tasks.json"
SETTINGS_FILE = "settings.json"

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Goal Slider - Study Progress Tracker", layout="wide")
st.title("🎯 Goal Slider – Study Progress Tracker")

# -------------------- HELPERS --------------------
def safe_read_csv(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if set(["date", "hours"]).issubset(df.columns):
                return df
        except:
            pass
    return pd.DataFrame(columns=["date", "hours"])

def safe_write_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_timeline(start_date: dt.date, end_date: dt.date) -> pd.DatetimeIndex:
    # inclusive daily range
    return pd.date_range(start=start_date, end=end_date, freq="D")

# -------------------- LOAD DATA --------------------
logs_df = safe_read_csv(LOG_FILE)

settings = load_json(SETTINGS_FILE, {
    "total_hours": 150,
    "start_date": str(dt.date.today()),
    "exam_date": str(dt.date.today() + dt.timedelta(days=30))
})

tasks_state = load_json(TASK_FILE, {"tasks": []})  # [{"title": "...", "done": False}]

# -------------------- SIDEBAR: SETTINGS --------------------
st.sidebar.header("⚙️ Goal Settings")

today = dt.date.today()

total_hours = st.sidebar.number_input(
    "Total Target Hours",
    min_value=1,
    value=int(settings.get("total_hours", 150)),
    step=1
)

start_date = st.sidebar.date_input(
    "Start Date (when you begin tracking)",
    value=dt.date.fromisoformat(settings.get("start_date", str(today)))
)

exam_date = st.sidebar.date_input(
    "Exam Date",
    value=dt.date.fromisoformat(settings.get("exam_date", str(today + dt.timedelta(days=30))))
)

# ----- validations -----
if exam_date <= start_date:
    st.sidebar.error("❗ Exam Date must be AFTER Start Date.")
    st.stop()

total_days = (exam_date - start_date).days + 1
days_left = (exam_date - today).days

if days_left < 0:
    st.sidebar.error("❗ Exam date is in the past. Please select a future date.")
    st.stop()

st.sidebar.write(f"📌 **Total Days (Plan):** {total_days}")
st.sidebar.write(f"⏳ **Days Left:** {days_left}")

# Save settings
if st.sidebar.button("💾 Save Settings"):
    save_json(SETTINGS_FILE, {
        "total_hours": int(total_hours),
        "start_date": str(start_date),
        "exam_date": str(exam_date)
    })
    st.sidebar.success("Settings saved!")

st.sidebar.markdown("---")

# Reset everything
if st.sidebar.button("🧹 Reset EVERYTHING (logs + tasks + settings)"):
    for f in [LOG_FILE, TASK_FILE, SETTINGS_FILE]:
        if os.path.exists(f):
            os.remove(f)
    st.sidebar.success("Reset done. Please refresh the page (R).")
    st.stop()

# -------------------- ADD HOURS --------------------
st.subheader("➕ Add Study Hours")

c1, c2, c3 = st.columns([1.2, 1, 1])

with c1:
    log_date = st.date_input("Date", value=today, key="log_date")

with c2:
    hours_today = st.number_input("Hours", min_value=0.0, value=0.0, step=0.5, key="log_hours")

with c3:
    if st.button("✅ Add Hours"):
        if hours_today <= 0:
            st.warning("Enter hours > 0")
        else:
            new_row = pd.DataFrame([{"date": str(log_date), "hours": float(hours_today)}])
            logs_df = pd.concat([logs_df, new_row], ignore_index=True)
            safe_write_csv(logs_df, LOG_FILE)
            st.success("Hours added!")

st.markdown("---")

# -------------------- AGGREGATE LOGS (FIXED) --------------------
# ✅ This block guarantees columns: ['day','hours'] so graph never breaks
if len(logs_df) > 0:
    logs_df["date"] = pd.to_datetime(logs_df["date"], errors="coerce")
    logs_df = logs_df.dropna(subset=["date"])
    logs_df["hours"] = pd.to_numeric(logs_df["hours"], errors="coerce").fillna(0.0)

    # ✅ Always create day column first
    logs_df["day"] = logs_df["date"].dt.date

    daily = (
        logs_df.groupby("day", as_index=False)["hours"]
        .sum()
        .sort_values("day")
        .reset_index(drop=True)
    )
else:
    daily = pd.DataFrame(columns=["day", "hours"])

total_done = float(daily["hours"].sum()) if len(daily) else 0.0
progress_percent = (total_done / total_hours) * 100 if total_hours > 0 else 0.0

ideal_per_day = total_hours / total_days
if days_left > 0:
    required_daily_now = max((total_hours - total_done) / days_left, 0.0)
else:
    required_daily_now = max(total_hours - total_done, 0.0)

# -------------------- METRICS --------------------
m1, m2, m3, m4 = st.columns(4)
m1.metric("🎯 Target", f"{total_hours} hrs")
m2.metric("🔥 Completed", f"{total_done:.1f} hrs")
m3.metric("📈 Progress", f"{progress_percent:.1f}%")
m4.metric("⏳ Required / Day", f"{required_daily_now:.2f} hrs/day")

# # -------------------- GRAPH (ACTUAL vs IDEAL) --------------------
# st.markdown("---")
# st.subheader("📊 Progress Graph (Actual vs Ideal)")

# graph_end = min(today, exam_date)  # don't go beyond exam date
# timeline = make_timeline(start_date, graph_end)

# # Map day -> hours (daily is already day-wise)
# actual_map = {}
# if len(daily):
#     actual_map = {r["day"]: float(r["hours"]) for _, r in daily.iterrows()}

# # Build series aligned to timeline
# actual_daily = [actual_map.get(d.date(), 0.0) for d in timeline]
# actual_cum = pd.Series(actual_daily).cumsum().tolist()

# # Ideal cumulative on calendar days
# days_from_start = [(d.date() - start_date).days for d in timeline]  # 0..N
# ideal_cum = [(x + 1) * ideal_per_day for x in days_from_start]

# fig, ax = plt.subplots(figsize=(12, 4))
# ax.plot(timeline, actual_cum, label="Actual (Cumulative)", linewidth=3)
# ax.plot(timeline, ideal_cum, label="Ideal (Cumulative)", linestyle="dashed")
# ax.set_xlabel("Date")
# ax.set_ylabel("Hours")
# ax.legend()
# st.pyplot(fig)


st.markdown("---")
st.subheader("📊 Progress Graph (Actual vs Ideal)")

graph_end = min(today, exam_date)

# timeline (inclusive)
timeline = pd.date_range(start=start_date, end=graph_end, freq="D")

# day -> hours map
actual_map = {r["day"]: float(r["hours"]) for _, r in daily.iterrows()} if len(daily) else {}

# daily hours aligned with timeline
actual_daily = [actual_map.get(d.date(), 0.0) for d in timeline]
actual_cum = pd.Series(actual_daily).cumsum()

# ideal cumulative aligned
ideal_per_day = total_hours / total_days
ideal_cum = pd.Series([(i + 1) * ideal_per_day for i in range(len(timeline))])

# ✅ baseline point so line always visible
baseline_date = pd.to_datetime(start_date) - pd.Timedelta(days=1)
timeline_plot = pd.DatetimeIndex([baseline_date]).append(timeline)

# ✅ pandas v2+ compatible (no Series.append)
actual_cum_plot = pd.concat([pd.Series([0.0]), actual_cum.reset_index(drop=True)], ignore_index=True)
ideal_cum_plot  = pd.concat([pd.Series([0.0]), ideal_cum.reset_index(drop=True)], ignore_index=True)

fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(timeline_plot, actual_cum_plot, label="Actual (Cumulative)", linewidth=3, marker="o")
ax.plot(timeline_plot, ideal_cum_plot, label="Ideal (Cumulative)", linestyle="dashed", marker="o")

ax.set_xlabel("Date")
ax.set_ylabel("Hours")
ax.legend()
ax.set_xlim(timeline_plot.min(), timeline_plot.max())

st.pyplot(fig)




# -------------------- LOGS TABLE + DELETE DATE --------------------
st.markdown("---")
st.subheader("🗂️ Your Study Logs (Daily Total)")

if len(daily) == 0:
    st.info("No logs yet. Add hours above.")
else:
    show_df = daily.copy()
    show_df["day"] = pd.to_datetime(show_df["day"]).dt.strftime("%Y-%m-%d")
    st.dataframe(show_df, use_container_width=True)

    d1, d2 = st.columns([1.2, 2])
    with d1:
        delete_date = st.date_input("Delete logs for date", value=today, key="delete_date")
    with d2:
        if st.button("🗑️ Delete This Date Logs"):
            raw = safe_read_csv(LOG_FILE)
            if len(raw) > 0:
                raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
                raw = raw.dropna(subset=["date"])
                raw = raw[raw["date"].dt.date != delete_date]
                raw["date"] = raw["date"].dt.strftime("%Y-%m-%d")
                safe_write_csv(raw, LOG_FILE)
                st.success("Deleted! App will refresh now.")
                st.stop()

# -------------------- SYLLABUS + MARKS PREDICTION --------------------
st.markdown("---")
st.subheader("📘 Syllabus Completion & Marks Prediction")

syllabus = st.slider("Syllabus Completed (%)", 0, 100, 40)
pyq = st.slider("PYQ Practice (%)", 0, 100, 50)

predicted_marks = (syllabus * 0.6) + (pyq * 0.4)
st.success(f"📌 Predicted Score: **{predicted_marks:.1f}%**")

# -------------------- TASKS (PERSISTENT) --------------------
st.markdown("---")
st.subheader("📋 Tasks / Topics Checklist (Saved)")

new_task = st.text_input("Add a new task (press Enter)", "")

if new_task.strip():
    existing = {t["title"].strip().lower() for t in tasks_state["tasks"]}
    if new_task.strip().lower() not in existing:
        tasks_state["tasks"].append({"title": new_task.strip(), "done": False})
        save_json(TASK_FILE, tasks_state)
        st.success("Task added! ✅")
        st.stop()
    else:
        st.warning("Task already exists.")

if len(tasks_state["tasks"]) == 0:
    st.info("No tasks yet. Add a task above.")
else:
    changed = False
    for i, t in enumerate(tasks_state["tasks"]):
        key = f"task_{i}"
        checked = st.checkbox(t["title"], value=bool(t.get("done", False)), key=key)
        if checked != bool(t.get("done", False)):
            tasks_state["tasks"][i]["done"] = checked
            changed = True

    cA, cB = st.columns(2)

    with cA:
        if st.button("💾 Save Task Status"):
            save_json(TASK_FILE, tasks_state)
            st.success("Saved!")

    with cB:
        if st.button("🧹 Remove Completed Tasks"):
            tasks_state["tasks"] = [t for t in tasks_state["tasks"] if not t.get("done", False)]
            save_json(TASK_FILE, tasks_state)
            st.success("Removed completed tasks!")
            st.stop()

    # auto-save if changed
    if changed:
        save_json(TASK_FILE, tasks_state)
