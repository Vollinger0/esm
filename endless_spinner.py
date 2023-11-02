from halo import Halo

print("Starting sleep phase, press CTRL+C to end.")
with Halo(text="Running", spinner="dots") as spinner:
    try:
        while True:
            pass
    except KeyboardInterrupt:
        spinner.succeed("Stopped")

print("The end.")

