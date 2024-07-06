import os
import sqlite3
import pandas as pd
import base64
import re
from flask import Flask, request, send_file, render_template

# Initialize Flask application
app = Flask(__name__)

# Base directory where your files are located
base_directory = os.path.dirname(__file__)
os.chdir(base_directory)

# Directory where CSS file is located
css_directory = os.path.join(base_directory, 'static')

# Directory where PDF images are stored
base_directory = r"Policies"
dest_folder = r"pdfimages"

# CSS styles (moved to CSS file)
CSS_STYLES = """
<style>
    mark { 
        padding: 0;
        background-color: transparent;
        color: inherit;
    }
    mark.highlight { 
        background-color: #ff0;
        font-weight: bold;
    }
    table {
        width: 100%;
    }
</style>
"""


def download_file(base_path, category, file_name):
    if not category:
        return "Category is empty."

    category_base_path = {
        'Contracts': os.path.join(base_path, 'Contracts'),
        'ISO': os.path.join(base_path, 'ISO'),
        'Policies': os.path.join(base_path, 'Policies'),
        'GDMS': os.path.join(base_path, 'GDMS')
    }
    if category not in category_base_path:
        return f"Invalid category: {category}"

    file_path = os.path.join(category_base_path[category], file_name)
    if os.path.exists(file_path):
        with open(file_path, "rb") as file:
            file_content = file.read()
            b64 = base64.b64encode(file_content).decode()
            href = (f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}"'
                    f'>Download {file_name}</a>')
            return href
    else:
        return f'File not found: {file_path}'


def view_page_link(category, filename, pagenumber):
    filename = re.sub(r'\.pdf$', '', filename)  # Remove the ".pdf" extension from the filename
    image_path = os.path.join(dest_folder, category, filename, f"{pagenumber}.png")
    if os.path.exists(image_path):
        return f'<a href="/view_image/{category}/{filename}/{pagenumber}" target="_blank">View Page</a>'
    else:
        return 'Image not found'


def search_data(db_name, keywords, category):
    conn = sqlite3.connect(db_name)

    if category and category != 'All':
        query = (f"SELECT filename, '{category}' AS category, pagenumber FROM "
                 f"{category.lower()} WHERE text LIKE ? OR filename LIKE ?")
        params = ('%' + keywords + '%', '%' + keywords + '%')
    else:
        query = (
            "SELECT filename, 'Contracts' AS category, pagenumber FROM contracts WHERE text LIKE ? OR filename LIKE ? "
            "UNION SELECT filename, 'Policies' AS category, pagenumber FROM policies WHERE text LIKE ? OR filename LIKE ? "
            "UNION SELECT filename, 'GDMS' AS category, pagenumber FROM GDMS WHERE text LIKE ? OR filename LIKE ? "
            "UNION SELECT filename, 'ISO' AS category, pagenumber FROM iso WHERE text LIKE ? OR filename LIKE ?"
        )
        params = (
            '%' + keywords + '%', '%' + keywords + '%',
            '%' + keywords + '%', '%' + keywords + '%',
            '%' + keywords + '%', '%' + keywords + '%',
            '%' + keywords + '%', '%' + keywords + '%',
        )
    # Fetch data with category
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    # Check if DataFrame is empty
    if df.empty:
        return df
    df.reset_index(drop=True, inplace=True)
    df.index = df.index + 1
    df.rename_axis('S.NO', axis=1, inplace=True)
    # Add download link and view page link columns
    df['View Page'] = df.apply(lambda row: view_page_link(row['category'], row['filename'], row['pagenumber']), axis=1)
    df['Download'] = df.apply(lambda row: download_file(base_directory, row['category'], row['filename']), axis=1)
    return df


def get_df2(db_name):
    conn = sqlite3.connect(db_name)
    # SQL query to select data with pagenumber 1 from all tables
    query = ("SELECT filename, 'Contracts' AS category, pagenumber "
             "FROM contracts WHERE pagenumber = 1 UNION SELECT filename, "
             "'Policies' AS category, pagenumber FROM policies WHERE pagenumber = 1 UNION SELECT filename, "
             "'ISO' AS category, pagenumber FROM iso WHERE pagenumber = 1 UNION SELECT filename, "
             "'GDMS' AS category, pagenumber FROM GDMS WHERE pagenumber = 1"
             )
    df2 = pd.read_sql_query(query, conn)
    conn.close()
    df2.reset_index(drop=True, inplace=True)
    df2 = df2.drop_duplicates(subset='filename', keep='first')
    df2.sort_values(by='category', inplace=True)
    df2.reset_index(drop=True, inplace=True)
    df2.drop('pagenumber', axis=1, inplace=True)
    df2.index = df2.index + 1
    df2.rename_axis('S.NO', axis=1, inplace=True)
    return df2


def generate_grouped_html_tables(grouped_df):
    html_code = ""
    for (filename, category), group in grouped_df.groupby(['filename', 'category']):
        filename = re.sub(r'\.pdf$', '', filename)
        # Add filename and category as the title of the group
        group_title = f"{filename} - {category}"
        html_code += f"<div class='group'><h2>{group_title}</h2>"

        # Generate HTML table for the group
        html_code += "<table>"
        # Add table headers
        html_code += "<tr>"
        for column in group.columns:
            html_code += f"<th>{column}</th>"
        html_code += "</tr>"
        # Add table rows
        for _, row in group.iterrows():
            html_code += "<tr>"
            for value in row:
                html_code += f"<td>{value}</td>"
            html_code += "</tr>"
        html_code += "</table></div>"

    return html_code


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/index_page")
def display_df2():
    df2 = get_df2("CHATBOT.db")
    return render_template('index_page.html', df2=df2)


@app.route("/search")
def search():
    keywords = request.args.get('keywords')
    category = request.args.get('category')
    df = search_data("CHATBOT.db", keywords, category if category else None)

    if df.empty:
        return render_template('search_results_empty.html', keywords=keywords)
    else:
        grouped_html_tables = generate_grouped_html_tables(df)
        return render_template('search_results.html', grouped_html_tables=grouped_html_tables)


@app.route("/view_image/<category>/<filename>/<int:pagenumber>")
def view_image(category, filename, pagenumber):
    filename = re.sub(r'\.pdf$', '', filename)
    image_path = os.path.join(dest_folder, category, filename, f"{pagenumber}.png")
    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/png')
    else:
        return f'Image not found at path: {image_path}'


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
