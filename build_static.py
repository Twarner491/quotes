import os
import shutil
from flask import Flask, render_template

app = Flask(__name__, template_folder='src/templates', static_folder='src/static')

# Mock request context for url_for and request.url
@app.route('/')
def build():
    # We manually override url_for behavior or just let Flask generate relative paths?
    # Flask url_for('static', ...) usually generates /static/... 
    # For GitHub pages in a subdir, we might need relative ./static/
    # But usually /static/ is fine if custom domain is root.
    # Let's try to render and see.
    pass

def build_site():
    with app.test_request_context(base_url='https://receipt.onethreenine.net'):
        # Render the template
        # We need to mock 'request' object properties used in template
        # The template uses: url_for('static'), request.url
        
        # Hardcode the static path replacement for simplicity in this script
        # because flask url_for might not produce exactly what we want for a static file
        # relative to the HTML file.
        
        # Actually, let's just read the file and replace string for a robust "static" build
        # without running the flask app context complexity if we don't need to.
        
        with open('src/templates/index.html', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Replace Jinja2 static calls with relative paths
        # pattern: {{ url_for('static', filename='...') }}
        
        # Simple replacements for the specific known assets
        content = content.replace("{{ url_for('static', filename='favicon.png') }}", "static/favicon.png")
        content = content.replace("{{ url_for('static', filename='paper.jpg') }}", "static/paper.jpg")
        
        # For the thumb, it has _external=True. 
        # {{ url_for('static', filename='thumb.png', _external=True) }}
        # We want the public URL here.
        content = content.replace("{{ url_for('static', filename='thumb.png', _external=True) }}", "https://receipt.onethreenine.net/static/thumb.png")
        
        # Request URL
        content = content.replace("{{ request.url }}", "https://receipt.onethreenine.net/")
        
        # Write to docs/index.html
        with open('docs/index.html', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("Generated docs/index.html")

    # Copy static files
    if os.path.exists('docs/static'):
        shutil.rmtree('docs/static')
    shutil.copytree('src/static', 'docs/static')
    print("Copied static files to docs/static")

    # Create CNAME file for GitHub Pages
    with open('docs/CNAME', 'w', encoding='utf-8') as f:
        f.write('receipt.onethreenine.net')
    print("Created docs/CNAME")

if __name__ == '__main__':
    build_site()
