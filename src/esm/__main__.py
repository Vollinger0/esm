import importlib
import sys

def getPackageVersion():
    return importlib.metadata.version(__package__)

# entry file for when the package is called directly
def main() -> int:
    from esm import main
    main.start()

#print(f"{__file__} was called, __name__ is {__name__}")
if __name__ == '__main__':
    sys.exit(main())