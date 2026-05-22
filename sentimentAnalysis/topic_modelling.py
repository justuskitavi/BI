import os, re, string, sys, time, warnings

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

import gensim
from gensim import corpora
from gensim.models import LdaModel
from gensim.parsing.preprocessing import (
    STOPWORDS, remove_stopwords, strip_punctuation, strip_numeric,
    strip_multiple_whitespaces,
)

try:
    import pyLDAvis
    import pyLDAvis.gensim_models as gensimvis
    HAS_PYLDAVIS = True
except ImportError:
    HAS_PYLDAVIS = False

def banner(title: str):
    print(f"\n--- {title} ---")

def info(msg: str):
    print(f"INFO: {msg}")

def ok(msg: str):
    print(f"OK: {msg}")

def warn(msg: str):
    print(f"WARNING: {msg}", file=sys.stderr)

def progress(current: int, total: int, label: str = "", width: int = 30):
    pct   = current / total
    filled = int(width * pct)
    bar   = "█" * filled + "░" * (width - filled)
    print(f"\r[{bar}] {pct:5.1%}  {label:<30}", end="", flush=True)
    if current == total:
        print()

banner("Configuration")

DATA_PATH     = "./data/Customer_Sentiment.csv"
OUTPUT_DIR    = "./outputs"
N_TOPICS      = 8
TOP_N_WORDS   = 12
LDA_PASSES    = 15
LDA_ITERATIONS= 400
RANDOM_STATE  = 42

os.makedirs(OUTPUT_DIR, exist_ok=True)

COMPETITOR_SEEDS = [
    "competitor", "competition", "rival", "alternative", "switch", "switched",
    "switching", "left", "moved", "migrated", "cancel", "cancelled", "canceled",
    "unsubscribe", "churn",
    "ai", "automation", "chatbot", "bot", "self-service", "app", "platform",
    "digital", "online", "api", "integration",
    "cheaper", "cheaper", "discount", "free", "trial", "promo", "offer",
    "deal", "price", "pricing", "cost", "expensive", "affordable",
    "slow", "delay", "delayed", "wait", "waiting", "unresponsive", "ignored",
    "unreliable", "broken", "bug", "error", "crash", "down", "outage",
    "refund", "billing", "overcharged",
]

PAIN_POINT_SEEDS = [
    "problem", "issue", "complaint", "frustrated", "frustrating", "terrible",
    "awful", "poor", "bad", "worst", "horrible", "disappointing", "disappointed",
    "useless", "broken", "fix", "difficult", "confusing", "complicated",
]

info(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
info(f"Number of topics: {N_TOPICS}")
info(f"LDA passes: {LDA_PASSES}")
ok("Configuration loaded.")

banner("Loading Data")

info(f"Reading: {DATA_PATH}")
t0 = time.time()

try:
    df = pd.read_csv(DATA_PATH, skipinitialspace=True)
except FileNotFoundError:
    sys.exit(f"ERROR: File not found: {DATA_PATH}")

df.columns = df.columns.str.strip()
df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

ok(f"Loaded {len(df):,} rows ({time.time()-t0:.1f}s)")

if "review_text" not in df.columns:
    candidates = [c for c in df.columns if "review" in c.lower() or "text" in c.lower() or "comment" in c.lower()]
    if candidates:
        df = df.rename(columns={candidates[0]: "review_text"})
    else:
        sys.exit("ERROR: Cannot find a review text column.")

missing = df["review_text"].isna().sum()
if missing:
    df = df.dropna(subset=["review_text"]).reset_index(drop=True)

banner("Text Preprocessing")

info("Cleaning reviews...")

EXTRA_STOPS = {
    "would", "could", "should", "also", "really", "very", "just", "get",
    "got", "said", "one", "two", "three", "us", "im", "ive", "dont",
    "didnt", "wasnt", "isnt", "cant", "wont", "via", "pm", "am",
}
STOP_WORDS = STOPWORDS | EXTRA_STOPS

def preprocess(text: str) -> list[str]:
    text = str(text).lower()
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"http\S+", "", text)
    text = strip_punctuation(text)
    text = strip_numeric(text)
    text = strip_multiple_whitespaces(text)
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    return tokens

total = len(df)
tokenised = []
for i, text in enumerate(df["review_text"], 1):
    tokenised.append(preprocess(text))
    if i % 200 == 0 or i == total:
        progress(i, total, label=f"preprocessed {i:,}/{total:,}")

df["tokens"] = tokenised
ok("Preprocessing complete.")

banner("Building Dictionary & Corpus")

info("Building dictionary...")
dictionary = corpora.Dictionary(tokenised)
dictionary.filter_extremes(no_below=3, no_above=0.60)

info("Converting to Bag-of-Words corpus...")
corpus = [dictionary.doc2bow(tokens) for tokens in tokenised]
ok(f"Corpus ready: {len(corpus):,} documents.")

banner("Training LDA Topic Model")

info(f"Training LDA with {N_TOPICS} topics...")
t0 = time.time()
lda_model = LdaModel(
    corpus=corpus,
    id2word=dictionary,
    num_topics=N_TOPICS,
    passes=LDA_PASSES,
    iterations=LDA_ITERATIONS,
    random_state=RANDOM_STATE,
    alpha="auto",
    eta="auto",
    eval_every=None,
    minimum_probability=0.0,
)
ok(f"LDA training finished in {time.time() - t0:.1f}s.")

banner("Extracting Topics")

rows = []
for topic_id in range(N_TOPICS):
    terms = lda_model.show_topic(topic_id, topn=TOP_N_WORDS)
    keywords = [w for w, _ in terms]
    weights  = [round(p, 4) for _, p in terms]
    rows.append({"topic_id": topic_id, "keywords": keywords, "weights": weights})

topics_df = pd.DataFrame(rows)

COMPETITOR_SET  = set(COMPETITOR_SEEDS)
PAIN_POINT_SET  = set(PAIN_POINT_SEEDS)

def auto_label(keywords: list[str]) -> str:
    kw_set = set(keywords)
    comp_hit  = kw_set & COMPETITOR_SET
    pain_hit  = kw_set & PAIN_POINT_SET
    if comp_hit and pain_hit:
        return f"Competitor Pain [{', '.join(list(comp_hit)[:3])}]"
    if comp_hit:
        return f"Competitor/Alt [{', '.join(list(comp_hit)[:3])}]"
    if pain_hit:
        return f"Pain Point [{', '.join(list(pain_hit)[:3])}]"
    return  "General Feedback"

topics_df["label"] = topics_df["keywords"].apply(auto_label)

print(f"\n{'Topic':<6} {'Label':<45} {'Top Keywords'}")
for _, row in topics_df.iterrows():
    kw_str = ", ".join(row["keywords"][:8])
    print(f"T{row['topic_id']:<5} {row['label']:<45} {kw_str}")

kw_rows = []
for _, row in topics_df.iterrows():
    for kw, wt in zip(row["keywords"], row["weights"]):
        kw_rows.append({"topic_id": row["topic_id"], "label": row["label"],
                        "keyword": kw, "weight": wt})
pd.DataFrame(kw_rows).to_csv(os.path.join(OUTPUT_DIR, "lda_topic_keywords.csv"), index=False)

banner("Assigning Topics")

dominant_topics, topic_probs = [], []
for i, bow in enumerate(corpus, 1):
    dist = lda_model.get_document_topics(bow, minimum_probability=0.0)
    dist_sorted = sorted(dist, key=lambda x: x[1], reverse=True)
    dominant_topics.append(dist_sorted[0][0])
    topic_probs.append(round(dist_sorted[0][1], 4))
    if i % 200 == 0 or i == len(corpus):
        progress(i, len(corpus), label=f"assigned {i:,}/{len(corpus):,}")

df["dominant_topic"]    = dominant_topics
df["topic_probability"] = topic_probs
df["topic_label"]       = df["dominant_topic"].map(topics_df.set_index("topic_id")["label"])

topic_counts = df["dominant_topic"].value_counts().sort_index()
df.to_csv(os.path.join(OUTPUT_DIR, "lda_doc_topic_assignments.csv"), index=False)

banner("Competitive Analysis")

def count_seed_hits(tokens: list[str], seed_set: set) -> list[str]:
    return [t for t in tokens if t in seed_set]

df["competitor_hits"] = df["tokens"].apply(lambda t: count_seed_hits(t, COMPETITOR_SET))
df["pain_hits"]       = df["tokens"].apply(lambda t: count_seed_hits(t, PAIN_POINT_SET))
df["has_competitor"]  = df["competitor_hits"].apply(bool)
df["has_pain"]        = df["pain_hits"].apply(bool)

info(f"Competitor mentions: {df['has_competitor'].sum():,}")
info(f"Pain point mentions: {df['has_pain'].sum():,}")

from collections import Counter
all_comp_hits = Counter(h for hits in df["competitor_hits"] for h in hits)
all_pain_hits = Counter(h for hits in df["pain_hits"]       for h in hits)

banner("Generating Visualisations")

PALETTE = "Blues_d"
sns.set_theme(style="whitegrid", font_scale=0.95)

def savefig(name: str):
    path = os.path.join(OUTPUT_DIR, name)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    ok(f"Saved: {name}")

fig, ax = plt.subplots(figsize=(10, 5))
short_labels = [f"T{i}\n{topics_df.loc[topics_df['topic_id']==i,'label'].values[0][:25]}"
                for i in range(N_TOPICS)]
ax.bar(short_labels, [topic_counts.get(i, 0) for i in range(N_TOPICS)],
              color=sns.color_palette("Blues_d", N_TOPICS))
ax.set_title("Topic Prominence", fontsize=13)
ax.set_ylabel("Review Count")
savefig("lda_topic_distribution.png")

top_comp = pd.DataFrame(all_comp_hits.most_common(15), columns=["keyword", "count"])
if not top_comp.empty:
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=top_comp, x="count", y="keyword", palette="Reds_d", ax=ax)
    ax.set_title("Top Competitor Keywords", fontsize=13)
    savefig("lda_competitor_mentions.png")

if "sentiment" in df.columns:
    sent_counts = df.groupby(["dominant_topic", "sentiment"]).size().reset_index(name="count")
    pivot = sent_counts.pivot(index="dominant_topic", columns="sentiment", values="count").fillna(0)
    pivot.plot(kind="bar", stacked=True, colormap="RdYlGn", edgecolor="white", linewidth=0.5)
    plt.title("Sentiment by Topic")
    savefig("lda_sentiment_by_topic.png")

if "customer_rating" in df.columns:
    avg_rating = df.groupby("dominant_topic")["customer_rating"].mean()
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = ["#d73027" if r < 3 else "#4dac26" for r in avg_rating]
    ax.bar([f"T{i}" for i in avg_rating.index], avg_rating.values, color=colors)
    ax.set_title("Average Rating per Topic")
    ax.set_ylim(0, 5.5)
    savefig("lda_rating_by_topic.png")

if "response_time_hours" in df.columns:
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.boxplot(data=df, x="dominant_topic", y="response_time_hours", palette="coolwarm", ax=ax)
    ax.set_title("Response Time per Topic")
    savefig("lda_response_time_by_topic.png")

if HAS_PYLDAVIS:
    try:
        vis_data = gensimvis.prepare(lda_model, corpus, dictionary, sort_topics=False)
        pyLDAvis.save_html(vis_data, os.path.join(OUTPUT_DIR, "lda_vis.html"))
        ok("Interactive explorer saved.")
    except Exception as e:
        warn(f"pyLDAvis failed: {e}")

banner("Analysis Complete")
print(f"Total reviews: {len(df):,}")
print(f"Topics: {N_TOPICS}")
print(f"Competitor mentions: {df['has_competitor'].sum():,}")
print(f"Pain point mentions: {df['has_pain'].sum():,}")
