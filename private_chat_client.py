import argparse
import codecs
import socket
import threading

PROMPT = "> "


def receive_messages(sock, disconnected, leaving):
    """Thread: print everything the server sends, as soon as it arrives."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    while True:
        try:
            data = sock.recv(4096)
        except OSError:
            break
        if not data:
            break
        text = decoder.decode(data).rstrip("\n")
        if text:
            print(f"\r{text}\n{PROMPT}", end="", flush=True)
    disconnected.set()
    if not leaving.is_set():
        print("\n disconnected from server - press enter to exit", flush=True)


def run_client(host="127.0.0.1", port=5000, name=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"connecting to {host}:{port}...")
    try:
        sock.connect((host, port))
    except ConnectionRefusedError:
        print("Could not connect to server")
        return

    print("Connected! type /help for commands, 'quit' to exit.")
    print("Send with:  @name msg  |  @name1,name2 msg  |  /to name1,name2  |  /all msg")
    print("-" * 50)

    disconnected = threading.Event()
    leaving = threading.Event()
    threading.Thread(target=receive_messages,
                     args=(sock, disconnected, leaving),
                     daemon=True).start()
    try:
        if name:                                    # name given on the command line
            sock.sendall((name.strip() + "\n").encode("utf-8"))

        while not disconnected.is_set():
            try:
                line = input(PROMPT)
            except EOFError:                        # Ctrl+D / closed stdin
                line = "quit"
            if disconnected.is_set():
                break
            if not line.strip():
                continue
            sock.sendall((line + "\n").encode("utf-8"))
            if line.strip().lower() in ("quit", "/quit"):
                print("Leaving chat...")
                break
    except KeyboardInterrupt:
        print("\nLeaving chat...")
        try:
            sock.sendall(b"quit\n")
        except OSError:
            pass
    except OSError as e:
        print(f"\nConnection error: {e}")
    finally:
        leaving.set()
        sock.close()
        print("Connection closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-client private chat client")
    parser.add_argument("name", nargs="?", help="your chat name (asked if omitted)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    run_client(args.host, args.port, args.name)
