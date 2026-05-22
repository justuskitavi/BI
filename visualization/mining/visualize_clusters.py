import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "outputs" / "cluster_formation_customer_clusters.csv"
OUTPUT_PATH = ROOT / "outputs" / "customer_clusters_visualization.png"

def generate_cluster_plot():
    if not DATA_PATH.exists():
        print(f"Error: {DATA_PATH} not found. Run the mining scripts first.")
        return

    # Load data
    df = pd.read_csv(DATA_PATH)
    
    # Select features used for clustering (adjust based on your actual columns)
    # Based on 03_cluster_formation logic: recency, frequency, monetary, profit, discount, breadth
    features = ['recency', 'orders', 'sales', 'profit', 'avg_discount', 'unique_categories']
    
    # Filter only available columns
    available_features = [f for f in features if f in df.columns]
    X = df[available_features]
    clusters = df['cluster']
    labels = df['business_label'] if 'business_label' in df.columns else clusters

    # Standardize and PCA
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    pca = PCA(n_components=2)
    components = pca.fit_transform(X_scaled)
    
    pca_df = pd.DataFrame(data=components, columns=['PC1', 'PC2'])
    pca_df['Cluster'] = labels

    # Plot
    plt.figure(figsize=(12, 8))
    sns.set_style("whitegrid")
    
    plot = sns.scatterplot(
        data=pca_df, 
        x='PC1', 
        y='PC2', 
        hue='Cluster', 
        palette='viridis', 
        alpha=0.7, 
        edgecolor='w', 
        s=100
    )
    
    plt.title('Customer Segments Visualization (PCA Projection)', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Principal Component 1 (Size/Frequency)', fontsize=12)
    plt.ylabel('Principal Component 2 (Profitability/Discount)', fontsize=12)
    plt.legend(title='Customer Segments', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()

    # Save
    plt.savefig(OUTPUT_PATH, dpi=300)
    print(f"✅ Cluster visualization saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_cluster_plot()
