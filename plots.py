import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# results.csv is in the root folder
csv_path = Path("results.csv")

# Output folder
out_dir = Path("poster_exports")
out_dir.mkdir(exist_ok=True)

# Read CSV
df = pd.read_csv(csv_path)
df.columns = df.columns.str.strip()

# Create epoch column if missing
if "epoch" not in df.columns:
    df["epoch"] = range(1, len(df) + 1)

# Required YOLO columns
precision_col = "metrics/precision(B)"
recall_col = "metrics/recall(B)"
map50_col = "metrics/mAP50(B)"
map5095_col = "metrics/mAP50-95(B)"

# Get best values
best_precision = df[precision_col].max()
best_recall = df[recall_col].max()
best_map50 = df[map50_col].max()
best_map5095 = df[map5095_col].max()

final_precision = df[precision_col].iloc[-1]
final_recall = df[recall_col].iloc[-1]
final_map50 = df[map50_col].iloc[-1]
final_map5095 = df[map5095_col].iloc[-1]

# ----------------------------
# Poster-friendly combined plot
# ----------------------------
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# 1) Precision and Recall
axes[0].plot(df["epoch"], df[precision_col], linewidth=2.8, label="Precision")
axes[0].plot(df["epoch"], df[recall_col], linewidth=2.8, label="Recall")
axes[0].set_title("Precision and Recall", fontsize=16, fontweight="bold")
axes[0].set_xlabel("Epoch", fontsize=12)
axes[0].set_ylabel("Score", fontsize=12)
axes[0].grid(True, alpha=0.3)
axes[0].legend(fontsize=11)

# 2) mAP@0.5
axes[1].plot(df["epoch"], df[map50_col], linewidth=3)
axes[1].set_title("mAP@0.5", fontsize=16, fontweight="bold")
axes[1].set_xlabel("Epoch", fontsize=12)
axes[1].set_ylabel("Score", fontsize=12)
axes[1].grid(True, alpha=0.3)

# 3) mAP@0.5:0.95
axes[2].plot(df["epoch"], df[map5095_col], linewidth=3)
axes[2].set_title("mAP@0.5:0.95", fontsize=16, fontweight="bold")
axes[2].set_xlabel("Epoch", fontsize=12)
axes[2].set_ylabel("Score", fontsize=12)
axes[2].grid(True, alpha=0.3)

fig.suptitle(
    "YOLOv8 Fire/Smoke Detection Performance",
    fontsize=22,
    fontweight="bold",
    y=1.05
)

plt.tight_layout()

plt.savefig(out_dir / "yolov8_poster_performance_curves.png", dpi=600, bbox_inches="tight")
plt.savefig(out_dir / "yolov8_poster_performance_curves.svg", bbox_inches="tight")
plt.close()

# ----------------------------
# Metric summary card as image
# ----------------------------
fig, ax = plt.subplots(figsize=(10, 4))
ax.axis("off")

table_data = [
    ["Precision", f"{best_precision:.4f}", f"{final_precision:.4f}"],
    ["Recall", f"{best_recall:.4f}", f"{final_recall:.4f}"],
    ["mAP@0.5", f"{best_map50:.4f}", f"{final_map50:.4f}"],
    ["mAP@0.5:0.95", f"{best_map5095:.4f}", f"{final_map5095:.4f}"],
]

table = ax.table(
    cellText=table_data,
    colLabels=["Metric", "Best Value", "Final Epoch"],
    cellLoc="center",
    colLoc="center",
    loc="center"
)

table.auto_set_font_size(False)
table.set_fontsize(14)
table.scale(1, 2)

for (row, col), cell in table.get_celld().items():
    cell.set_linewidth(0.8)
    if row == 0:
        cell.set_text_props(weight="bold", color="white")
        cell.set_facecolor("#0B2E59")
    else:
        cell.set_facecolor("#F7FBFF")

ax.set_title(
    "YOLOv8 Detection Metric Summary",
    fontsize=20,
    fontweight="bold",
    pad=20
)

plt.savefig(out_dir / "yolov8_metric_summary_card.png", dpi=600, bbox_inches="tight")
plt.savefig(out_dir / "yolov8_metric_summary_card.svg", bbox_inches="tight")
plt.close()

print("Saved poster-ready files in:", out_dir.resolve())
print("\nBest values:")
print(f"Precision: {best_precision:.4f}")
print(f"Recall: {best_recall:.4f}")
print(f"mAP@0.5: {best_map50:.4f}")
print(f"mAP@0.5:0.95: {best_map5095:.4f}")