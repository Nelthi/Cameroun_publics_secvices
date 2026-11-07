"""Test manuel de la recherche.  Usage : python search_demo.py "ma question" -k 4"""
import argparse

from backend.rag import search

parser = argparse.ArgumentParser()
parser.add_argument("question")
parser.add_argument("-k", "--top-k", type=int, default=4)
args = parser.parse_args()

for r in search(args.question, args.top_k):
    print(f"\n#{r['rank']}  score={r['score']}  {r['chunk_id']}  (page {r['source_page']})")
    print(r["text"][:300])
