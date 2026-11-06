"""Configuration centrale de la tâche T4 (vectorisation + index FAISS).

Tous les chemins et paramètres sont ici : si l'équipe change un dossier
ou un modèle, on ne modifie qu'un seul fichier.
"""
from pathlib import Path

# Racine du projet = deux niveaux au-dessus de ce fichier (backend/rag/config.py)
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

CHUNKS_DIR = DATA_DIR / "chunks"          # ENTRÉE  : JSON produits par T3
INDEX_DIR = DATA_DIR / "indexes"          # SORTIE  : index + mapping
INDEX_PATH = INDEX_DIR / "faiss.index"
MAPPING_PATH = INDEX_DIR / "chunk_mapping.json"
MODEL_NAME = "BAAI/bge-m3"
# MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
DEFAULT_TOP_K = 4
