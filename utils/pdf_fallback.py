"""
Fallback PDF generation for Windows builds
Uses xhtml2pdf instead of WeasyPrint when GTK libraries are not available
"""

import os
import sys
from io import BytesIO
from datetime import datetime

def is_weasyprint_available():
    """Check if WeasyPrint is available and working"""
    try:
        from weasyprint import HTML, CSS
        # Try to create a simple HTML to test if GTK libraries are available
        HTML(string="<html><body>Test</body></html>").write_pdf()
        return True
    except (ImportError, OSError, Exception):
        return False

def generate_pdf_fallback(html_content, css_content=None):
    """
    Generate PDF using xhtml2pdf as fallback
    
    Args:
        html_content (str): HTML content to convert
        css_content (str): CSS content (optional)
    
    Returns:
        bytes: PDF content
    """
    try:
        from xhtml2pdf import pisa
        
        # Combine HTML and CSS
        if css_content:
            html_with_css = f"""
            <html>
            <head>
                <style>
                {css_content}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """
        else:
            html_with_css = html_content
        
        # Create PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(
            src=BytesIO(html_with_css.encode('utf-8')),
            dest=result,
            encoding='utf-8'
        )
        
        if pdf.err:
            raise Exception(f"PDF generation failed with errors: {pdf.err}")
        
        return result.getvalue()
        
    except ImportError:
        raise Exception("Neither WeasyPrint nor xhtml2pdf is available for PDF generation")
    except Exception as e:
        raise Exception(f"PDF generation failed: {str(e)}")

def generate_pdf_smart(html_content, css_content=None):
    """
    Smart PDF generation that tries WeasyPrint first, falls back to xhtml2pdf
    
    Args:
        html_content (str): HTML content to convert
        css_content (str): CSS content (optional)
    
    Returns:
        bytes: PDF content
    """
    # Try WeasyPrint first
    if is_weasyprint_available():
        try:
            from weasyprint import HTML, CSS
            
            html_obj = HTML(string=html_content)
            
            if css_content:
                css_obj = CSS(string=css_content)
                return html_obj.write_pdf(stylesheets=[css_obj])
            else:
                return html_obj.write_pdf()
                
        except Exception as e:
            print(f"WeasyPrint failed, falling back to xhtml2pdf: {e}")
    
    # Fallback to xhtml2pdf
    return generate_pdf_fallback(html_content, css_content)

def get_pdf_engine_info():
    """Get information about the available PDF generation engine"""
    if is_weasyprint_available():
        return {
            'engine': 'WeasyPrint',
            'version': 'Available',
            'features': ['Full CSS support', 'Advanced layouts', 'Vector graphics']
        }
    else:
        try:
            import xhtml2pdf
            return {
                'engine': 'xhtml2pdf',
                'version': getattr(xhtml2pdf, '__version__', 'Unknown'),
                'features': ['Basic CSS support', 'Simple layouts', 'Fallback mode']
            }
        except ImportError:
            return {
                'engine': 'None',
                'version': 'N/A',
                'features': ['No PDF generation available']
            } 