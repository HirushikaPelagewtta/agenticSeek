import sys

def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python factorial.py <number>")
        return
    
    try:
        num = int(sys.argv[1])
    except ValueError:
        print("Error: Please provide a valid integer")
        return
    
    if num < 0:
        print("Error: Factorial is not defined for negative numbers")
        return
    
    result = factorial(num)
    print(f"Factorial of {num} is {result}")

if __name__ == "__main__":
    main()
