"""Tests for entry 09's prime_directive package (FR-1, M2).

Covers the typed wire surface that the cycle adapter + supervised
worker rely on:

  * attest.attest / compute_digest / config_fingerprint
  * validate.validate_attestation / verify_attestation_chain
  * meta_validator.validate_meta / validate_all_metas
  * extension_bridge.render_sanctioned_globs

The tests are hermetic; they do not touch the network or any
sibling repo. Cross-repo integration is exercised by
``tests/simulation/test_compat_matrix.py`` and the cycle's own
end-to-end adapter.
"""
