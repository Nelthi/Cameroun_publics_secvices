"""Interface Streamlit.   Lancement :  streamlit run ui/streamlit_app.py
(l'API doit tourner : uvicorn app.main:app)"""
import os

import requests
import streamlit as st

API = os.getenv("API_URL", "http://127.0.0.1:8000")
LABELS = {"approved": ("success", "Réponse approuvée"),
          "partial": ("warning", "Réponse partielle"),
          "refused": ("warning", "Information non disponible"),
          "needs_clarification": ("info", "Précision demandée"),
          "error": ("error", "Erreur technique")}

st.set_page_config(page_title="Cameroun Public Service AI", page_icon="🇨🇲")
st.title("Cameroun Public Service AI")
st.caption("Orientation dans les démarches administratives, à partir de documents officiels")

question = st.text_area("Votre question", max_chars=500, height=100,
                        placeholder="Ex : Quelles sont les pièces pour la CNI ?")

if st.button("Poser la question", type="primary"):
    if not question.strip():
        st.warning("Veuillez écrire une question.")
        st.stop()
    try:
        resp = requests.post(f"{API}/ask", json={"question": question}, timeout=90)
    except requests.RequestException:
        st.error("API injoignable. Vérifiez qu'elle est lancée (uvicorn app.main:app).")
        st.stop()
    if resp.status_code == 422:
        st.warning("Question invalide (vide ou de plus de 500 caractères).")
        st.stop()
    data = resp.json()
    kind, label = LABELS.get(data["status"], ("info", data["status"]))
    getattr(st, kind)(label)
    st.write(data["answer"])
    if data["sources"]:
        st.subheader("Sources")
        for s in data["sources"]:
            st.write(f"- {s['document_id']}, page {s['source_page']}")
    with st.expander("Détails techniques"):
        st.write(f"Identifiant : `{data['request_id']}`")
        detail = requests.get(f"{API}/audit/{data['request_id']}", timeout=10)
        if detail.ok:
            row = detail.json()
            st.write("Routage :", row["routing_json"])
            st.write("Contrôles :", (row["validation_json"] or {}).get("checks"))
            if row["error"]:
                st.write("Erreur :", row["error"])

with st.sidebar:
    st.header("Lacunes détectées")
    try:
        gaps = requests.get(f"{API}/gaps", timeout=5).json()
        if not gaps:
            st.write("Aucune pour le moment.")
        for g in gaps:
            st.write(f"- {g['topic']} ({g['count']})")
    except requests.RequestException:
        st.write("API injoignable.")
