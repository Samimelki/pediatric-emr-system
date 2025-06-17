"""
PDF Generation Wrapper
Maintains full WeasyPrint compatibility for macOS while providing fallback for Windows
"""

import os
import sys
from io import BytesIO

def generate_pdf_with_fallback(html_content, stylesheets=None):
    """
    Generate PDF with automatic fallback support
    
    This function maintains 100% compatibility with existing WeasyPrint usage
    but provides fallback support for Windows builds where GTK libraries may not be available.
    
    Args:
        html_content (str): HTML content to convert
        stylesheets (list): List of CSS stylesheets (WeasyPrint CSS objects)
    
    Returns:
        bytes: PDF content
    """
    # First, try the normal WeasyPrint approach (works on macOS)
    try:
        from weasyprint import HTML, CSS
        
        html_obj = HTML(string=html_content)
        
        if stylesheets:
            return html_obj.write_pdf(stylesheets=stylesheets)
        else:
            return html_obj.write_pdf()
            
    except (ImportError, OSError) as e:
        # WeasyPrint failed (likely Windows without GTK), use fallback
        print(f"WeasyPrint unavailable ({e}), using fallback PDF generator...")
        return _generate_pdf_fallback(html_content, stylesheets)

def _generate_pdf_fallback(html_content, stylesheets=None):
    """
    Fallback PDF generation using xhtml2pdf
    
    Args:
        html_content (str): HTML content to convert
        stylesheets (list): List of WeasyPrint CSS objects (will be converted)
    
    Returns:
        bytes: PDF content
    """
    try:
        from xhtml2pdf import pisa
        
        # Convert WeasyPrint stylesheets to CSS strings
        css_content = ""
        if stylesheets:
            for stylesheet in stylesheets:
                # Extract CSS content from WeasyPrint CSS objects
                if hasattr(stylesheet, 'string'):
                    css_content += stylesheet.string + "\n"
                elif hasattr(stylesheet, 'content'):
                    css_content += stylesheet.content + "\n"
        
        # Combine HTML and CSS
        if css_content:
            html_with_css = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                {css_content}
                /* Additional fallback styles for xhtml2pdf compatibility */
                body {{
                    font-family: Arial, sans-serif;
                    font-size: 12px;
                    line-height: 1.4;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                .page-break {{
                    page-break-before: always;
                }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
        else:
            html_with_css = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                body {{
                    font-family: Arial, sans-serif;
                    font-size: 12px;
                    line-height: 1.4;
                }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
        
        # Create PDF using xhtml2pdf
        result = BytesIO()
        pdf = pisa.pisaDocument(
            src=BytesIO(html_with_css.encode('utf-8')),
            dest=result,
            encoding='utf-8'
        )
        
        if pdf.err:
            raise Exception(f"Fallback PDF generation failed with errors: {pdf.err}")
        
        return result.getvalue()
        
    except ImportError:
        raise Exception("Neither WeasyPrint nor xhtml2pdf is available for PDF generation")
    except Exception as e:
        raise Exception(f"Fallback PDF generation failed: {str(e)}")

def get_pdf_engine_status():
    """Get information about the available PDF generation engine"""
    try:
        from weasyprint import HTML, CSS
        # Test if WeasyPrint actually works
        HTML(string="<html><body>Test</body></html>").write_pdf()
        return {
            'primary_engine': 'WeasyPrint',
            'status': 'Available and working',
            'fallback_available': False
        }
    except (ImportError, OSError):
        try:
            import xhtml2pdf
            return {
                'primary_engine': 'xhtml2pdf (fallback)',
                'status': 'WeasyPrint unavailable, using fallback',
                'fallback_available': True
            }
        except ImportError:
            return {
                'primary_engine': 'None',
                'status': 'No PDF generation available',
                'fallback_available': False
            } 