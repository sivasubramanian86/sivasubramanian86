"""Verification tests for profile repository integrity."""

def test_profile_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content) > 500, "Profile README should be comprehensive"
    assert "Sivasubramanian" in content, "Profile name should be present"
    assert "Google Cloud" in content, "Core credentials should be listed"

def test_banner_exists():
    import os
    assert os.path.exists("banner.svg"), "Profile banner should exist"
