"""
=============================================================
BUYER POWER SENTIMENT ANALYSIS
Porter's Five Forces — Bargaining Power of Buyers
=============================================================
Analyzes customer reviews for negative sentiment related to:
  - Price sensitivity
  - Missing / lacking features
  - Poor service quality
=============================================================
"""

import os
import warnings
import pandas as pd
import numpy as np
import re
import string
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

try:
    import tensorflow as tf
    from tensorflow.keras.layers import TextVectorization
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("TensorFlow not found — skipping LSTM model.")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix

CSV_PATH = "./data/Customer_Sentiment.csv"

try:
    df = pd.read_csv(CSV_PATH, skipinitialspace=True)
except FileNotFoundError:
    raise FileNotFoundError(f"CSV not found at '{CSV_PATH}'")

df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

REVIEW_COL      = "review_text"
SENTIMENT_COL   = "sentiment"
RATING_COL      = "customer_rating"
RESPONSE_COL    = "response_time_hours"
RESOLVED_COL    = "issue_resolved"

required = [REVIEW_COL, SENTIMENT_COL]
missing  = [c for c in required if c not in df.columns]
if missing:
    for col in missing:
        candidates = [c for c in df.columns if col.split("_")[0] in c]
        if candidates:
            df[col] = df[candidates[0]]

print(f"Loaded {len(df):,} records | Columns: {list(df.columns)}")

def clean_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\d+", " ", text)
    text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

df["clean_review"] = df[REVIEW_COL].apply(clean_text)

encoder = LabelEncoder()
df["sentiment_encoded"] = encoder.fit_transform(df[SENTIMENT_COL].str.lower())
classes = list(encoder.classes_)
print(f"Sentiment classes: {classes}")

NEG_LABEL = next((c for c in classes if "neg" in c), classes[0])
print(f"Using '{NEG_LABEL}' as the negative class")

if TF_AVAILABLE:
    print("\nBuilding LSTM sentiment classifier")
    
    MAX_TOKENS = 5_000
    SEQ_LEN    = 100

    vectorizer = TextVectorization(max_tokens=MAX_TOKENS,
                                   output_sequence_length=SEQ_LEN)
    vectorizer.adapt(df["clean_review"])

    X = vectorizer(df["clean_review"]).numpy()
    y = df["sentiment_encoded"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    num_classes = len(classes)
    output_activation = "sigmoid" if num_classes == 2 else "softmax"
    output_units      = 1         if num_classes == 2 else num_classes
    loss_fn           = ("binary_crossentropy"
                         if num_classes == 2
                         else "sparse_categorical_crossentropy")

    model = tf.keras.Sequential([
        tf.keras.layers.Embedding(MAX_TOKENS, 64, mask_zero=True),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(64, dropout=0.2)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(output_units, activation=output_activation),
    ], name="BuyerPower_LSTM")

    model.compile(loss=loss_fn, optimizer="adam", metrics=["accuracy"])
    model.summary()

    early_stop = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=2, restore_best_weights=True
    )

    history = model.fit(
        X_train, y_train,
        epochs=10,
        batch_size=32,
        validation_data=(X_test, y_test),
        callbacks=[early_stop],
        verbose=1
    )

    loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
    print(f"Test Accuracy: {accuracy:.4f}")
    print(f"Test Loss: {loss:.4f}")

    y_pred_raw = model.predict(X_test, verbose=0)
    if num_classes == 2:
        y_pred = (y_pred_raw > 0.5).astype(int).flatten()
    else:
        y_pred = np.argmax(y_pred_raw, axis=1)

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=classes))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(history.history["accuracy"],   label="Train")
    axes[0].plot(history.history["val_accuracy"], label="Val")
    axes[0].set_title("Model Accuracy"); axes[0].legend()
    axes[1].plot(history.history["loss"],   label="Train")
    axes[1].plot(history.history["val_loss"], label="Val")
    axes[1].set_title("Model Loss"); axes[1].legend()
    fig.tight_layout()
    fig.savefig("training_curves.png", dpi=150)
    plt.close(fig)

    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=classes, yticklabels=classes, ax=ax)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix")
    fig.tight_layout()
    fig.savefig("confusion_matrix.png", dpi=150)
    plt.close(fig)

print("\nBuyer Power Keyword Analysis")

COMPLAINT_THEMES = {
    "Price Sensitivity": [
        "price", "expensive", "cost", "overpriced", "cheap", "afford",
        "discount", "refund", "value", "money", "fee", "charge", "billing",
    ],
    "Lack of Features": [
        "feature", "missing", "option", "functionality", "limited",
        "basic", "outdated", "upgrade", "version", "support", "integration",
        "capability", "unable",
    ],
    "Poor Service Quality": [
        "slow", "delay", "late", "rude", "unhelpful", "dissatisfied",
        "disappointed", "broken", "faulty", "poor", "bad", "terrible",
        "awful", "unacceptable", "complaint", "ignored", "wait", "hours",
    ],
}

ALL_KEYWORDS = [kw for kws in COMPLAINT_THEMES.values() for kw in kws]

def flag_theme(text: str, keywords: list) -> bool:
    return any(f" {kw} " in f" {text} " for kw in keywords)

negative_df = df[df[SENTIMENT_COL].str.lower() == NEG_LABEL].copy()

for theme, kws in COMPLAINT_THEMES.items():
    col = theme.lower().replace(" ", "_")
    negative_df[col] = negative_df["clean_review"].apply(
        lambda t: flag_theme(t, kws)
    )

negative_df["is_buyer_complaint"] = negative_df[
    [t.lower().replace(" ", "_") for t in COMPLAINT_THEMES]
].any(axis=1)

buyer_complaints = negative_df[negative_df["is_buyer_complaint"]].copy()

print(f"Total negative reviews: {len(negative_df):,}")
print(f"Buyer-power complaints found: {len(buyer_complaints):,} "
      f"({len(buyer_complaints)/max(len(negative_df),1)*100:.1f}% of negatives)")

print("\nComplaint Theme Breakdown:")
for theme, kws in COMPLAINT_THEMES.items():
    col   = theme.lower().replace(" ", "_")
    count = negative_df[col].sum()
    pct   = count / max(len(negative_df), 1) * 100
    print(f"  {theme:<25} {count:>5,}  ({pct:.1f}%)")

print("\nTop 15 Words in Buyer Complaints:")
all_words   = " ".join(buyer_complaints["clean_review"])
word_counts = Counter(all_words.split())

STOP = {"the","and","a","to","of","in","is","it","i","was","for","my",
        "that","this","with","but","on","at","not","have","had","be",
        "so","we","they","you","he","she","are","an","as","by","or",
        "its","been","no","just","were","from","me","do","your"}
filtered_counts = {w: c for w, c in word_counts.items() if w not in STOP}
top_words = sorted(filtered_counts.items(), key=lambda x: x[1], reverse=True)[:15]

for word, count in top_words:
    print(f"  {word:<20} {count:>5,}")

print("\nService Quality Metrics (Buyer Complaints):")

if RESPONSE_COL in buyer_complaints.columns:
    rt = pd.to_numeric(buyer_complaints[RESPONSE_COL], errors="coerce")
    print(f"  Avg Response Time   : {rt.mean():.1f} hours")
    print(f"  Median Response Time: {rt.median():.1f} hours")
    print(f"  90th Percentile     : {rt.quantile(0.9):.1f} hours")

if RESOLVED_COL in buyer_complaints.columns:
    res = buyer_complaints[RESOLVED_COL].astype(str).str.lower()
    resolved_pct = res.isin(["yes","true","1"]).mean() * 100
    print(f"\n  Issue Resolution Rate: {resolved_pct:.1f}% resolved")
    print(f"  Breakdown:\n{res.value_counts(normalize=True).mul(100).round(1).to_string()}")

if RATING_COL in buyer_complaints.columns:
    rat = pd.to_numeric(buyer_complaints[RATING_COL], errors="coerce")
    print(f"\n  Avg Rating (complaints): {rat.mean():.2f} / 5")
    print(f"  Avg Rating (all)        : {pd.to_numeric(df[RATING_COL], errors='coerce').mean():.2f} / 5")

PALETTE = {"negative": "#e63946", "neutral": "#457b9d", "positive": "#2a9d8f"}
sns.set_theme(style="whitegrid", palette="muted")

fig, ax = plt.subplots(figsize=(7, 4))
counts = df[SENTIMENT_COL].str.lower().value_counts()
colors = [PALETTE.get(s, "#888") for s in counts.index]
counts.plot(kind="bar", color=colors, ax=ax, edgecolor="white", width=0.6)
ax.set_title("Sentiment Distribution", fontsize=14, fontweight="bold")
ax.set_xlabel(""); ax.set_ylabel("Number of Reviews")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
for p in ax.patches:
    ax.annotate(f"{int(p.get_height()):,}",
                (p.get_x() + p.get_width() / 2, p.get_height()),
                ha="center", va="bottom", fontsize=10)
fig.tight_layout()
fig.savefig("sentiment_distribution.png", dpi=150)
plt.close(fig)

theme_counts = {
    t: negative_df[t.lower().replace(" ", "_")].sum()
    for t in COMPLAINT_THEMES
}
fig, ax = plt.subplots(figsize=(7, 4))
theme_colors = ["#e63946", "#f4a261", "#e9c46a"]
bars = ax.barh(list(theme_counts.keys()), list(theme_counts.values()),
               color=theme_colors, edgecolor="white")
ax.set_title("Buyer Complaint Themes", fontsize=13, fontweight="bold")
ax.set_xlabel("Number of Mentions")
for bar in bars:
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
            f"{int(bar.get_width()):,}", va="center", fontsize=10)
fig.tight_layout()
fig.savefig("complaint_themes.png", dpi=150)
plt.close(fig)

words, freqs = zip(*top_words)
fig, ax = plt.subplots(figsize=(9, 5))
sns.barplot(x=list(freqs), y=list(words), palette="Reds_r", ax=ax)
ax.set_title("Top 15 Words in Buyer Complaints", fontsize=13, fontweight="bold")
ax.set_xlabel("Frequency")
fig.tight_layout()
fig.savefig("top_complaint_words.png", dpi=150)
plt.close(fig)

if RATING_COL in buyer_complaints.columns:
    fig, ax = plt.subplots(figsize=(7, 4))
    rat_data = pd.to_numeric(buyer_complaints[RATING_COL], errors="coerce").dropna()
    sns.histplot(rat_data, bins=5, color="#e63946", edgecolor="white",
                 kde=False, ax=ax)
    ax.set_title("Customer Ratings — Buyer Complaints",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Rating (1-5)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig("ratings_distribution.png", dpi=150)
    plt.close(fig)

if RESPONSE_COL in df.columns:
    fig, ax = plt.subplots(figsize=(7, 4))
    plot_df = df.copy()
    plot_df[RESPONSE_COL] = pd.to_numeric(plot_df[RESPONSE_COL], errors="coerce")
    order = sorted(plot_df[SENTIMENT_COL].str.lower().unique())
    palette = [PALETTE.get(s, "#888") for s in order]
    sns.boxplot(x=SENTIMENT_COL, y=RESPONSE_COL, data=plot_df,
                order=order, palette=palette, ax=ax,
                flierprops=dict(marker="o", alpha=0.4))
    ax.set_title("Response Time by Sentiment",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Sentiment"); ax.set_ylabel("Response Time (hours)")
    fig.tight_layout()
    fig.savefig("response_time_vs_sentiment.png", dpi=150)
    plt.close(fig)

print("\nAnalysis complete. All charts saved.")