import io
import logging
from typing import Tuple, Optional
from PIL import Image, ImageOps
import math

logger = logging.getLogger(__name__)

# Supported image formats (Shopify compatible)
SUPPORTED_FORMATS = {
    'JPEG': ['.jpg', '.jpeg'],
    'PNG': ['.png'],
    'GIF': ['.gif'],
    'WEBP': ['.webp'],
    'BMP': ['.bmp'],
    'TIFF': ['.tiff', '.tif']
}

def get_image_format_from_bytes(image_bytes: bytes) -> str:
    """Detect image format from bytes."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            return img.format
    except Exception as e:
        logger.error(f"Error detecting image format: {e}")
        raise ValueError("Unable to detect image format")

def validate_image_format(image_bytes: bytes) -> bool:
    """Validate if image format is supported."""
    try:
        format_name = get_image_format_from_bytes(image_bytes)
        return format_name in SUPPORTED_FORMATS.keys()
    except:
        return False

def estimate_compressed_size(width: int, height: int, format_name: str, quality: int = 85) -> int:
    """
    Estimate compressed file size in bytes for given dimensions and format.
    This is an approximation based on typical compression ratios.
    """
    pixels = width * height
    
    if format_name.upper() == 'JPEG':
        # JPEG compression estimation (bytes per pixel varies with quality)
        if quality >= 90:
            bytes_per_pixel = 1.5
        elif quality >= 80:
            bytes_per_pixel = 1.0
        elif quality >= 70:
            bytes_per_pixel = 0.7
        elif quality >= 60:
            bytes_per_pixel = 0.5
        else:
            bytes_per_pixel = 0.3
        return int(pixels * bytes_per_pixel)
    
    elif format_name.upper() == 'PNG':
        # PNG compression is lossless, typically 2-4 bytes per pixel
        bytes_per_pixel = 3.0
        return int(pixels * bytes_per_pixel)
    
    elif format_name.upper() == 'WEBP':
        # WebP compression similar to JPEG but more efficient
        if quality >= 90:
            bytes_per_pixel = 1.2
        elif quality >= 80:
            bytes_per_pixel = 0.8
        elif quality >= 70:
            bytes_per_pixel = 0.6
        else:
            bytes_per_pixel = 0.4
        return int(pixels * bytes_per_pixel)
    
    else:
        # Conservative estimate for other formats
        bytes_per_pixel = 3.0
        return int(pixels * bytes_per_pixel)

def calculate_scale_factor_for_size(
    current_width: int, 
    current_height: int, 
    target_size_bytes: int, 
    format_name: str
) -> float:
    """
    Calculate the scale factor needed to achieve target file size.
    Returns a scale factor between 0 and 1.
    """
    current_pixels = current_width * current_height
    
    # Binary search for the right scale factor
    min_scale = 0.1
    max_scale = 1.0
    tolerance = 0.05  # 5% tolerance
    
    for _ in range(20):  # Maximum 20 iterations
        mid_scale = (min_scale + max_scale) / 2
        new_width = int(current_width * mid_scale)
        new_height = int(current_height * mid_scale)
        
        estimated_size = estimate_compressed_size(new_width, new_height, format_name)
        
        if abs(estimated_size - target_size_bytes) / target_size_bytes < tolerance:
            return mid_scale
        elif estimated_size > target_size_bytes:
            max_scale = mid_scale
        else:
            min_scale = mid_scale
    
    # Return the scale factor that should be under the target
    return max_scale

def apply_square_padding(image: Image.Image, background_color: str = "white") -> Image.Image:
    """
    Add padding to make image square while maintaining aspect ratio.
    Centers the image in the square.
    """
    width, height = image.size
    max_dimension = max(width, height)
    
    # Create square canvas
    square_image = Image.new(image.mode, (max_dimension, max_dimension), background_color)
    
    # Calculate position to center the image
    x_offset = (max_dimension - width) // 2
    y_offset = (max_dimension - height) // 2
    
    # Paste the image onto the square canvas
    if image.mode == 'RGBA' or 'transparency' in image.info:
        square_image.paste(image, (x_offset, y_offset), image)
    else:
        square_image.paste(image, (x_offset, y_offset))
    
    return square_image

def get_optimal_save_params(format_name: str, target_size_bytes: int, image_size: Tuple[int, int]) -> dict:
    """
    Get optimal save parameters to achieve target file size.
    Returns dictionary of parameters for PIL save method.
    """
    width, height = image_size
    
    if format_name.upper() == 'JPEG':
        # Binary search for optimal quality
        min_quality = 20
        max_quality = 95
        
        for _ in range(10):  # Maximum 10 iterations
            mid_quality = (min_quality + max_quality) // 2
            estimated_size = estimate_compressed_size(width, height, format_name, mid_quality)
            
            if estimated_size <= target_size_bytes:
                min_quality = mid_quality + 1
            else:
                max_quality = mid_quality - 1
        
        return {
            'format': 'JPEG',
            'quality': max_quality,
            'optimize': True
        }
    
    elif format_name.upper() == 'PNG':
        return {
            'format': 'PNG',
            'optimize': True,
            'compress_level': 9  # Maximum compression
        }
    
    elif format_name.upper() == 'WEBP':
        # Binary search for optimal quality
        min_quality = 20
        max_quality = 95
        
        for _ in range(10):
            mid_quality = (min_quality + max_quality) // 2
            estimated_size = estimate_compressed_size(width, height, format_name, mid_quality)
            
            if estimated_size <= target_size_bytes:
                min_quality = mid_quality + 1
            else:
                max_quality = mid_quality - 1
        
        return {
            'format': 'WEBP',
            'quality': max_quality,
            'optimize': True
        }
    
    else:
        # For other formats, use default compression
        return {
            'format': format_name,
            'optimize': True
        }

def downscale_image(
    image_bytes: bytes,
    max_size_mb: float,
    aspect_ratio_mode: str,
    output_format: str = "original"
) -> bytes:
    """
    Downscale image to meet size requirements with aspect ratio control.
    
    Args:
        image_bytes: Input image as bytes
        max_size_mb: Maximum file size in megabytes
        aspect_ratio_mode: "original" or "square"
        output_format: "original", "jpeg", or "png"
    
    Returns:
        Processed image as bytes
    
    Raises:
        ValueError: If image format is unsupported or processing fails
    """
    try:
        # Validate input
        if not validate_image_format(image_bytes):
            raise ValueError("Unsupported image format")
        
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        original_format = image.format
        
        # Convert RGBA to RGB for JPEG output
        if output_format == "jpeg" and image.mode in ('RGBA', 'LA'):
            # Create white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'RGBA':
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
            else:
                background.paste(image)
            image = background
        
        # Determine target format
        if output_format == "original":
            target_format = original_format
        elif output_format == "jpeg":
            target_format = "JPEG"
        elif output_format == "png":
            target_format = "PNG"
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        # Calculate target size in bytes
        target_size_bytes = int(max_size_mb * 1024 * 1024)
        
        # Get current file size
        current_buffer = io.BytesIO()
        image.save(current_buffer, format=target_format, quality=85 if target_format == 'JPEG' else None)
        current_size = len(current_buffer.getvalue())
        
        logger.info(f"Original size: {current_size / (1024*1024):.2f}MB, Target: {max_size_mb}MB")
        
        # Check if already under target size
        if current_size <= target_size_bytes:
            logger.info("Image already under target size, applying aspect ratio mode only")
            if aspect_ratio_mode == "square":
                image = apply_square_padding(image)
            
            # Re-check size after padding
            final_buffer = io.BytesIO()
            save_params = get_optimal_save_params(target_format, target_size_bytes, image.size)
            image.save(final_buffer, **save_params)
            return final_buffer.getvalue()
        
        # Calculate scale factor needed
        original_width, original_height = image.size
        scale_factor = calculate_scale_factor_for_size(
            original_width, original_height, target_size_bytes, target_format
        )
        
        logger.info(f"Calculated scale factor: {scale_factor:.3f}")
        
        # Apply scaling
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Apply square padding if requested
        if aspect_ratio_mode == "square":
            image = apply_square_padding(image)
        
        # Save with optimal parameters
        final_buffer = io.BytesIO()
        save_params = get_optimal_save_params(target_format, target_size_bytes, image.size)
        image.save(final_buffer, **save_params)
        
        final_size = len(final_buffer.getvalue())
        logger.info(f"Final size: {final_size / (1024*1024):.2f}MB")
        
        # Verify size constraint
        if final_size > target_size_bytes:
            logger.warning(f"Final size ({final_size}) exceeds target ({target_size_bytes}), applying additional compression")
            # Additional compression attempt
            if target_format == 'JPEG':
                for quality in range(save_params.get('quality', 85) - 10, 10, -5):
                    final_buffer = io.BytesIO()
                    image.save(final_buffer, format='JPEG', quality=quality, optimize=True)
                    if len(final_buffer.getvalue()) <= target_size_bytes:
                        break
        
        return final_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise ValueError(f"Failed to process image: {str(e)}") 