#!/usr/bin/env python3
"""Verify that refactored steps are working correctly."""

from pathlib import Path
import sys

# Add parent to path
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from pipeline import step1_brief, step2a_structure, step2d_copy, step2e_links, step3_cohesion

def test_step_classes():
    """Test that step classes can be instantiated."""
    print("Testing step class instantiation...")
    
    # Test step1
    s1 = step1_brief.Step1Brief()
    assert s1.step_id == "step1_brief"
    assert hasattr(s1, 'run')
    assert hasattr(s1, 'load_inputs')
    assert hasattr(s1, 'build_prompt')
    print("  ✓ Step1Brief")
    
    # Test step2a
    s2a = step2a_structure.Step2aStructure()
    assert s2a.step_id == "step2a_structure"
    assert hasattr(s2a, 'run')
    assert hasattr(s2a, 'validate')
    print("  ✓ Step2aStructure")
    
    # Test step2d
    s2d = step2d_copy.Step2dCopy()
    assert s2d.step_id == "step2d_copy"
    assert hasattr(s2d, 'run')
    assert hasattr(s2d, 'validate')
    print("  ✓ Step2dCopy")
    
    # Test step2e
    s2e = step2e_links.Step2eLinks()
    assert s2e.step_id == "step2e_links"
    assert hasattr(s2e, 'run')
    assert hasattr(s2e, 'validate')
    print("  ✓ Step2eLinks")
    
    # Test step3
    s3 = step3_cohesion.Step3Cohesion()
    assert s3.step_id == "step3_cohesion"
    assert hasattr(s3, 'run')
    assert hasattr(s3, 'validate')
    print("  ✓ Step3Cohesion")
    
    print("All step classes OK!\n")


def test_backward_compatibility():
    """Test that old run() functions still exist."""
    print("Testing backward compatibility...")
    
    assert callable(step1_brief.run)
    print("  ✓ step1_brief.run() exists")
    
    assert callable(step2a_structure.run)
    print("  ✓ step2a_structure.run() exists")
    
    assert callable(step2d_copy.run)
    print("  ✓ step2d_copy.run() exists")
    
    assert callable(step2e_links.run)
    print("  ✓ step2e_links.run() exists")
    
    assert callable(step3_cohesion.run)
    print("  ✓ step3_cohesion.run() exists")
    
    print("Backward compatibility OK!\n")


def test_shared_modules():
    """Test that shared modules work."""
    print("Testing shared modules...")
    
    from pipeline import json_parser, effective, audit, validators
    
    # Test json_parser
    data, warnings = json_parser.parse_llm_json('{"foo": "bar"}', {"foo": ""})
    assert data["foo"] == "bar"
    assert len(warnings) == 0
    print("  ✓ json_parser")
    
    # Test validators
    warnings = validators.validate_structure_tokens({
        "html_skeleton": "{{token1}} {{token2}}",
        "token_manifest": [
            {"token": "{{token1}}", "source_agent": "copy"},
            {"token": "{{token2}}", "source_agent": "image"},
        ]
    })
    assert len(warnings) == 0
    print("  ✓ validators")
    
    # Test audit (just import, don't write files)
    assert hasattr(audit, 'write_audit_log')
    print("  ✓ audit")
    
    # Test effective (just import)
    assert hasattr(effective, 'effective_copy')
    assert hasattr(effective, 'effective_links')
    assert hasattr(effective, 'effective_structure')
    print("  ✓ effective")
    
    print("Shared modules OK!\n")


if __name__ == "__main__":
    try:
        test_step_classes()
        test_backward_compatibility()
        test_shared_modules()
        print("=" * 50)
        print("ALL TESTS PASSED ✓")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
