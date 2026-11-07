"""Couche de liaison T1 -> T2 -> T3 -> T4 (ajoutée lors de la fusion).

Aucun module d'un membre n'est modifié : ce paquet ne fait que brancher
leurs sorties les unes sur les entrées des autres.
"""
from .run import run_pipeline

__all__ = ["run_pipeline"]
