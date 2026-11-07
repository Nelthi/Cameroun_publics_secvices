"""Couche de liaison T1 -> T2 -> T3 -> T4 (ajoutée lors de la fusion).

Aucun module d'un membre n'est modifié : ce paquet ne fait que brancher
leurs sorties les unes sur les entrées des autres.
"""


def run_pipeline(*args, **kwargs):
    """Chaîne complète (import différé pour pouvoir lancer les sous-modules avec -m)."""
    from .run import run_pipeline as _run

    return _run(*args, **kwargs)


__all__ = ["run_pipeline"]
