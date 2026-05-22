# ==============================================================================
# PIPELINE: FROM DATA COLLECTION TO INSIGHT GENERATION AND VISUALIZATION
# ==============================================================================
# This script outlines the 8-stage pipeline for Sentiment Analysis as per 
# General Procedures for Business Intelligence and Porter's Five Forces Analysis.

import os
import re
import string
import pandas as pd
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import seaborn as sns
from tensorflow.keras.layers import TextVectorization
from sklearn.model_selection import train_test_split

# Suppress TensorFlow/CUDA warnings for cleaner output in reports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# ------------------------------------------------------------------------------
# 1. DATA ACQUISITION
# ------------------------------------------------------------------------------
# Collect relevant text data from customer review platforms.
# Using 'skipinitialspace' to handle potential formatting errors in scraped data.
df = pd.read_csv("./data/Customer_Sentiment.csv", skipinitialspace=True)
df.columns = df.columns.str.strip()  # Remove trailing spaces from headers


# ------------------------------------------------------------------------------
# 2. DATA PREPROCESSING (using tf.strings)
# ------------------------------------------------------------------------------
# Cleaning the text data by removing noise and special characters.
def clean_text_pipeline(text_tensor):
    lowercase = tf.strings.lower(text_tensor)
    # Remove HTML tags and punctuation using regex
    clean = tf.strings.regex_replace(lowercase, "<.*?>", "")
    clean = tf.strings.regex_replace(clean, f"[{re.escape(string.punctuation)}]", "")
    return clean

# Applying stripping to handle specific dataset whitespace inconsistencies
df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
df['clean_review'] = df['review_text'].apply(lambda x: clean_text_pipeline(tf.constant(x)).numpy().decode())


# ------------------------------------------------------------------------------
# 3. TEXT REPRESENTATION (using tf.keras.layers.TextVectorization)
# ------------------------------------------------------------------------------
# Convert preprocessed text into numerical tensors for deep learning.
vectorizer = TextVectorization(max_tokens=5000, output_sequence_length=100)
vectorizer.adapt(df['clean_review'].values)

X = vectorizer(df['clean_review']).numpy() # Convert to numpy for train_test_split compatibility
y = pd.get_dummies(df['sentiment']).values # One-hot encoding labels


# ------------------------------------------------------------------------------
# 4. MODEL BUILDING (using tf.keras)
# ------------------------------------------------------------------------------
# Constructing a neural network model using LSTM (RNN) for Sentiment Analysis.
model = tf.keras.Sequential([
    tf.keras.layers.Embedding(5000, 64, input_length=100),
    tf.keras.layers.LSTM(64),
    tf.keras.layers.Dense(32, activation='relu'),
    tf.keras.layers.Dense(y.shape[1], activation='softmax')
])


# ------------------------------------------------------------------------------
# 5. MODEL TRAINING (using model.fit())
# ------------------------------------------------------------------------------
# Training the classification model on labeled customer sentiment data.
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
# model.fit(X_train, y_train, epochs=5, batch_size=32)


# ------------------------------------------------------------------------------
# 6. MODEL EVALUATION (using model.evaluate())
# ------------------------------------------------------------------------------
# Assess the performance using accuracy and loss metrics.
# loss, accuracy = model.evaluate(X_test, y_test)
# print(f"Test Accuracy: {accuracy:.4f}")


# ------------------------------------------------------------------------------
# 7. PREDICTION AND INSIGHT GENERATION (using model.predict())
# ------------------------------------------------------------------------------
# Analyze new reviews to extract sentiment scores and strategic intelligence.
predictions = model.predict(X_test[:5])
# Insight: Identifying high-dissatisfaction areas affecting 'Buyer Power'.
negative_impact = df[df['sentiment'] == 'negative']['response_time_hours'].mean()
print(f"Strategic Insight - Avg Response Time for Negative Reviews: {negative_impact:.2f} hrs")


# ------------------------------------------------------------------------------
# 8. VISUALIZATION AND REPORTING (using Matplotlib & Seaborn)
# ------------------------------------------------------------------------------
# Presenting findings in an actionable format for Porter's Five Forces framework.
plt.figure(figsize=(10, 6))
sns.boxplot(x='sentiment', y='response_time_hours', data=df)
plt.title("Bargaining Power of Buyers: Sentiment vs. Response Latency")
plt.savefig("analysis_report_plot.png")
print("Visualizations saved: analysis_report_plot.png")
