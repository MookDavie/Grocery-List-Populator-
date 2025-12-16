import json
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for
import requests
from bs4 import BeautifulSoup

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

        # 2. Look for JSON-LD structured data (Best method)
        scripts = soup.find_all('script', {'type': 'application/ld+json'})
        
        for script in scripts:
            try:
                data = json.loads(script.string)
                
                # Handle single object or list of objects in JSON-LD
                if not isinstance(data, list):
                    data = [data]
                    
                for item in data:
                    # Look for the main Recipe type
                    if item.get('@type') == 'Recipe':
                        ingredients = item.get('recipeIngredient', [])
                        if ingredients:
                            return "\n".join(ingredients)

            except json.JSONDecodeError:
                # Silently skip scripts that are not valid JSON
                continue
            
        # 3. Fallback: Search for common HTML tags (Less reliable)
        # We'll just look for common list items as a simple fallback
        # This will likely require manual tweaking for specific sites.
        ingredient_list = []
        for tag in soup.find_all(['li', 'span'], class_=lambda c: c and 'ingredient' in c.lower()):
            text = tag.get_text(strip=True)
            if text and len(text.split()) > 2 and 'cup' in text.lower() or 'tsp' in text.lower() or 'tbsp' in text.lower():
                 ingredient_list.append(text)
        
        if ingredient_list:
             # De-duplicate and return
             return "\n".join(sorted(list(set(ingredient_list))))

        return "Error: Could not find ingredients using standard methods."

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
        # Replace newlines with URL-encoded newlines (%0A)
        # Use '-' for better bullet points in Apple Notes (optional)
        formatted_list = raw_list.replace('\n', ' - ') 
        
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
    app.run(debug=True)