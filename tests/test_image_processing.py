import pytest
import io
import base64
import sys
import os
from PIL import Image

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from utils.image_processing import (
    downscale_image,
    validate_image_format,
    get_image_format_from_bytes,
    apply_square_padding,
    estimate_compressed_size,
    calculate_scale_factor_for_size
)

def create_test_image(width: int, height: int, format_name: str = "PNG") -> bytes:
    """Create a test image with specified dimensions."""
    image = Image.new('RGB', (width, height), color='red')
    buffer = io.BytesIO()
    image.save(buffer, format=format_name)
    return buffer.getvalue()

def create_test_image_rgba(width: int, height: int) -> bytes:
    """Create a test RGBA image for transparency testing."""
    image = Image.new('RGBA', (width, height), color=(255, 0, 0, 128))  # Semi-transparent red
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()

class TestImageValidation:
    def test_validate_supported_formats(self):
        """Test validation of supported image formats."""
        # Test JPEG
        jpeg_image = create_test_image(100, 100, "JPEG")
        assert validate_image_format(jpeg_image) == True
        
        # Test PNG
        png_image = create_test_image(100, 100, "PNG")
        assert validate_image_format(png_image) == True
    
    def test_get_image_format_from_bytes(self):
        """Test format detection from bytes."""
        jpeg_image = create_test_image(100, 100, "JPEG")
        assert get_image_format_from_bytes(jpeg_image) == "JPEG"
        
        png_image = create_test_image(100, 100, "PNG")
        assert get_image_format_from_bytes(png_image) == "PNG"
    
    def test_invalid_image_data(self):
        """Test validation with invalid image data."""
        invalid_data = b"not an image"
        assert validate_image_format(invalid_data) == False

class TestSquarePadding:
    def test_square_padding_landscape(self):
        """Test square padding on landscape image."""
        # Create 300x200 image (landscape)
        original_image = Image.new('RGB', (300, 200), color='blue')
        
        # Apply square padding
        square_image = apply_square_padding(original_image)
        
        # Should be 300x300 (size of larger dimension)
        assert square_image.size == (300, 300)
        
        # Check that center pixel is still blue (from original image)
        center_pixel = square_image.getpixel((150, 100))  # Center of original image area
        assert center_pixel == (0, 0, 255)  # Blue
        
        # Check that padding areas are white
        top_padding = square_image.getpixel((150, 25))  # Top padding area
        assert top_padding == (255, 255, 255)  # White
    
    def test_square_padding_portrait(self):
        """Test square padding on portrait image."""
        # Create 200x300 image (portrait)
        original_image = Image.new('RGB', (200, 300), color='green')
        
        # Apply square padding
        square_image = apply_square_padding(original_image)
        
        # Should be 300x300 (size of larger dimension)
        assert square_image.size == (300, 300)
        
        # Check that center pixel is still green
        center_pixel = square_image.getpixel((100, 150))
        assert center_pixel == (0, 128, 0)  # Green
        
        # Check that padding areas are white
        left_padding = square_image.getpixel((25, 150))  # Left padding area
        assert left_padding == (255, 255, 255)  # White
    
    def test_square_padding_already_square(self):
        """Test square padding on already square image."""
        # Create 200x200 image (already square)
        original_image = Image.new('RGB', (200, 200), color='yellow')
        
        # Apply square padding
        square_image = apply_square_padding(original_image)
        
        # Should remain 200x200
        assert square_image.size == (200, 200)
        
        # All pixels should be yellow (no padding needed)
        center_pixel = square_image.getpixel((100, 100))
        assert center_pixel == (255, 255, 0)  # Yellow

class TestSizeEstimation:
    def test_estimate_compressed_size_jpeg(self):
        """Test JPEG size estimation."""
        size = estimate_compressed_size(1000, 1000, "JPEG", quality=85)
        assert isinstance(size, int)
        assert size > 0
        
        # Higher quality should result in larger size
        size_high = estimate_compressed_size(1000, 1000, "JPEG", quality=95)
        size_low = estimate_compressed_size(1000, 1000, "JPEG", quality=60)
        assert size_high > size_low
    
    def test_estimate_compressed_size_png(self):
        """Test PNG size estimation."""
        size = estimate_compressed_size(1000, 1000, "PNG")
        assert isinstance(size, int)
        assert size > 0
    
    def test_calculate_scale_factor(self):
        """Test scale factor calculation."""
        # Test with 1000x1000 image, target 500KB
        target_size = 500 * 1024  # 500KB
        scale_factor = calculate_scale_factor_for_size(1000, 1000, target_size, "JPEG")
        
        assert 0.1 <= scale_factor <= 1.0
        assert isinstance(scale_factor, float)

class TestDownscaleImage:
    def test_downscale_large_image(self):
        """Test downscaling a large image to smaller size."""
        # Create a large image (should be > 1MB)
        large_image = create_test_image(2000, 2000, "JPEG")
        original_size_mb = len(large_image) / (1024 * 1024)
        
        # Downscale to 0.5MB
        target_size_mb = 0.5
        downscaled = downscale_image(
            image_bytes=large_image,
            max_size_mb=target_size_mb,
            aspect_ratio_mode="original",
            output_format="original"
        )
        
        final_size_mb = len(downscaled) / (1024 * 1024)
        
        # Should be smaller than original and close to target
        assert final_size_mb < original_size_mb
        assert final_size_mb <= target_size_mb * 1.1  # Allow 10% tolerance
    
    def test_downscale_small_image_no_compression(self):
        """Test that small images aren't compressed if already under target."""
        # Create a small image
        small_image = create_test_image(100, 100, "PNG")
        original_size_mb = len(small_image) / (1024 * 1024)
        
        # Target size larger than current size
        target_size_mb = 5.0
        
        result = downscale_image(
            image_bytes=small_image,
            max_size_mb=target_size_mb,
            aspect_ratio_mode="original",
            output_format="original"
        )
        
        # Should maintain similar size (possibly slightly different due to re-encoding)
        final_size_mb = len(result) / (1024 * 1024)
        assert final_size_mb <= target_size_mb
    
    def test_downscale_with_square_padding(self):
        """Test downscaling with square padding."""
        # Create a rectangular image
        rect_image = create_test_image(400, 200, "PNG")  # 2:1 aspect ratio
        
        result = downscale_image(
            image_bytes=rect_image,
            max_size_mb=0.1,
            aspect_ratio_mode="square",
            output_format="original"
        )
        
        # Load result to check dimensions
        result_image = Image.open(io.BytesIO(result))
        width, height = result_image.size
        
        # Should be square
        assert width == height
        
        # Check file size
        final_size_mb = len(result) / (1024 * 1024)
        assert final_size_mb <= 0.1
    
    def test_format_conversion_rgba_to_jpeg(self):
        """Test converting RGBA image to JPEG (should handle transparency)."""
        # Create RGBA image
        rgba_image = create_test_image_rgba(200, 200)
        
        result = downscale_image(
            image_bytes=rgba_image,
            max_size_mb=0.5,
            aspect_ratio_mode="original",
            output_format="jpeg"
        )
        
        # Should successfully convert to JPEG
        result_format = get_image_format_from_bytes(result)
        assert result_format == "JPEG"
    
    def test_format_conversion_original_to_png(self):
        """Test converting to PNG format."""
        # Create JPEG image
        jpeg_image = create_test_image(300, 300, "JPEG")
        
        result = downscale_image(
            image_bytes=jpeg_image,
            max_size_mb=1.0,
            aspect_ratio_mode="original",
            output_format="png"
        )
        
        # Should be converted to PNG
        result_format = get_image_format_from_bytes(result)
        assert result_format == "PNG"
    
    def test_unsupported_format_error(self):
        """Test error handling for unsupported image formats."""
        invalid_data = b"not an image"
        
        with pytest.raises(ValueError, match="Unsupported image format"):
            downscale_image(
                image_bytes=invalid_data,
                max_size_mb=1.0,
                aspect_ratio_mode="original",
                output_format="original"
            )
    
    def test_invalid_output_format_error(self):
        """Test error handling for invalid output format."""
        valid_image = create_test_image(100, 100, "PNG")
        
        with pytest.raises(ValueError, match="Unsupported output format"):
            downscale_image(
                image_bytes=valid_image,
                max_size_mb=1.0,
                aspect_ratio_mode="original",
                output_format="invalid_format"
            )

class TestEdgeCases:
    def test_very_small_target_size(self):
        """Test with very small target size."""
        image = create_test_image(1000, 1000, "JPEG")
        
        # Target 10KB (very small)
        result = downscale_image(
            image_bytes=image,
            max_size_mb=0.01,  # 10KB
            aspect_ratio_mode="original",
            output_format="jpeg"
        )
        
        final_size_mb = len(result) / (1024 * 1024)
        assert final_size_mb <= 0.01 * 1.2  # Allow some tolerance for very small sizes
    
    def test_minimum_image_size(self):
        """Test with very small input image."""
        tiny_image = create_test_image(10, 10, "PNG")
        
        result = downscale_image(
            image_bytes=tiny_image,
            max_size_mb=1.0,
            aspect_ratio_mode="square",
            output_format="original"
        )
        
        # Should still work and be square
        result_image = Image.open(io.BytesIO(result))
        width, height = result_image.size
        assert width == height
        assert width >= 10  # Should not be smaller than original 