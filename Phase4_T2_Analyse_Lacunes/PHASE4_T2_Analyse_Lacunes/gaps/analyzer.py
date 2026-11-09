"""Cœur de T2 : fusionne audit + échecs d'évaluation, regroupe par sujet, classe, suggère."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from .classify import NON_GAP_TYPE, classify_failure
from .knowledge import (DEFAULT_DOMAIN, DEFAULT_SUBDOMAIN, infer_subdomain, suggest_document,
                        suggest_institution)
from .models import AuditContext, AuditData, EvalData, Observation
from .readers import MAX_QUESTION_CHARS, MAX_TOPIC_CHARS
from .text import clean_text, fold, similarity, tokens, topic_key

DEFAULT_SIMILARITY = 0.6
MAX_EXAMPLES = 3
MAX_REQUEST_IDS = 5
MAX_QUESTION_IDS = 10


def _iso(moment: datetime | None) -> str | None:
    return moment.replace(microsecond=0).isoformat() if moment else None


def _most_common(values: list[str], default: str) -> str:
    counts = Counter(v for v in values if v)
    if not counts:
        return default
    best = max(counts.values())
    return sorted(v for v, n in counts.items() if n == best)[0]


def _unique(items, limit: int) -> list:
    seen, out = set(), []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
            if len(out) == limit:
                break
    return out


def build_observations(audit: AuditData | None, eval_data: EvalData | None, questions: dict[str, str],
                       count_unexpected: bool, warnings: list[str]) -> tuple[list[Observation], list[dict]]:
    """Toutes les observations (audit puis évaluation) et la liste des échecs écartés."""
    contexts = audit.contexts if audit else {}
    observations: list[Observation] = []
    audit_by_request: dict[str, Observation] = {}

    for obs in (audit.observations if audit else []):
        ctx = contexts.get(obs.request_id or "", AuditContext())
        obs.question = obs.question or ctx.question
        obs.domain = obs.domain or ctx.domain
        obs.subdomain = obs.subdomain or ctx.subdomain or infer_subdomain(f"{obs.topic} {obs.question or ''}")
        observations.append(obs)
        if obs.request_id and obs.request_id not in audit_by_request:
            audit_by_request[obs.request_id] = obs

    ignored: list[dict] = []
    for failure in (eval_data.failures if eval_data else []):
        qid, request_id = str(failure["question_id"]), failure.get("request_id")
        request_id = str(request_id) if request_id else None
        ftype = classify_failure(failure.get("expected"), failure.get("got"))
        base = {"question_id": qid, "request_id": request_id, "expected": failure.get("expected"),
                "got": failure.get("got")}
        if ftype is None:
            ignored.append({**base, "failure_type": None, "reason": "pas un échec (attendu absent ou refus correct)"})
            continue
        if ftype == NON_GAP_TYPE and not count_unexpected:
            ignored.append({**base, "failure_type": ftype,
                            "reason": "refus attendu mais réponse donnée : problème de garde-fous, "
                                      "pas de document manquant"})
            continue
        ctx = contexts.get(request_id or "", AuditContext())
        raw_question = failure.get("question") if isinstance(failure.get("question"), str) else None
        question = clean_text(raw_question, MAX_QUESTION_CHARS) if raw_question else (ctx.question or questions.get(qid))
        linked = audit_by_request.get(request_id) if request_id else None
        if linked is not None:
            # Même événement que la lacune déjà relevée par l'audit : on le confirme sans le recompter.
            observations.append(Observation(topic=linked.topic, origin="eval", weight=0, failure_type=ftype,
                                            request_id=request_id, question_id=qid, question=question,
                                            domain=linked.domain, subdomain=linked.subdomain))
        elif question:
            observations.append(Observation(
                topic=clean_text(question, MAX_TOPIC_CHARS), origin="eval", weight=1, failure_type=ftype,
                request_id=request_id, question_id=qid, question=question, domain=ctx.domain,
                subdomain=ctx.subdomain or infer_subdomain(question)))
        else:
            ignored.append({**base, "failure_type": ftype, "reason": "texte de la question introuvable "
                            "(ni dans audit_log, ni dans questions.json)"})
    n_unreadable = sum(1 for i in ignored if i["reason"].startswith("texte de la question"))
    if n_unreadable:
        warnings.append(f"{n_unreadable} échec(s) d'évaluation écarté(s) faute de texte de question "
                        f"(fournir --questions ou un audit_log)")
    return observations, ignored


def cluster_observations(observations: list[Observation], threshold: float) -> list[list[Observation]]:
    """Regroupe les observations d'un même sous-domaine dont les sujets se ressemblent."""
    by_subdomain: dict[str, dict[str, list[Observation]]] = {}
    for obs in observations:
        units = by_subdomain.setdefault(obs.subdomain or DEFAULT_SUBDOMAIN, {})
        units.setdefault(topic_key(tokens(obs.topic), obs.topic), []).append(obs)

    clusters: list[list[Observation]] = []
    for subdomain in sorted(by_subdomain):
        units = by_subdomain[subdomain]
        ordered = sorted(units.items(), key=lambda kv: (-sum(o.weight for o in kv[1]), -len(kv[1]), kv[0]))
        group: list[tuple[frozenset, list[Observation]]] = []  # (mots du représentant, observations)
        for key, members in ordered:
            words = tokens(members[0].topic)
            best, best_sim = None, 0.0
            for index, (rep_words, _) in enumerate(group):
                sim = similarity(words, rep_words)
                if sim >= threshold and sim > best_sim:
                    best, best_sim = index, sim
            if best is None:
                group.append((words, list(members)))
            else:
                group[best][1].extend(members)
        clusters.extend(members for _, members in group)
    return clusters


def _representative_topic(members: list[Observation]) -> tuple[str, str]:
    """(libellé affiché, clé de sujet) : le libellé le plus fréquent, de préférence issu de l'audit."""
    weight, from_audit = Counter(), set()
    for o in members:
        weight[o.topic] += o.weight
        if o.origin == "audit":
            from_audit.add(o.topic)
    topic = sorted(weight, key=lambda t: (-weight[t], t not in from_audit, len(t), t))[0]
    return topic, topic_key(tokens(topic), topic)


def build_gap(members: list[Observation]) -> dict:
    topic, key = _representative_topic(members)
    subdomain = members[0].subdomain or DEFAULT_SUBDOMAIN
    origins = {o.origin for o in members}
    stamps = [o.timestamp for o in members if o.timestamp]
    questions = _unique((o.question for o in members), MAX_EXAMPLES)
    evidence = {
        "audit_occurrences": sum(o.weight for o in members if o.origin == "audit"),
        "eval_occurrences": sum(o.weight for o in members if o.origin == "eval"),
        "eval_failures": sum(1 for o in members if o.origin == "eval"),
        "reasons": dict(sorted(Counter(o.reason for o in members if o.reason).items())),
        "failure_types": dict(sorted(Counter(o.failure_type for o in members if o.failure_type).items())),
        "example_questions": questions,
        "request_ids": _unique((o.request_id for o in members), MAX_REQUEST_IDS),
        "question_ids": _unique((o.question_id for o in members), MAX_QUESTION_IDS),
        "first_seen": _iso(min(stamps)) if stamps else None,
        "last_seen": _iso(max(stamps)) if stamps else None,
    }
    slug = "-".join(fold(key).split()) or "sans-sujet"
    return {
        "gap_id": "",  # attribué après classement
        "topic": topic,
        "topic_key": f"{subdomain}:{slug}",
        "domain": _most_common([o.domain for o in members], DEFAULT_DOMAIN),
        "subdomain": subdomain,
        "occurrences": sum(o.weight for o in members),
        "source": "+".join(s for s in ("audit", "eval") if s in origins),
        "suggested_document": suggest_document(sorted({o.topic for o in members}) + questions),
        "suggested_institution": suggest_institution(subdomain),
        "evidence": evidence,
    }


def rank_gaps(gaps: list[dict]) -> list[dict]:
    """Par occurrences décroissantes ; à égalité : confirmées par l'évaluation, plus récentes, puis clé."""
    def sort_key(gap: dict):
        ev = gap["evidence"]
        return (-gap["occurrences"], 0 if ev["eval_failures"] else 1, _neg_ts(ev["last_seen"]), gap["topic_key"])

    ranked = sorted(gaps, key=sort_key)
    for position, gap in enumerate(ranked, start=1):
        gap["gap_id"] = f"GAP-{position:03d}"
    return ranked


def _neg_ts(value: str | None) -> float:
    return -datetime.fromisoformat(value).timestamp() if value else 0.0


def analyze(audit: AuditData | None, eval_data: EvalData | None, questions: dict[str, str] | None = None, *,
            threshold: float = DEFAULT_SIMILARITY, count_unexpected: bool = False,
            now: datetime | None = None, parameters: dict | None = None,
            warnings: list[str] | None = None) -> dict:
    """Produit le rapport complet (contrat du guide + champs additionnels)."""
    warnings = list(warnings or [])
    if audit is None and eval_data is None:
        warnings.append("aucune source : ni audit, ni évaluation")
    if audit is not None and audit.info.get("kind") == "api":
        warnings.append("source GET /gaps : pas de request_id, donc les échecs d'évaluation ne peuvent pas "
                        "être dédoublonnés avec l'audit (un même événement peut être compté deux fois)")
    observations, ignored = build_observations(audit, eval_data, questions or {}, count_unexpected, warnings)
    gaps = rank_gaps([build_gap(members) for members in cluster_observations(observations, threshold)])

    n_unknown = sum(1 for g in gaps if g["subdomain"] == DEFAULT_SUBDOMAIN)
    if n_unknown:
        warnings.append(f"{n_unknown} lacune(s) sans sous-domaine identifié (« {DEFAULT_SUBDOMAIN} ») : à classer à la main")

    by_subdomain: dict[str, dict] = {}
    for gap in gaps:
        entry = by_subdomain.setdefault(gap["subdomain"], {"n_gaps": 0, "occurrences": 0})
        entry["n_gaps"] += 1
        entry["occurrences"] += gap["occurrences"]

    now = (now or datetime.now()).replace(microsecond=0)
    return {
        "report_date": now.isoformat(),
        "n_gaps": len(gaps),
        "gaps": gaps,
        "summary": {"total_occurrences": sum(g["occurrences"] for g in gaps), "by_subdomain": by_subdomain},
        "inputs": {"audit": audit.info if audit else None, "eval": eval_data.info if eval_data else None},
        "ignored_failures": ignored,
        "warnings": warnings,
        "parameters": parameters or {},
    }
