import io
import base64
from typing import Optional, Tuple, Union
from io import BytesIO

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False
    print("Warning: cairosvg not available. SVG conversion will be limited.")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Image processing will be limited.")


class SvgConverter:
    """Convert SVG graphics to PNG format for PowerPoint"""
    
    def __init__(self):
        if not CAIROSVG_AVAILABLE:
            raise ImportError(
                "cairosvg is required for SVG conversion. "
                "Install with: pip install cairosvg"
            )
    
    def svg_to_png(
        self,
        svg_content: str,
        width: int = 256,
        height: int = 256,
        scale: int = 3
    ) -> bytes:
        """
        Convert SVG string to PNG bytes
        
        Args:
            svg_content: SVG XML string
            width: Output width in pixels
            height: Output height in pixels
            scale: Scale factor for higher DPI (3 = 3x resolution)
            
        Returns:
            PNG image as bytes
        """
        # Scale for high DPI
        output_width = width * scale
        output_height = height * scale
        
        png_data = cairosvg.svg2png(
            bytestring=svg_content.encode('utf-8'),
            output_width=output_width,
            output_height=output_height
        )
        
        return png_data
    
    def svg_to_png_with_color(
        self,
        svg_content: str,
        color: str,
        width: int = 256,
        height: int = 256,
        scale: int = 3
    ) -> bytes:
        """
        Convert SVG to PNG with color replacement
        
        Args:
            svg_content: SVG XML string
            color: Hex color (e.g., '#3B82F6') to replace currentColor
            width: Output width
            height: Output height
            scale: DPI scale factor
            
        Returns:
            PNG image as bytes
        """
        # Replace currentColor with specified color
        svg_colored = svg_content.replace('currentColor', color)
        svg_colored = svg_colored.replace('fill="currentColor"', f'fill="{color}"')
        svg_colored = svg_colored.replace('stroke="currentColor"', f'stroke="{color}"')
        
        return self.svg_to_png(svg_colored, width, height, scale)
    
    def svg_to_bytesio(
        self,
        svg_content: str,
        width: int = 256,
        height: int = 256,
        color: Optional[str] = None,
        scale: int = 3
    ) -> BytesIO:
        """
        Convert SVG to BytesIO object (ready for python-pptx)
        
        Args:
            svg_content: SVG XML string
            width: Output width
            height: Output height
            color: Optional color override
            scale: DPI scale factor
            
        Returns:
            BytesIO object containing PNG data
        """
        if color:
            png_data = self.svg_to_png_with_color(svg_content, color, width, height, scale)
        else:
            png_data = self.svg_to_png(svg_content, width, height, scale)
        
        return BytesIO(png_data)
    
    def svg_to_pil_image(
        self,
        svg_content: str,
        width: int = 256,
        height: int = 256,
        color: Optional[str] = None,
        scale: int = 3
    ) -> Optional['Image.Image']:
        """
        Convert SVG to PIL Image object
        
        Args:
            svg_content: SVG XML string
            width: Output width
            height: Output height
            color: Optional color override
            scale: DPI scale factor
            
        Returns:
            PIL Image object or None if PIL unavailable
        """
        if not PIL_AVAILABLE:
            return None
        
        png_bytes = self.svg_to_bytesio(svg_content, width, height, color, scale)
        return Image.open(png_bytes)
    
    def optimize_png(self, png_data: bytes, quality: int = 85) -> bytes:
        """
        Optimize PNG file size while maintaining quality
        
        Args:
            png_data: Original PNG bytes
            quality: Quality level (1-100)
            
        Returns:
            Optimized PNG bytes
        """
        if not PIL_AVAILABLE:
            return png_data
        
        try:
            # Open image
            image = Image.open(BytesIO(png_data))
            
            # Convert to RGB if RGBA
            if image.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
                image = background
            
            # Save optimized
            output = BytesIO()
            image.save(output, format='PNG', optimize=True, quality=quality)
            return output.getvalue()
        
        except Exception as e:
            print(f"PNG optimization failed: {e}")
            return png_data
    
    def batch_convert(
        self,
        svg_list: list[Tuple[str, str]],
        width: int = 256,
        height: int = 256,
        scale: int = 3
    ) -> dict[str, BytesIO]:
        """
        Convert multiple SVGs at once
        
        Args:
            svg_list: List of tuples (name, svg_content)
            width: Output width
            height: Output height
            scale: DPI scale factor
            
        Returns:
            Dictionary mapping names to BytesIO objects
        """
        results = {}
        
        for name, svg_content in svg_list:
            try:
                results[name] = self.svg_to_bytesio(svg_content, width, height, None, scale)
            except Exception as e:
                print(f"Failed to convert {name}: {e}")
        
        return results


class SvgColorManipulator:
    """Utilities for manipulating SVG colors"""
    
    @staticmethod
    def replace_color(svg_content: str, old_color: str, new_color: str) -> str:
        """Replace specific color in SVG"""
        return svg_content.replace(old_color, new_color)
    
    @staticmethod
    def apply_gradient(svg_content: str, start_color: str, end_color: str) -> str:
        """Apply gradient to SVG (basic implementation)"""
        # Create gradient definition
        gradient_id = "grad1"
        gradient_def = f'''
        <defs>
            <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:{start_color};stop-opacity:1" />
                <stop offset="100%" style="stop-color:{end_color};stop-opacity:1" />
            </linearGradient>
        </defs>
        '''
        
        # Replace solid fills with gradient
        svg_with_gradient = svg_content.replace(
            '<svg',
            f'<svg{gradient_def}'
        )
        svg_with_gradient = svg_with_gradient.replace(
            'fill="currentColor"',
            f'fill="url(#{gradient_id})"'
        )
        
        return svg_with_gradient
    
    @staticmethod
    def adjust_opacity(svg_content: str, opacity: float) -> str:
        """Adjust SVG opacity (0.0 to 1.0)"""
        # Add opacity to svg root element
        if 'opacity=' in svg_content:
            import re
            svg_content = re.sub(r'opacity="[\d.]+"', f'opacity="{opacity}"', svg_content)
        else:
            svg_content = svg_content.replace('<svg', f'<svg opacity="{opacity}"')
        
        return svg_content


# Convenience functions
def quick_svg_to_png(svg_content: str, width: int = 256, color: str = "#000000") -> BytesIO:
    """Quick conversion function"""
    converter = SvgConverter()
    return converter.svg_to_bytesio(svg_content, width, width, color)


def convert_icon_for_pptx(svg_content: str, size_inches: float, color: str) -> BytesIO:
    """
    Convert icon specifically for PowerPoint insertion
    
    Args:
        svg_content: SVG string
        size_inches: Desired size in inches
        color: Hex color
        
    Returns:
        BytesIO ready for pptx.shapes.add_picture()
    """
    # Convert inches to pixels at 72 DPI
    size_pixels = int(size_inches * 72)
    
    converter = SvgConverter()
    return converter.svg_to_bytesio(
        svg_content=svg_content,
        width=size_pixels,
        height=size_pixels,
        color=color,
        scale=4  # High quality for presentations
    )
