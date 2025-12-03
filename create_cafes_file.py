
#!/usr/bin/env python3
"""
Script to create rennes_cafes.txt with the exact content specified.
Overwrites existing file if it exists.
"""

import os

def create_cafes_file():
    """Create rennes_cafes.txt with the exact content specified."""
    
    # Define the exact content as specified
    content = """Top 3 Cafes in Rennes, France

1. Café 1802
34 Rue d'Antrain, 35700 Rennes, France

2. Oh my Biche - COLOMBIER
3 Rue du Puits Mauger, 35000 Rennes, France

3. Bourbon d'Arsel - Torréfacteur et Coffee Shop
8 Rue de la Monnaie, 35000 Rennes, France"""
    
    # File path in current working directory
    file_path = os.path.join(os.getcwd(), "rennes_cafes.txt")
    
    # Write to file (overwrites if exists)
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)
    
    return file_path

if __name__ == "__main__":
    output_file = create_cafes_file()
    print(f"File successfully created: {output_file}")
    print(f"File size: {os.path.getsize(output_file)} bytes")
