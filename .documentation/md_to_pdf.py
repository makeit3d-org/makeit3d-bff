#!/usr/bin/env python3

"""
Markdown to PDF Converter
-------------------------
This script converts a Markdown file to PDF.
Dependencies: markdown2, weasyprint, pygments (for code highlighting)

Usage:
    python md_to_pdf.py input.md [output.pdf]
"""

import os
import sys
import markdown2
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

def convert_md_to_pdf(md_file, pdf_file=None):
    """Convert a Markdown file to PDF."""
    # Default output filename
    if pdf_file is None:
        pdf_file = os.path.splitext(md_file)[0] + '.pdf'
    
    print(f"Converting {md_file} to {pdf_file}...")
    
    # Read the Markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert Markdown to HTML
    # extras provides additional Markdown features like tables, code highlighting, footnotes
    html_content = markdown2.markdown(
        md_content,
        extras=[
            "fenced-code-blocks",
            "tables",
            "header-ids",
            "task_list",
            "footnotes",
            "smarty-pants",
            "code-friendly"
        ]
    )
    
    # Wrap the HTML content in a proper HTML document with basic styling
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{os.path.basename(md_file)}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 2em;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #333;
                margin-top: 1.5em;
                margin-bottom: 0.5em;
            }}
            h1 {{ font-size: 2.2em; }}
            h2 {{ font-size: 1.8em; }}
            h3 {{ font-size: 1.5em; }}
            h4 {{ font-size: 1.3em; }}
            code, pre {{
                background-color: #f5f5f5;
                border-radius: 3px;
                font-family: Consolas, Monaco, 'Andale Mono', monospace;
                padding: 0 3px;
            }}
            pre {{
                padding: 1em;
                overflow-x: auto;
            }}
            blockquote {{
                border-left: 4px solid #ddd;
                padding-left: 1em;
                color: #777;
                margin-left: 0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }}
            table, th, td {{
                border: 1px solid #ddd;
            }}
            th, td {{
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            img {{
                max-width: 100%;
            }}
            strong {{
                font-weight: bold;
            }}
            em {{
                font-style: italic;
            }}
            ul, ol {{
                padding-left: 2em;
            }}
            /* Page break style */
            .page-break {{ 
                page-break-after: always; 
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Create temporary HTML file
    temp_html = md_file + '.temp.html'
    with open(temp_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Configure font and render PDF
    font_config = FontConfiguration()
    html = HTML(filename=temp_html)
    css = CSS(string='''
        @page {
            margin: 1cm;
        }
    ''', font_config=font_config)
    
    # Generate PDF
    html.write_pdf(pdf_file, stylesheets=[css], font_config=font_config)
    
    # Remove temporary HTML file
    os.remove(temp_html)
    
    print(f"Successfully created {pdf_file}")
    return pdf_file

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: python md_to_pdf.py input.md [output.pdf]")
        sys.exit(1)
    
    md_file = sys.argv[1]
    pdf_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(md_file):
        print(f"Error: File '{md_file}' not found.")
        sys.exit(1)
    
    try:
        convert_md_to_pdf(md_file, pdf_file)
    except Exception as e:
        print(f"Error converting file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 