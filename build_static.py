import os
import shutil

def replace_jinja_templates(content, show_about=False):
    """Replace Jinja2 static calls with relative paths"""
    content = content.replace("{{ url_for('static', filename='favicon.png') }}", "static/favicon.png")
    content = content.replace("{{ url_for('static', filename='paper.jpg') }}", "static/paper.jpg")
    content = content.replace("{{ url_for('static', filename='thumb.png', _external=True) }}", "static/thumb.png")
    content = content.replace("{{ request.url }}", "")
    # Handle show_about variable
    content = content.replace("{{ 'true' if show_about else 'false' }}", "true" if show_about else "false")
    return content

def build_site():
    # Ensure docs directory exists
    os.makedirs('docs', exist_ok=True)
    
    # Build index.html
    with open('src/templates/index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    content = replace_jinja_templates(content, show_about=False)
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Generated docs/index.html")
    
    # Build about page (same template with show_about=True)
    with open('src/templates/index.html', 'r', encoding='utf-8') as f:
        about_content = f.read()
    about_content = replace_jinja_templates(about_content, show_about=True)
    
    # Fix paths for subdirectory (about/ needs ../static/)
    about_content = about_content.replace('href="static/', 'href="../static/')
    about_content = about_content.replace('url("static/', 'url("../static/')
    about_content = about_content.replace('content="static/', 'content="../static/')
    
    # Create about directory for clean URLs (/about instead of /about.html)
    os.makedirs('docs/about', exist_ok=True)
    with open('docs/about/index.html', 'w', encoding='utf-8') as f:
        f.write(about_content)
    print("Generated docs/about/index.html")

    # Copy static files
    if os.path.exists('docs/static'):
        shutil.rmtree('docs/static')
    shutil.copytree('src/static', 'docs/static')
    print("Copied static files to docs/static")
    
    # Note: Create docs/CNAME manually with your custom domain if using GitHub Pages

if __name__ == '__main__':
    build_site()
