import json
import urllib.parse
import os
from flask import Flask, render_template, request, redirect, url_for
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def extract_recipe_data(url):
    """Fetches the recipe page and extracts the Title and Ingredients."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- 1. EXTRACT TITLE ---
        # Look for the recipe title in common header tags
        title = "My Recipe"  # Default fallback
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)

        # --- 2. EXTRACT INGREDIENTS ---
        ingredients_text = ""
        
        # Priority 1: JSON-LD
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        for script in scripts:
            try:
                data = json.loads(script.string)
                data_list = data if isinstance(data, list) else [data]
                for item in data_list:
                    # Check for Recipe type
                    target = None
                    if item.get('@type') == 'Recipe':
                        target = item
                    elif isinstance(item, dict) and '@graph' in item:
                        for g in item['@graph']:
                            if g.get('@type') == 'Recipe':
                                target = g
                    
                    if target:
                        # Grab specific recipe name from JSON if available
                        if target.get('name'):
                            title = target.get('name')
                        ingredients = target.get('recipeIngredient', [])
                        if ingredients:
                            ingredients_text = "\n".join(ingredients)
                            return title, ingredients_text
            except:
                continue

        # Priority 2: HTML Fallback
        common_classes = ['wprm-recipe-ingredient', 'ingredient', 'recipe-ingredients', 'tasty-recipes-ingredients']
        found_ingredients = []
        for cls in common_classes:
            tags = soup.find_all(['li', 'span'], class_=lambda c: c and cls.lower() in c.lower())
            for tag in tags:
                txt = tag.get_text(strip=True)
                if len(txt.split()) > 1:
                    found_ingredients.append(txt)
            if found_ingredients:
                ingredients_text = "\n".join(sorted(list(set(found_ingredients))))
                return title, ingredients_text

        return title, "Error: Could not find ingredients."

    except Exception as e:
        return "Error", f"Failed to scrape: {e}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['recipe_url']
        recipe_title, ingredients = extract_recipe_data(url)

        if ingredients.startswith("Error"):
            return render_template('index.html', error=ingredients)

        # --- FORMAT FOR APPLE NOTES ---
        # First line is the Title, followed by a double space and bullet points
        full_note_content = f"{recipe_title.upper()}\n\n" + "• " + ingredients.replace('\n', '\n• ')
        
        encoded_text = urllib.parse.quote(full_note_content)
        shortcut_url = f"shortcuts://run-shortcut?name=Add%20to%20Notes&input=text&text={encoded_text}"

        return redirect(url_for('result', 
                                title=recipe_title, 
                                list_text=ingredients, 
                                shortcut_link=shortcut_url))
    
    return render_template('index.html')

@app.route('/result')
def result():
    title = request.args.get('title', 'Recipe')
    list_text = request.args.get('list_text', '')
    shortcut_link = request.args.get('shortcut_link', '#')
    
    # Send both the title and the ingredients to the template
    return render_template('result.html', 
                           recipe_title=title, 
                           display_list=list_text, 
                           shortcut_link=shortcut_link, 
                           raw_list=list_text)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
