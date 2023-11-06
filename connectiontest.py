import socket
from threading import Thread

def acceptConnections():
    # Listen for incoming connections
    socket.listen(1)
    # Accept incoming connections
    print(f"Listening to connections at {address}")
    while True:
        clientSocket, clientAddress = socket.accept()
        print(f"Accepted connection from {clientAddress}")
        # Close the client socket
        clientSocket.close()

socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
address= ('', 7777)
socket.bind(address)

thread = Thread(target=acceptConnections, daemon=True)
thread.start()

print("enter 'q<enter>' to quit")
key = ""
while key != "q":
    key = input().lower()
