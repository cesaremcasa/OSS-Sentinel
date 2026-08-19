import os
import json
import requests
import logging
import yaml  # Importante para ler o config
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURAÇÃO DE AMBIENTE ---
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "settings.yaml"

load_dotenv(BASE_DIR / "config" / ".env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IngestionEngine:
    def __init__(self, output_dir="data/raw", config_path=None):
        self.output_dir = BASE_DIR / output_dir
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Carregar configurações YAML
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self):
        """Lê o arquivo de configuração settings.yaml"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Arquivo de configuração não encontrado em: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Erro ao ler YAML: {e}")
            raise

    def _get_date_filter(self, days_back):
        """Gera a string de data para a query da API (ex: 2024-07-01)"""
        date_limit = datetime.now() - timedelta(days=days_back)
        return date_limit.strftime("%Y-%m-%d")

    def fetch_github_issues(self, query, sort="created", order="desc", per_page=100):
        """Busca issues baseado em uma query específica"""
        url = "https://api.github.com/search/issues"
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page
        }
        
        logger.info(f"Buscando com query: {query}")
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição: {e}")
            return None

    def save_raw_data(self, data, source_name):
        """Salva o JSON bruto com o nome do repositório alvo"""
        if not data:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # O source_name será algo como "apache_superset"
        filename = f"ingest_{source_name}_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Salvo: {filepath}")

    def run(self):
        """Executa o loop de ingestão para todos os alvos definidos no YAML"""
        targets = self.config.get('github', {}).get('targets', [])
        params = self.config.get('parameters', {})
        days_back = params.get('days_back', 30)
        max_results = params.get('max_results', 100)
        
        date_str = self._get_date_filter(days_back)
        
        logger.info(f"Iniciando ingestão para {len(targets)} alvos (janela: {days_back} dias).")

        for target_query in targets:
            # Monta a query final: "repo:owner/name is:issue created:2024-XX-XX"
            final_query = f"{target_query} created:>{date_str}"
            
            # Extrai nome limpo para o arquivo (ex: repo:apache/superset -> apache_superset)
            repo_name = target_query.replace("repo:", "").replace(" is:issue", "").replace("/", "_")
            
            # Executa busca
            raw_data = self.fetch_github_issues(
                query=final_query, 
                per_page=max_results
            )
            
            # Salva
            self.save_raw_data(raw_data, source_name=repo_name)

def main():
    engine = IngestionEngine()
    engine.run()

if __name__ == "__main__":
    main()
