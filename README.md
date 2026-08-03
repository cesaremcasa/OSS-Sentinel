# OSS Sentinel

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-API-181717?style=for-the-badge&logo=github&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

Automated AI-Driven Health Monitor & Decision Engine for Open Source Ecosystems

---

## The Problem

Traditional OSS metrics like **Star counts** and **Forks** are lagging indicators. They do not reflect current operational reality, maintenance burden, or developer satisfaction of a project.

**OSS Sentinel** addresses this gap by analyzing the **"heartbeat"** of a repository: its **Issues**. By leveraging NLP to classify sentiment and urgency, we move beyond vanity metrics to actionable insights about project stability and technical debt.

---

## Architecture

The pipeline follows a rigorous **data engineering flow**:

**Ingestion Layer:** Connects to GitHub Search API to fetch raw issue data based on temporal and repository targets.

**Processing Layer:** Uses Pandas to clean, normalize, and flatten nested JSON structures into a structured schema.

**Enrichment Layer:** Employs OpenAI's GPT-4o-mini to perform deep semantic classification on every issue: Sentiment (Positive / Neutral / Negative), Category (Bug / Feature / Documentation / Other), Urgency (High / Medium / Low).

**Analytics Layer:** Computes a proprietary Pain Index (Sentiment × Urgency) and generates diagnostic heatmaps.

---

## Findings & Insights

As a **Proof of Concept**, OSS Sentinel analyzed the health of three major Business Intelligence tools (**Apache Superset**, **Grafana**, and **Metabase**) over the last 6 months.

Window: 180 Days | Sample: 100 issues/repo

### Health Comparison (Pain Index)

| Repository        | Pain Index | Sentiment Distribution       | High Urgency Rate |
|-------------------|------------|------------------------------|-------------------|
| **Grafana**       | `-1.03`    | Balanced (51% Neg / 12% Pos) | 25%               |
| **Metabase**      | `-1.54`    | Mixed (67% Neg / 7% Pos)     | 41%               |
| **Apache Superset** | `-2.21`  | Critical (87% Neg)           | 53%               |

**Pain Index Formula**: `(-1 to +1) × (Low:1 / Med:2 / High:3)`. Lower is "worse".

---

### Key Insights

#### Grafana: The "Safe Bet"
Exhibits the **lowest Pain Score**. While issues exist, they tend to be of medium urgency. The higher positive sentiment ratio indicates a healthier community response to issues.

#### Apache Superset: The "Trauma Hospital"
The data reveals a **demanding technical debt load**. The overwhelming negative sentiment (87%) coupled with the highest Urgency rate suggests the project is in a constant state of triage. Adoption requires a strong internal engineering team.

#### Metabase: The "Tired Middle Ground"
Sits between the two. High urgency bugs are prevalent, but the community is slightly more positive than Apache, indicating a **resilient but strained** support ecosystem.

---

## Installation & Setup

### Prerequisites

- **Python 3.9+**
- **GitHub Personal Access Token** (Classic) with `public_repo` scope
- **OpenAI API Key**

### Installation

Clone the repository:

```bash
git clone https://github.com/cesaremcasa/OSS-Sentinel.git
cd OSS-Sentinel
```

Create and activate virtual environment:

```bash
python3.9 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Set your environment variables:

```bash
export GITHUB_TOKEN="your_github_token"
export OPENAI_API_KEY="your_openai_key"
```

Or create a `.env` file in the root directory:

```
GITHUB_TOKEN=your_github_token
OPENAI_API_KEY=your_openai_key
```

---

## Running the System

### Step 1: Data Ingestion

Fetch raw issue data from GitHub repositories:

```bash
python src/ingestion.py
```

This step queries the GitHub Search API and saves raw JSON data to `data/raw/`.

### Step 2: Data Processing

Clean and normalize the raw data into a structured format:

```bash
python src/processing.py
```

Processed data will be saved to `data/processed/`.

### Step 3: AI Enrichment

Perform semantic classification using OpenAI GPT-4o-mini:

```bash
python src/enrichment.py
```

Each issue will be classified by Sentiment, Category, and Urgency. Results are saved to `data/enriched/`.

### Step 4: Analytics & Visualization

Generate Pain Index calculations and diagnostic heatmaps:

```bash
python src/analyze.py
```

Results and plots will be saved in `assets/plots/` and `data/analysis/`.

### Full Pipeline Execution

To run all steps sequentially:

```bash
python main.py
```

---

## Project Structure

```
.
├── src/
│   ├── ingestion.py       # GitHub API data fetching
│   ├── processing.py      # Data cleaning & normalization
│   ├── enrichment.py      # AI-powered classification
│   └── analyze.py         # Pain Index calculation & visualization
├── data/
│   ├── raw/               # Raw GitHub API responses
│   ├── processed/         # Cleaned & structured data
│   ├── enriched/          # AI-classified data
│   └── analysis/          # Final metrics & reports
├── assets/
│   └── plots/             # Generated visualizations
├── main.py                # Full pipeline orchestrator
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Technical Details

### Pain Index Methodology

The Pain Index is calculated as:

```
Pain Index = Sentiment_Score × Urgency_Weight
```

Where:
- **Sentiment Score**: Positive (+1), Neutral (0), Negative (-1)
- **Urgency Weight**: Low (1), Medium (2), High (3)

This metric provides a quantitative measure of project health, where lower (more negative) values indicate higher technical debt and community frustration.

### API Rate Limits

GitHub API has rate limits. The system includes exponential backoff and retry logic to handle rate limiting gracefully. For unauthenticated requests: 60 requests/hour. For authenticated requests: 5,000 requests/hour.

### AI Classification

The system uses OpenAI's GPT-4o-mini for classification due to its optimal cost/performance ratio for structured extraction tasks. Each issue is processed individually with a structured prompt to ensure consistent classification.

---

## License

**MIT License**

Copyright (c) 2025 Cesar Augusto

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

## Contact

For questions or collaboration opportunities, please reach out via [GitHub Issues](https://github.com/cesaremcasa/OSS-Sentinel/issues).

---

**Cesar Augusto**  
AI Systems Engineer, Mycellium Lab
