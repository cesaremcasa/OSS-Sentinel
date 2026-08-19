import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

# --- CONFIGURAÇÃO DE CAMINHOS E ESTILO ---
BASE_DIR = Path(__file__).resolve().parent.parent
ENRICHED_DIR = BASE_DIR / "data/enriched"
ANALYSIS_DIR = BASE_DIR / "data/analysis"
PLOTS_DIR = ANALYSIS_DIR / "plots"

# Garante pastas de saída
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Estilo profissional para plots
sns.set_theme(style="whitegrid")

SENTIMENT_PAIN = {"positive": 0.0, "neutral": 0.5, "negative": 1.0}
URGENCY_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 3.0}


def calculate_pain_index(sentiment: str, urgency: str) -> float:
    """Return an intuitive 0..3 pain score, where larger values are worse."""
    return SENTIMENT_PAIN.get(str(sentiment).strip().lower(), 0.5) * URGENCY_WEIGHT.get(
        str(urgency).strip().lower(), 1.0
    )


def _normalized_label_tokens(value) -> list[str]:
    return [token.strip().lower() for token in str(value or "").split(",") if token.strip()]

def load_and_clean_data(enriched_dir=ENRICHED_DIR):
    """Carrega dados, ignora POCs e adiciona source_repo."""
    dfs = []
    files = list(Path(enriched_dir).glob("enriched_*.csv"))
    
    if not files:
        print("Nenhum arquivo encontrado em data/enriched/")
        return pd.DataFrame()

    print(f"Carregando dados de {len(files)} arquivos...")

    for file in files:
        if "_poc" in file.name:
            continue
            
        try:
            df = pd.read_csv(file)
            # Extrair nome do repositório
            repo_name = file.stem.replace("enriched_", "")
            df['source_repo'] = repo_name
            dfs.append(df)
        except Exception as e:
            print(f"Erro ao ler {file.name}: {e}")

    if not dfs:
        return pd.DataFrame()
        
    full_df = pd.concat(dfs, ignore_index=True)
    print(f"Total de registros carregados: {len(full_df)}")
    return full_df

def feature_engineering(df):
    """Cria scores numéricos e o pain_index."""
    if df.empty:
        return df

    # 1. Pain components: positive=0, neutral=0.5, negative=1.
    df["sentiment_score"] = df["sentiment"].map(SENTIMENT_PAIN).fillna(0.5)
    df["urgency_score"] = df["urgency"].map(URGENCY_WEIGHT).fillna(1.0)
    df["pain_index"] = df["sentiment_score"] * df["urgency_score"]
    
    return df

def analyze_labels(df):
    """Processa strings de labels e encontra os Top 5 globais."""
    if df.empty or 'labels' not in df.columns:
        return [], df

    all_labels = df["labels"].map(_normalized_label_tokens).explode()
    all_labels = all_labels[all_labels.notna() & (all_labels != "")]
    
    # Contar frequência
    label_counts = all_labels.value_counts()
    
    # Pegar Top 5
    top_5_labels = label_counts.head(5).index.tolist()
    
    print(f"\nTop 5 Labels globais: {top_5_labels}")
    
    return top_5_labels, df

def generate_heatmap(df, top_labels, plots_dir=PLOTS_DIR):
    """Gera heatmap de Sentimento Médio por Repo x Top Labels."""
    if not top_labels:
        return

    # Preparar dados: Filtrar linhas que possuem PELO MENOS UM dos top labels
    # Precisamos expandir os labels novamente para criar a tabela pivô
    
    # Cria uma cópia para não estragar o df principal
    plot_df = df[['source_repo', 'sentiment_score', 'labels']].copy()
    
    # Para cada label dos top 5, verifica se está presente na string de labels da issue
    # Criamos colunas binárias (one-hot encoding para presença do label)
    for label in top_labels:
        # Verifica se a string do label está dentro da coluna 'labels'
        plot_df[f"has_{label}"] = plot_df["labels"].apply(
            lambda value: label in _normalized_label_tokens(value)
        )
    
    # Agora, para cada label top, filtramos onde has_label=True e agrupamos por repo
    heatmap_data = []
    
    for label in top_labels:
        subset = plot_df[plot_df[f'has_{label}']]
        if not subset.empty:
            avg_sentiment = subset.groupby('source_repo')['sentiment_score'].mean()
            heatmap_data.append(avg_sentiment)
    
    if not heatmap_data:
        print("Dados insuficientes para gerar Heatmap.")
        return

    # Criar DataFrame do Heatmap
    heatmap_df = pd.DataFrame(heatmap_data).T
    heatmap_df.columns = top_labels
    
    # Plotar
    plt.figure(figsize=(10, 6))
    sns.heatmap(heatmap_df, annot=True, cmap='coolwarm', center=0, fmt=".2f", linewidths=.5)
    plt.title('Sentimento Médio por Repositório e Top Labels', fontsize=14, fontweight='bold')
    plt.ylabel('Repositório', fontsize=12)
    plt.xlabel('Label', fontsize=12)
    plt.tight_layout()
    
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plots_dir / "heatmap_sentiment_labels.png"
    plt.savefig(plot_path)
    print(f"Heatmap salvo em: {plot_path}")
    plt.close()

def generate_health_barplot(df, plots_dir=PLOTS_DIR):
    """Gera gráfico comparativo do Pain Index médio por Repositório."""
    if df.empty:
        return

    # Calcular média do pain index por repo
    repo_pain = df.groupby('source_repo')['pain_index'].mean().reset_index()
    
    # Higher pain is worse, so rank descending.
    repo_pain = repo_pain.sort_values("pain_index", ascending=False)

    plt.figure(figsize=(10, 6))
    # Usando uma paleta que indica intensidade
    barplot = sns.barplot(x='pain_index', y='source_repo', data=repo_pain, palette="vlag")
    
    plt.xlim(0, 3)
    
    plt.title('Comparação de "Clima" (Pain Index Médio) por Repositório', fontsize=14, fontweight='bold')
    plt.xlabel('Pain Index Médio (0 = menor dor, 3 = maior dor)', fontsize=12)
    plt.ylabel('Repositório', fontsize=12)
    plt.tight_layout()
    
    plots_dir = Path(plots_dir)
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plots_dir / "barplot_pain_index_comparison.png"
    plt.savefig(plot_path)
    print(f"Barplot salvo em: {plot_path}")
    plt.close()
    
    # Imprimir ranking no terminal
    print("\n--- RANKING DE CLIMA (Pain Index Médio) ---")
    print(repo_pain.to_string(index=False))

def run_analysis(enriched_dir=ENRICHED_DIR, analysis_dir=ANALYSIS_DIR, plots_dir=PLOTS_DIR):
    # 1. Load
    analysis_dir = Path(analysis_dir)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    df = load_and_clean_data(enriched_dir)
    if df.empty:
        return

    # 2. Feature Engineering
    df = feature_engineering(df)

    # 3. Labels Analysis
    top_labels, df = analyze_labels(df)

    # 4. Visualizations
    generate_heatmap(df, top_labels, plots_dir)
    generate_health_barplot(df, plots_dir)
    
    print("\nAnálise Deep Diagnostic concluída. Verifique data/analysis/plots/.")


def main():
    run_analysis()

if __name__ == "__main__":
    main()
