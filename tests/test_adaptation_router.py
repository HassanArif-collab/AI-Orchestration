"""Tests for required RouterClient injection in adaptation stages.

These tests verify that router_client is a required parameter
(no default value) in all adaptation stages (2-5), ensuring
proper dependency injection from the runner.
"""

import inspect


def test_stage2_requires_router_client():
    """Stage 2's stage2_analyze must require router_client parameter."""
    from packages.content_factory.adaptation.stage2_structural import stage2_analyze
    sig = inspect.signature(stage2_analyze)
    param = sig.parameters.get("router_client")
    assert param is not None and param.default is inspect.Parameter.empty


def test_stage3_requires_router_client():
    """Stage 3's stage3_localize must require router_client parameter."""
    from packages.content_factory.adaptation.stage3_localization import stage3_localize
    sig = inspect.signature(stage3_localize)
    param = sig.parameters.get("router_client")
    assert param is not None and param.default is inspect.Parameter.empty


def test_stage4_requires_router_client():
    """Stage 4's stage4_generate must require router_client parameter."""
    from packages.content_factory.adaptation.stage4_script import stage4_generate
    sig = inspect.signature(stage4_generate)
    param = sig.parameters.get("router_client")
    assert param is not None and param.default is inspect.Parameter.empty


def test_stage5_requires_router_client():
    """Stage 5's stage5_refine must require router_client parameter."""
    from packages.content_factory.adaptation.stage5_refinement import stage5_refine
    sig = inspect.signature(stage5_refine)
    param = sig.parameters.get("router_client")
    assert param is not None and param.default is inspect.Parameter.empty
