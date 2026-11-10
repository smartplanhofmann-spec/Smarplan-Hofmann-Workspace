"""Verify shared immutable Source5 ancestors once within one read traversal.

No result survives the outer call. Writes, later reads, other offices, threads
and tasks receive a fresh graph. Failed or incomplete proofs are never reused.
"""
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
from hashlib import sha256

from core import Problem, canonical

_graph = ContextVar('source5_original_verification_graph', default=None)


@contextmanager
def _scope():
    token = None
    if _graph.get() is None:
        token = _graph.set(dict(done={}, active=set(), calculations={}))
    try:
        yield
    finally:
        if token is not None:
            _graph.reset(token)


def within_original_graph(read):
    @wraps(read)
    def checked(*args, **kwargs):
        with _scope():
            return read(*args, **kwargs)
    return checked


def calculate_multiple_source(source, *, rule_version, source_contract_version):
    """Reuse only deterministic math for exact source bytes inside this read."""
    from payroll_multiple_oneoff_2026 import calculate_multiple_source as calculate
    graph = _graph.get()
    if graph is None:
        return calculate(source, rule_version=rule_version, source_contract_version=source_contract_version)
    key = sha256(canonical([source, rule_version, source_contract_version]).encode()).digest()
    if key not in graph['calculations']:
        graph['calculations'][key] = calculate(source, rule_version=rule_version,
            source_contract_version=source_contract_version)
    # Consumers may attach their own views. Never share a mutable result.
    return deepcopy(graph['calculations'][key])


def once_per_original_graph(verify):
    @within_original_graph
    @wraps(verify)
    def checked(payroll, record):
        graph = _graph.get()
        key = (id(payroll.office), sha256(canonical(record).encode()).digest())
        if key in graph['done']:
            # Even a repeated identical supplied object must still match
            # its authoritative original row in the current transaction.
            if payroll._event(payroll._row(record['id'], 'run', record['revision'])) != record:
                raise Problem(500, 'Die historische Originalfassung wurde während der Prüfung verändert.')
            return graph['done'][key]
        if key in graph['active']:
            raise Problem(500, 'Die ursprüngliche Lohnkette enthält einen zyklischen Nachweis.')
        graph['active'].add(key)
        try:
            result = verify(payroll, record)
        finally:
            graph['active'].remove(key)
        graph['done'][key] = result
        return result
    return checked
