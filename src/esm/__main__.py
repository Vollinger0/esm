import sys

# entry file for when the package is called directly
def main() -> int:
    from esm import main
    main.start()

#print(f"{__file__} was called, __name__ is {__name__}")
if __name__ == '__main__':
    sys.exit(main())