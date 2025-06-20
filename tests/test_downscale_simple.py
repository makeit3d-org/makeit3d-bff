#!/usr/bin/env python3
"""
Simple test script for downscale functionality.
Can be run independently to test image processing without API setup.
"""

import sys
import os
import io
from pathlib import Path
from PIL import Image

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def create_test_image(width: int, height: int, format_name: str = "JPEG", color: str = "red") -> bytes:
    """Create a test image with specified properties."""
    if color == "red":
        color_rgb = (255, 0, 0)
    elif color == "blue":
        color_rgb = (0, 0, 255)
    elif color == "green":
        color_rgb = (0, 255, 0)
    else:
        color_rgb = (128, 128, 128)  # Gray
    
    image = Image.new('RGB', (width, height), color=color_rgb)
    buffer = io.BytesIO()
    image.save(buffer, format=format_name, quality=85 if format_name == 'JPEG' else None)
    return buffer.getvalue()

def test_downscale_basic():
    """Test basic downscaling functionality."""
    try:
        from utils.image_processing import downscale_image
        
        print("🧪 Testing basic downscaling...")
        
        # Create a large test image (about 2MB)
        large_image = create_test_image(2000, 2000, "JPEG")
        original_size_mb = len(large_image) / (1024 * 1024)
        print(f"   Original image: {original_size_mb:.2f}MB")
        
        # Downscale to 0.5MB
        target_size_mb = 0.5
        downscaled = downscale_image(
            image_bytes=large_image,
            max_size_mb=target_size_mb,
            aspect_ratio_mode="original",
            output_format="original"
        )
        
        final_size_mb = len(downscaled) / (1024 * 1024)
        print(f"   Downscaled image: {final_size_mb:.2f}MB (target: {target_size_mb}MB)")
        
        # Verify result
        assert final_size_mb <= target_size_mb * 1.1, f"Final size {final_size_mb:.2f}MB exceeds target {target_size_mb}MB"
        assert final_size_mb < original_size_mb, "Image should be smaller than original"
        
        print("   ✅ Basic downscaling test passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Basic downscaling test failed: {e}")
        return False

def test_square_padding():
    """Test square padding functionality."""
    try:
        from utils.image_processing import downscale_image
        
        print("🧪 Testing square padding...")
        
        # Create a rectangular image
        rect_image = create_test_image(800, 400, "PNG", "blue")  # 2:1 aspect ratio
        original_size_mb = len(rect_image) / (1024 * 1024)
        print(f"   Original rectangular image: 800x400, {original_size_mb:.2f}MB")
        
        # Apply square padding
        result = downscale_image(
            image_bytes=rect_image,
            max_size_mb=0.2,
            aspect_ratio_mode="square",
            output_format="png"
        )
        
        final_size_mb = len(result) / (1024 * 1024)
        
        # Check dimensions
        result_image = Image.open(io.BytesIO(result))
        width, height = result_image.size
        print(f"   Result image: {width}x{height}, {final_size_mb:.2f}MB")
        
        # Verify it's square
        assert width == height, f"Result should be square, got {width}x{height}"
        assert final_size_mb <= 0.2 * 1.1, f"Final size {final_size_mb:.2f}MB exceeds target 0.2MB"
        
        print("   ✅ Square padding test passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Square padding test failed: {e}")
        return False

def test_format_conversion():
    """Test format conversion functionality."""
    try:
        from utils.image_processing import downscale_image, get_image_format_from_bytes
        
        print("🧪 Testing format conversion...")
        
        # Create a PNG image
        png_image = create_test_image(600, 600, "PNG", "green")
        original_format = get_image_format_from_bytes(png_image)
        print(f"   Original format: {original_format}")
        
        # Convert to JPEG
        result = downscale_image(
            image_bytes=png_image,
            max_size_mb=0.3,
            aspect_ratio_mode="original",
            output_format="jpeg"
        )
        
        result_format = get_image_format_from_bytes(result)
        final_size_mb = len(result) / (1024 * 1024)
        print(f"   Result format: {result_format}, Size: {final_size_mb:.2f}MB")
        
        # Verify conversion
        assert result_format == "JPEG", f"Expected JPEG, got {result_format}"
        assert final_size_mb <= 0.3 * 1.1, f"Final size {final_size_mb:.2f}MB exceeds target 0.3MB"
        
        print("   ✅ Format conversion test passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Format conversion test failed: {e}")
        return False

def test_small_image_handling():
    """Test handling of images already smaller than target."""
    try:
        from utils.image_processing import downscale_image
        
        print("🧪 Testing small image handling...")
        
        # Create a small image
        small_image = create_test_image(100, 100, "PNG")
        original_size_mb = len(small_image) / (1024 * 1024)
        print(f"   Small image: {original_size_mb:.3f}MB")
        
        # Target much larger than current size
        target_size_mb = 5.0
        result = downscale_image(
            image_bytes=small_image,
            max_size_mb=target_size_mb,
            aspect_ratio_mode="original",
            output_format="original"
        )
        
        final_size_mb = len(result) / (1024 * 1024)
        print(f"   Result: {final_size_mb:.3f}MB (target: {target_size_mb}MB)")
        
        # Should not significantly increase size
        assert final_size_mb <= target_size_mb, f"Result size should not exceed target"
        # Allow some size variation due to re-encoding
        assert abs(final_size_mb - original_size_mb) < 0.1, "Size should not change dramatically for small images"
        
        print("   ✅ Small image handling test passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Small image handling test failed: {e}")
        return False

def test_image_validation():
    """Test image validation functionality."""
    try:
        from utils.image_processing import validate_image_format, downscale_image
        
        print("🧪 Testing image validation...")
        
        # Test valid image
        valid_image = create_test_image(100, 100, "JPEG")
        assert validate_image_format(valid_image), "Valid image should pass validation"
        
        # Test invalid data
        invalid_data = b"not an image"
        assert not validate_image_format(invalid_data), "Invalid data should fail validation"
        
        # Test downscaling with invalid data (should raise exception)
        try:
            downscale_image(invalid_data, 1.0, "original", "original")
            assert False, "Should have raised exception for invalid image"
        except ValueError:
            pass  # Expected
        
        print("   ✅ Image validation test passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Image validation test failed: {e}")
        return False

def save_test_outputs():
    """Save test output images for manual inspection."""
    try:
        from utils.image_processing import downscale_image
        
        print("💾 Saving test outputs...")
        
        # Create output directory
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        
        # Test 1: Large to small downscaling
        large_image = create_test_image(2000, 1500, "JPEG", "red")
        downscaled = downscale_image(large_image, 0.2, "original", "jpeg")
        
        with open(output_dir / "test_downscale_large_to_small.jpg", "wb") as f:
            f.write(downscaled)
        
        # Test 2: Square padding
        rect_image = create_test_image(800, 400, "PNG", "blue")
        square_result = downscale_image(rect_image, 0.15, "square", "png")
        
        with open(output_dir / "test_downscale_square_padding.png", "wb") as f:
            f.write(square_result)
        
        # Test 3: Format conversion
        png_image = create_test_image(600, 600, "PNG", "green")
        jpeg_result = downscale_image(png_image, 0.1, "original", "jpeg")
        
        with open(output_dir / "test_downscale_format_conversion.jpg", "wb") as f:
            f.write(jpeg_result)
        
        print(f"   💾 Test outputs saved to {output_dir}")
        print("   🔍 You can manually inspect these files to verify quality")
        return True
        
    except Exception as e:
        print(f"   ❌ Failed to save test outputs: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Running downscale functionality tests...\n")
    
    tests = [
        test_image_validation,
        test_downscale_basic,
        test_square_padding,
        test_format_conversion,
        test_small_image_handling,
        save_test_outputs
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   💥 Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Empty line between tests
    
    print("📊 Test Results:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Downscale functionality is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 