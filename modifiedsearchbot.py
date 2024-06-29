import os
import sqlite3
import pandas as pd
import base64
import re
from flask import Flask, request, send_file

directory = os.path.dirname(__file__)
os.chdir(directory)


app = Flask(__name__)

# Base directory where your files are located
base_directory = r"Policies"
dest_folder = r"pdfimag6"

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
        'Policies': os.path.join(base_path, 'Policies')
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

    # Prepare SQL query to select specific columns
    if category and category != 'All':
        query = (f"SELECT filename, '{category}' AS category, pagenumber FROM "
                 f"{category.lower()} WHERE text LIKE ? OR filename LIKE ?")
        params = ('%' + keywords + '%', '%' + keywords + '%')

    else:
        query = ("SELECT filename, 'Contracts' AS category, pagenumber"
                 " FROM contracts WHERE text LIKE ? OR filename LIKE ? UNION SELECT filename, "
                 "'Policies' AS category, pagenumber FROM policies WHERE text LIKE ? OR filename LIKE ? "
                 "UNION SELECT filename, 'ISO' AS category, pagenumber FROM iso WHERE text LIKE ? OR filename LIKE ?")
        params = ('%' + keywords + '%', '%' + keywords + '%',
                  '%' + keywords + '%', '%' + keywords + '%', '%' + keywords + '%', '%' + keywords + '%')

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
             "'ISO' AS category, pagenumber FROM iso WHERE pagenumber = 1")
    # Fetch data
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
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search Interface</title>
    <style>
        body {
            background-color: rgb(240, 240, 240);
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-size: cover; /* Use 'cover' to ensure the image covers the entire background */
            margin: 0; /* Remove default margin */
            padding: 0; /* Remove default padding */
            font-family: Arial, sans-serif; /* Use a generic font family */
        }
        /* Additional CSS styles can be added here */
        h1 {
            text-align: center; /* Center the heading */
            padding: 2% 0; /* Add padding to the heading */
            font-size: 30px; /* Set font size for the heading */
            position: relative; /* Position the icon relative to the heading */
        }
        /* Style for labels */
        label {
            font-weight: bold;
            display: block; /* Make labels block elements */
            margin-bottom: 1%; /* Add space below labels */
            font-size: 16px; /* Set font size for labels */
        }

        form {
            width: 30%; /* Set form width to 50% of the viewport */
            background-color: rgba(220, 220, 220, 0.5);
            margin: 0 auto; /* Center the form horizontally */
            margin-top: 5%; /* Add space from the top of the page */
            padding: 2%; /* Add padding to the entire form */
            border-radius: 10px; /* Add border radius for a rounded look */
        }

        /* Style the input fields and select dropdown */
        input[type="text"],
        select {
            padding: 2%; /* Add padding to input fields and select dropdown */
            width: 100%; /* Make input fields and select dropdown width 100% */
            box-sizing: border-box; /* Include padding and border in element's total width and height */
            margin-bottom: 2%; /* Add margin bottom to create space between elements */
            font-size: 16px; /* Set font size for input fields and select dropdown */
        }

        /* Style the search button */
        input[type="submit"] {
            padding: 2% 5%; /* Add padding to the search button */
            background-color: #007bff; /* Example color, you can change it */
            margin: 0 auto;
            color: white; /* Text color */
            border: none; /* Remove border */
            cursor: pointer; /* Change cursor to pointer on hover */
            display: block;
            font-size: 16px; /* Set font size for the button */
            border-radius: 5px; /* Add border radius for a rounded look */
        }

        /* Change button color on hover */
        input[type="submit"]:hover {
            background-color: #0056b3; /* Darker shade of blue */
        }

        /* Style the icon */
            .icon {
               display: inline-block; /* Make the icon inline with text */
               width: 25%; /* Set the width of the icon */
               height: auto; /* Let the height adjust automatically */
               margin-right: 10px; /* Add space between the icon and text */
               }
    </style>

</head>
<body>
<body>
 <style>
        h1 {
            font-size: 45px; /* Adjust the font size as needed */
            text-align: center; /* Center align the h1 heading */
            color: #004080;
        }
        h2 {
            font-size: 19px; /* Smaller font size for subheading */
            padding: 3px; /* Add padding around the heading */
            text-align: center; /* Center align the h2 heading */
            padding: 3px; /* Add padding on all four sides */
            color: black;
        }
    </style>
</head>
<body>
    <h1>
        <img src="/static/search bot.png"  class="icon"> <!-- Add your icon image here -->
    </h1>
    <h2>CONTRACTS, POLICIES, ISO SEARCH BOT</h2> <!-- Subheading added here -->

    <form action="/search" method="get">
    <br>
        <label for="keywords">KEYWORDS:</label>
        <input type="text" id="keywords" name="keywords" required><br><br>
        <label for="category">CATEGORY:</label>
        <select id="category" name="category">
            <option value="All">All</option>
            <option value="Contracts">Contracts</option>
            <option value="Policies">Policies</option>
            <option value="ISO">ISO</option>
        </select><br><br>
        <!-- Search button -->
        <input type="submit" value="Search">

        <!-- Index button -->
        <input type="button" value="Index" onclick="location.href='/index_page';">
    </form>
</body>
</html>
"""


@app.route("/index_page")
def display_df2():
    df2 = get_df2("fietails2.db")

    html_table = df2.to_html()

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Index Page</title>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Index Page</title>
    <style>
        body {{
            font-family: Arial, sans-serif; /* Use a generic font family */
            background-color: rgb(240, 240, 240);
            margin: 0;
            padding: 0;
        }}

        h1 {{
            text-align: center;
            padding: 20px 0;
            font-size: 24px;
        }}

        table {{
            width: 80%;
            margin: 0 auto;
            border-collapse: collapse;
            border: 1px solid #ddd;
        }}

        th, td {{
            padding: 12px;
            text-align: center;
            border: 1px solid #ddd;
        }}

        th {{
            background-color: #f2f2f2;
            text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <!-- Display df2 data in HTML table format -->
    {html_table}
</body>
</html>
"""


@app.route("/index")
def display_index():
    df2 = get_df2("fietails2.db")

    # Generate HTML table for df2 data
    html_table = df2.to_html()  # Convert DataFrame to HTML table without index

    # Return the HTML content with df2 data
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Index Page</title>
    <style>
        body {{
            font-family: Arial, sans-serif; /* Use a generic font family */
            background-color: rgb(240, 240, 240);
            margin: 0;
            padding: 0;
        }}

        table {{
            width: 80%;
            margin: 0 auto;
            border-collapse: collapse;
            border: 1px solid #ddd;
        }}

        th, td {{
            padding: 12px;
            text-align: center;
            border: 1px solid #ddd;
        }}

        th {{
            background-color: #f2f2f2;
            text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <!-- Display df2 data in HTML table format -->
    {html_table}
</body>
</html>
"""


@app.route("/search")
def search():
    db_name = "fietails2.db"
    keywords = request.args.get('keywords')
    category = request.args.get('category')

    # Fetch data based on keywords and category
    df = search_data(db_name, keywords, category if category else None)
    # Display results in HTML format
    if df.empty:
        return f"""

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search Results</title>
    <style>
        body {{
            background-color: rgb(240, 240, 240);
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-size: cover; /* Use 'cover' to ensure the image covers the entire background */
            margin: 0; /* Remove default margin */
            padding: 0; /* Remove default padding */
            font-family: Arial, sans-serif; /* Use a generic font family */
        }}
    </style>
</head>
<body>
   <h1>Search Results</h1>
    <p>No results found for keywords '{keywords}' in the selected category.</p>

    """
    else:
        # Group the DataFrame by filename and generate HTML tables for each group
        grouped_html_tables = generate_grouped_html_tables(df)
        # Return the complete HTML page with the HTML tables
        return f"""
</body>
</html>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search Results</title>
    <style>
        body {{
            font-family: Arial, sans-serif; /* Use a generic font family */
            background-color: rgb(240, 240, 240);
            margin: 0;
            padding: 0;
        }}

        h1 {{
            text-align: center;
            padding: 20px 0;
            font-size: 24px;
        }}

        table {{
            width: 80%;
            margin: 0 auto;
            border-collapse: collapse;
            border: 1px solid #ddd;
        }}

        th, td {{
            padding: 12px;
            text-align: center;
            border: 1px solid #ddd;
        }}

        th {{
            background-color: #f2f2f2;
            text-transform: uppercase;
        }}

             .group table {{
            display: none;
        }}

        /* Show table when its title is clicked */
        .group.active table {{
            display: table;
        }}
        /* Cursor style for clickable titles */
        .group h2 {{
            cursor: pointer;
            position: relative;
            left: 10%;
        }}
        .group h2::before {{
        content: attr(data-index) ". ";
        position: absolute;
        right: 100%;
         }}
                 #loading {{
            font-weight: bold;
            color: black;
            text-align: center;
            padding: 1.5% 0 ;
            font-size: 100%;
        }}
    </style>
    </head> 
    <body>
    <div id="loading">Fetching Data, Please Wait...</div>
    <h1>Search Results</h1>
    {grouped_html_tables}
<script>
    // Get all group titles
    const titles = document.querySelectorAll('.group h2');

    // Add index and click event listener to each title
    titles.forEach((title, index) => {{
        // Add index to the title
        title.setAttribute('data-index', index + 1);

        // Add click event listener to toggle 'active' class
        title.addEventListener('click', () => {{
            // Toggle the 'active' class on the parent div
            title.parentNode.classList.toggle('active');
        }});
    }});
</script>
    <script>
        // Wait for the page to load
        window.addEventListener('load', function() {{
            // Simulate fetching data (replace with actual data retrieval)
            setTimeout(function() {{
                // Show the table and hide the loading message
                document.getElementById('loading').style.display = 'none';
            }}, 2000); // Simulate a delay of 2 seconds (replace with actual data fetching)
        }});
    </script>
</body>
</html>
    </style>

"""


@app.route("/view_image/<category>/<filename>/<int:pagenumber>")
def view_image(category, filename, pagenumber):
    filename = re.sub(r'\.pdf$', '', filename)  # Remove the ".pdf" extension from the filename
    image_path = os.path.join(dest_folder, category, filename, f"{pagenumber}.png")
    if os.path.exists(image_path):
        return send_file(image_path, mimetype='image/png')
    else:
        return f'Image not found at path: {image_path}'


if __name__ == "__main__":
    # app.run(host='0.0.0.0', debug=True)
    app.run(host='0.0.0.0', debug=False)
