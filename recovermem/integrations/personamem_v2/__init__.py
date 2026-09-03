"""PersonaMem-v2 / ImplicitPersona integration (TEXT-only, 128K, MCQ).

The released PersonaMem-v2 evaluator is used as a library for the two things that define
the benchmark's semantics -- MCQ option construction and answer extraction -- so neither is
reimplemented here. Everything else (bounded memory evidence, bounded recovery, paired
logging) is ReCoverMem's own.
"""
