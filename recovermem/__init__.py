"""ReCoverMem -- host-agnostic recoverability scoring, calibration and routing.

The package is deliberately layered so that the scientific invariants are structural
rather than conventional:

* ``interfaces``  -- the only surface the controller may touch on a memory host.
* ``hosts``       -- concrete host adapters. Table 1 uses ``mem0_adapter`` ONLY.
* ``scoring``     -- host-agnostic features and the frozen recoverability predictor.
* ``calibration`` -- episode-level threshold selection rules.
* ``metrics``     -- episode-equal-weighted risk quantities.
* ``recovery``    -- bounded retrieval over the immutable raw trajectory H_t.
* ``control``     -- TRUST/RECOVER routing.
* ``logging``     -- the paired-decision record that every downstream analysis reads.

Three-Layer Memory is NOT part of ReCoverMem. It exists only as an optional host in
``hosts.three_layer_adapter`` and is never imported unless explicitly selected.
"""

__version__ = "0.1.0"
FEATURE_SCHEMA_VERSION = "recovermem-features-v1"
