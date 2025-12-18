import os
import shutil

def build_site():
    with open('src/templates/index.html', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace Jinja2 static calls with relative paths
    content = content.replace("{{ url_for('static', filename='favicon.png') }}", "static/favicon.png")
    content = content.replace("{{ url_for('static', filename='paper.jpg') }}", "static/paper.jpg")
    content = content.replace("{{ url_for('static', filename='thumb.png', _external=True) }}", "static/thumb.png")
    content = content.replace("{{ request.url }}", "")
    
    # Ensure docs directory exists
    os.makedirs('docs', exist_ok=True)
    
    # Write to docs/index.html
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Generated docs/index.html")

    # Copy static files
    if os.path.exists('docs/static'):
        shutil.rmtree('docs/static')
    shutil.copytree('src/static', 'docs/static')
    print("Copied static files to docs/static")
    
    # Note: Create docs/CNAME manually with your custom domain if using GitHub Pages

if __name__ == '__main__':
    build_site()
