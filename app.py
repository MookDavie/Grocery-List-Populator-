import json
import urllib.parse
import os # Added for optional deployment port configuration
from flask import Flask, render_template, request, redirect, url_for
import requests
from bs4 import BeautifulSoup

# Correct Flask initialization
app = Flask(__name__)

def extract_ingredients(url):
    """Fetches the recipe page and extracts ingredients, prioritizing JSON-LD."""
    try:
        # 1. Fetch the page content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raise exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # --- EXTRACT TITLE ---
        # Look for the recipe title in common header tags
        title = "My Recipe"  # Default fallback
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 2. Robust JSON-LD Structured Data Check (PRIORITY 1)
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Handle single object, or list of objects, or nested @graph structure
                data_list = data if isinstance(data, list) else [data]
                
                for item in data_list:
                    # Look for Recipe type directly
                    if item.get('@type') == 'Recipe':
                        ingredients = item.get('recipeIngredient', [])
                        if ingredients:
                            return "\n".join(ingredients)
                    
                    # Look inside a nested @graph structure
                    if isinstance(item, dict) and '@graph' in item:
                        for graph_item in item['@graph']:
                            if graph_item.get('@type') == 'Recipe':
                                ingredients = graph_item.get('recipeIngredient', [])
                                if ingredients:
                                    return "\n".join(ingredients)

            except json.JSONDecodeError:
                # Silently skip scripts that are not valid JSON
                continue
            
        # 3. Targeted HTML Fallback (PRIORITY 2)
        
        # List of common CSS class names for ingredient containers/list items
        common_ingredient_classes = [
            'wprm-recipe-ingredient',      # WP Recipe Maker plugin
            'ingredient',
            'ingredients',
            'recipe-ingredients',
            'list-ingredients',
            'tasty-recipes-ingredients',   # Common food blog plugin
            'pantry-list',
            'recipeIngredient',            # Common itemprop tag
            'o-Ingredients__a-Ingredient'  # Example specific site class (e.g., Food Network)
        ]
        
        ingredient_list = []
        
        for class_name in common_ingredient_classes:
            # Find list items or spans/divs with the ingredient class
            found_tags = soup.find_all(
                ['li', 'span', 'div'], 
                class_=lambda c: c and class_name.lower() in c.lower()
            )
            
            for tag in found_tags:
                text = tag.get_text(strip=True)
                
                # Simple validation: must contain some text and likely a measurement unit
                if text and len(text.split()) > 1 and any(unit in text.lower() for unit in ['cup', 'tsp', 'tbsp', 'oz', 'gram', 'ml']):
                    # Filter out instructional text often included in ingredient containers
                    if 'cook time' not in text.lower() and 'directions' not in text.lower():
                        ingredient_list.append(text)

            # If we find a good list, use it and stop searching other classes
            if ingredient_list:
                # Use set to de-duplicate, then sort and join
                return "\n".join(sorted(list(set(ingredient_list))))
                
        # 4. Final Fail State
        return "Error: Could not find ingredients using structured data or common HTML methods."

    except requests.exceptions.RequestException as e:
        return f"Error connecting to URL: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        recipe_url = request.form['recipe_url']
        
        # 1. Get the raw ingredient list text
        raw_list = extract_ingredients(recipe_url)

        if raw_list.startswith("Error"):
            # If there's an error, just render the template with the message
            return render_template('index.html', error=raw_list)

        # 2. Format the list for Notes and URL scheme
        # Replace newlines with a bullet and space for better readability in Notes
        formatted_list = "• " + raw_list.replace('\n', '\n• ') 
        
        # 3. URL-encode the final text string for the Shortcuts link
        encoded_list = urllib.parse.quote(formatted_list)
        
        # 4. Construct the Apple Shortcuts URL
        # NOTE: The user must have a pre-made Shortcut named 'Add to Notes'
        shortcut_name = "Add to Notes" 
        shortcuts_url = f"shortcuts://run-shortcut?name={urllib.parse.quote(shortcut_name)}&input=text&text={encoded_list}"

        # Redirect the user to a page that contains the list and the direct link
        return redirect(url_for('result', list_text=raw_list, shortcut_link=shortcuts_url))
    
    return render_template('index.html')

@app.route('/result')
def result():
    list_text = request.args.get('list_text', "No list generated.")
    shortcut_link = request.args.get('shortcut_link', '#')
    
    # We use <br> for displaying the list nicely on the result page
    display_list = list_text.replace('\n', '<br>')
    
    return render_template('result.html', display_list=display_list, shortcut_link=shortcut_link, raw_list=list_text)

if __name__ == '__main__':
    # Use Gunicorn in production (deployment), but this runs for local testing
    # Uses 0.0.0.0 host for compatibility in containerized environments (like Docker/Render)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

