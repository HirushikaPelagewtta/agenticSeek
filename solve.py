def transform_grid(grid):
    """Apply the transformation rule to the grid."""
    rows = len(grid)
    cols = len(grid[0])
    result = [row[:] for row in grid]  # Create a deep copy
    
    for i in range(rows):
        for j in range(cols):
            if grid[i][j] == 3:
                # Check if all four orthogonal neighbors exist and are 3
                # For a cell to have all four neighbors, it must not be on the edge
                if i > 0 and i < rows - 1 and j > 0 and j < cols - 1:
                    if (grid[i-1][j] == 3 and  # up
                        grid[i+1][j] == 3 and  # down
                        grid[i][j-1] == 3 and  # left
                        grid[i][j+1] == 3):    # right
                        result[i][j] = 4
    
    return result

def read_grid_from_file(filename):
    """Read grid from file."""
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    grid = []
    for line in lines:
        line = line.strip()
        if line:
            # Remove brackets and split by commas
            row_str = line.strip('[]')
            row = [int(x.strip()) for x in row_str.split(',')]
            grid.append(row)
    
    return grid

def main():
    # Read input from file
    try:
        grid = read_grid_from_file('test_input.txt')
        print(f"Read grid of size {len(grid)}x{len(grid[0])}")
    except FileNotFoundError:
        print("test_input.txt not found. Using hardcoded 20x20 grid with all 3s for testing.")
        # Create a 20x20 grid with all 3s for testing
        grid = [[3 for _ in range(20)] for _ in range(20)]
    
    # Apply transformation
    transformed = transform_grid(grid)
    
    # Print the result
    print("Transformed grid:")
    for row in transformed:
        print(row)
    
    # Save to output.txt
    with open('output.txt', 'w') as f:
        for row in transformed:
            f.write(str(row) + '\n')
    
    print(f"\nOutput saved to output.txt")

if __name__ == "__main__":
    main()
