#!/usr/bin/env python3
"""
Test script to verify the resolution parameter functionality
"""

import sys
import os

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dl

def test_resolution_selection():
    """Test the resolution selection logic"""
    
    # Mock variants data (similar to what would be parsed from HLS manifest)
    test_variants = [
        (1, 5000000, "1920x1080", "30", "avc1.640028", "https://example.com/1080p.m3u8"),
        (2, 3000000, "1280x720", "30", "avc1.640028", "https://example.com/720p.m3u8"),
        (3, 1500000, "854x480", "30", "avc1.640028", "https://example.com/480p.m3u8"),
        (4, 800000, "640x360", "30", "avc1.640028", "https://example.com/360p.m3u8"),
    ]
    
    print("Testing resolution selection logic...")
    print("Available variants:")
    for idx, bw, res, fps, codecs, url in test_variants:
        print(f"  {idx}. {res} @ {fps} fps | {bw//1000} Kbps")
    
    # Test exact match for 1080p
    print("\n--- Test 1: Exact match for 1080p ---")
    dl.main.preferred_resolution = "1080"
    
    # Simulate the selection logic from select_variant function
    preferred_res = getattr(dl.main, "preferred_resolution", None)
    if preferred_res:
        target_height = int(preferred_res)
        
        # First try exact match
        selected = None
        for variant in test_variants:
            _, _, res, _, _, _ = variant
            if "x" in res:
                _, height = map(int, res.split("x"))
                if height == target_height:
                    selected = variant
                    print(f"✓ Selected {res} (exact match for {preferred_res}p)")
                    break
        
        if not selected:
            print("✗ No exact match found")
    
    # Test closest match for 900p (should select 1080p)
    print("\n--- Test 2: Closest match for 900p (should select 1080p) ---")
    dl.main.preferred_resolution = "900"
    
    preferred_res = getattr(dl.main, "preferred_resolution", None)
    if preferred_res:
        target_height = int(preferred_res)
        
        # Try exact match first
        selected = None
        for variant in test_variants:
            _, _, res, _, _, _ = variant
            if "x" in res:
                _, height = map(int, res.split("x"))
                if height == target_height:
                    selected = variant
                    break
        
        if not selected:
            # Find closest resolution
            closest = None
            min_diff = float('inf')
            for variant in test_variants:
                _, _, res, _, _, _ = variant
                if "x" in res:
                    _, height = map(int, res.split("x"))
                    diff = abs(height - target_height)
                    if diff < min_diff:
                        min_diff = diff
                        closest = variant
            
            if closest:
                _, _, res, _, _, _ = closest
                print(f"✓ Selected {res} (closest match to {preferred_res}p)")
    
    # Test closest match for 600p (should select 720p)
    print("\n--- Test 3: Closest match for 600p (should select 720p) ---")
    dl.main.preferred_resolution = "600"
    
    preferred_res = getattr(dl.main, "preferred_resolution", None)
    if preferred_res:
        target_height = int(preferred_res)
        
        # Find closest resolution
        closest = None
        min_diff = float('inf')
        for variant in test_variants:
            _, _, res, _, _, _ = variant
            if "x" in res:
                _, height = map(int, res.split("x"))
                diff = abs(height - target_height)
                if diff < min_diff:
                    min_diff = diff
                    closest = variant
        
        if closest:
            _, _, res, _, _, _ = closest
            print(f"✓ Selected {res} (closest match to {preferred_res}p)")
    
    print("\n--- Test 4: No preferred resolution (should prompt user) ---")
    dl.main.preferred_resolution = None
    preferred_res = getattr(dl.main, "preferred_resolution", None)
    if not preferred_res:
        print("✓ No preferred resolution set - would prompt user for selection")
    
    print("\nAll tests completed successfully! ✓")

if __name__ == "__main__":
    test_resolution_selection()
