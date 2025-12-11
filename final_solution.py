import json

def transform_grid(grid):
    # Transform all 1s to 2s
    transformed = []
    for row in grid:
        new_row = []
        for value in row:
            if value == 1:
                new_row.append(2)
            else:
                new_row.append(value)
        transformed.append(new_row)
    
    # Append first half of rows
    rows_count = len(transformed)
    half_count = rows_count // 2
    result = transformed + transformed[:half_count]
    
    return result

def main():
    # TEST INPUT
    test_input = [
        [1, 1, 1],
        [0, 1, 0],
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0],
        [0, 1, 0]
    ]
    
    # Transform the grid
    result = transform_grid(test_input)
    
    # Print JSON output
    print(json.dumps(result))

if __name__ == "__main__":
    main()
