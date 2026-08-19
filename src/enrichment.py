import pandas as pd
import logging
from pathlib import Path

from src.providers import IssueClassifier, make_provider

BASE_DIR = Path(__file__).resolve().parent.parent

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnrichmentEngine:
    def __init__(
        self,
        processed_dir="data/processed",
        enriched_dir="data/enriched",
        provider: IssueClassifier | None = None,
        provider_name: str | None = None,
    ):
        self.processed_dir = BASE_DIR / processed_dir
        self.enriched_dir = BASE_DIR / enriched_dir
        self.enriched_dir.mkdir(parents=True, exist_ok=True)
        self.provider = provider or make_provider(provider_name)

    def classify_issue(self, title: str, body: str):
        """Classify one issue through the selected provider."""
        try:
            return self.provider.classify_issue(str(title), str(body or ""))
        except Exception as e:
            logger.error(f"Erro no provider de enriquecimento: {e}")
            return {"sentiment": "error", "category": "unknown", "urgency": "unknown"}

    def run_batch(self):
        """Varre todos CSVs em data/processed, enriquece e salva em data/enriched."""
        csv_files = sorted(list(self.processed_dir.glob("processed_*.csv")))
        
        if not csv_files:
            logger.warning("Nenhum CSV processado encontrado em data/processed.")
            return

        logger.info(f"Iniciando enriquecimento de lote para {len(csv_files)} arquivos.")

        for csv_file in csv_files:
            logger.info(f"--- Processando: {csv_file.name} ---")
            
            try:
                # 1. Ler o arquivo completo (sem limites de linha)
                df = pd.read_csv(csv_file)
                
                # Listas para novos dados
                sentiments = []
                categories = []
                urgencies = []

                # 2. Iterar sobre o DataFrame completo
                for index, row in df.iterrows():
                    if (index + 1) % 10 == 0:
                        logger.info(f"Progresso: {index + 1}/{len(df)} linhas processadas...")
                    
                    res = self.classify_issue(row['title'], row['body'])
                    sentiments.append(res.get('sentiment'))
                    categories.append(res.get('category'))
                    urgencies.append(res.get('urgency'))

                # 3. Adicionar colunas
                df['sentiment'] = sentiments
                df['category'] = categories
                df['urgency'] = urgencies

                # 4. Gerar nome dinâmico de saída
                # Exemplo Input: processed_apache_superset_20231223_120000.csv
                # Exemplo Output: enriched_apache_superset.csv
                stem = csv_file.stem # remove .csv
                # Remover prefixo 'processed_'
                if stem.startswith("processed_"):
                    stem = stem[len("processed_"):]
                
                # Remover timestamp do final (últimos 2 underscores: _YYYYMMDD_HHMMSS)
                # Assume padrão: nome_repo_DATA_HORA
                parts = stem.rsplit('_', 2)
                core_name = parts[0] if len(parts) == 3 else stem
                
                output_filename = f"enriched_{core_name}.csv"
                output_path = self.enriched_dir / output_filename

                # 5. Salvar
                df.to_csv(output_path, index=False)
                logger.info(f"Arquivo salvo: {output_path}")

            except Exception as e:
                logger.error(f"Erro crítico ao processar {csv_file.name}: {e}")

def main():
    engine = EnrichmentEngine()
    engine.run_batch()

if __name__ == "__main__":
    main()
