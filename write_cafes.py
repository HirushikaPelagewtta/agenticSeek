
#!/usr/bin/env python3
"""
Script to write cafe information from Rennes to a text file.
Uses data from web search about popular cafes in Rennes.
"""

import os

def write_cafes_to_file():
    """Write cafe information to a text file."""
    
    # Cafe data from the web search
    cafes = [
        {
            "name": "Café 1802",
            "address": "34 Rue d'Antrain, 35700 Rennes, France",
            "rating": "4.8/5 (459 avis)"
        },
        {
            "name": "Oh my Biche - COLOMBIER",
            "address": "3 Rue du Puits Mauger, 35000 Rennes, France",
            "rating": "4.5/5 (902 avis)"
        },
        {
            "name": "Bourbon d'Arsel - Torréfacteur et Coffee Shop",
            "address": "8 Rue de la Monnaie, 35000 Rennes, France",
            "rating": "4.6/5 (238 avis)"
        },
        {
            "name": "7 grammes",
            "address": "3 Rue Saint-Melaine, 35000 Rennes, France",
            "rating": "4.7/5 (368 avis)"
        },
        {
            "name": "Café Joyeux",
            "address": "14 Rue Vasselot, 35000 Rennes, France",
            "rating": "4.7/5 (727 avis)"
        }
    ]
    
    # File path in current working directory
    file_path = os.path.join(os.getcwd(), "rennes_cafes.txt")
    
    # Write to file
    with open(file_path, 'w', encoding='utf-8') as file:
        # Write header
        file.write("=" * 60 + "\n")
        file.write("BEST COFFEE SHOPS AND CAFES IN RENNES\n")
        file.write("=" * 60 + "\n\n")
        file.write("Data extracted from Wanderlog: 'The 39 best coffee shops and best cafes in Rennes'\n")
        file.write("URL: https://wanderlog.com/list/geoCategory/17381/best-coffee-shops-and-best-cafes-in-rennes\n\n")
        
        # Write each cafe entry
        for i, cafe in enumerate(cafes, 1):
            file.write(f"CAFE #{i}\n")
            file.write("-" * 40 + "\n")
            file.write(f"Name: {cafe['name']}\n")
            file.write(f"Address: {cafe['address']}\n")
            file.write(f"Rating: {cafe['rating']}\n")
            file.write("\n" + "=" * 60 + "\n\n")
    
    return file_path

if __name__ == "__main__":
    output_file = write_cafes_to_file()
    print(f"Cafe information successfully written to: {output_file}")
