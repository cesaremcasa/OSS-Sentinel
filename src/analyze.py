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

    # 1. Sentiment Score
    sentiment_map = {'positive': 1, 'neutral': 0, 'negative': -1}
    df['sentiment_score'] = df['sentiment'].map(sentiment_map).fillna(0)

    # 2. Urgency Score
    urgency_map = {'low': 1, 'medium': 2, 'high': 3}
    df['urgency_score'] = df['urgency'].map(urgency_map).fillna(1)

    # 3. Pain Index (Produto Sentimento * Urgência)
    # -3 (Muito Negativo + Alta Urgência) é o pior caso
    # 3 (Muito Positivo + Alta Urgência) é um caso de "Boa Oportunidade/Feature Quente"
    df['pain_index'] = df['sentiment_score'] * df['urgency_score']
    
    return df

def analyze_labels(df):
    """Processa strings de labels e encontra os Top 5 globais."""
    if df.empty or 'labels' not in df.columns:
        return [], df

    # A coluna labels veio como string separada por vírgula do processing.py (ex: "bug, ui")
    # Vamos separar e explodir
    all_labels = df['labels'].str.split(',').explode()
    
    # Limpar espaços em branco
    all_labels = all_labels.str.strip()
    
    # Remover vazios
    all_labels = all_labels[all_labels != ""]
    
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
        plot_df[f'has_{label}'] = plot_df['labels'].apply(lambda x: label in str(x))
    
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
    
    # Ordenar (opcional, mas bom para visualização: pior clima primeiro)
    repo_pain = repo_pain.sort_values('pain_index', ascending=True)

    plt.figure(figsize=(10, 6))
    # Usando uma paleta que indica intensidade
    barplot = sns.barplot(x='pain_index', y='source_repo', data=repo_pain, palette="vlag")
    
    # Adicionar linha de referência (Neutro = 0)
    plt.axvline(x=0, color='black', linestyle='--', linewidth=1)
    
    plt.title('Comparação de "Clima" (Pain Index Médio) por Repositório', fontsize=14, fontweight='bold')
    plt.xlabel('Pain Index Médio (Negativo = Dor, Positivo = Oportunidade)', fontsize=12)
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
