#!/usr/bin/env python3

import argparse
import re
import socket
import threading
import time

NAME_RE = re.compile(r"^[\w.-]{1,20}$")          # letters/digits/_ . -  (Unicode OK)
RESERVED_NAMES = {"all", "you", "server"}

HELP_TEXT = """\
Commands:
  @name message        private message to one user
  @n1,n2 message       message to several users (also: @n1 @n2 message)
  /to n1,n2            set default recipients (plain text then goes to them)
  /to                  show current default recipients
  /clear               clear default recipients
  /all message         send to everyone (broadcast)
  /list                list online users
  /help                show this help
  quit                 leave the chat"""


class Client:
    """State kept by the server for one connected client."""

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.name = None               # display name (set after registration)
        self.default_targets = []      # names used for plain-text messages
        self._send_lock = threading.Lock()

    def send(self, text):
        data = (text.rstrip("\n") + "\n").encode("utf-8")
        try:
            with self._send_lock:      # avoid interleaving from several threads
                self.sock.sendall(data)
            return True
        except OSError:
            return False


clients = {}                          # lower-case name -> Client
clients_lock = threading.Lock()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def online_snapshot():
    with clients_lock:
        return dict(clients)


def broadcast(text, exclude=None):
    count = 0
    for c in online_snapshot().values():
        if c is not exclude and c.send(text):
            count += 1
    return count



def parse_names(spec):
    names, seen = [], set()
    for part in spec.split(","):
        n = part.strip().lstrip("@")
        if n and n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    return names


def split_recipients(line):
    specs, rest = [], line
    while rest.startswith("@"):
        token, _, rest = rest.partition(" ")
        specs.append(token[1:])
        rest = rest.lstrip()
    return parse_names(",".join(specs)), rest


def resolve(sender, names):
    snap = online_snapshot()
    found, missing, to_self = [], [], False
    for n in names:
        key = n.lower()
        if key == sender.name.lower():
            to_self = True
        elif key in snap:
            found.append(snap[key])
        else:
            missing.append(n)
    return found, missing, to_self


def deliver(sender, names, message):
    if not message:
        sender.send("Empty message - nothing sent.")
        return
    found, missing, to_self = resolve(sender, names)
    if to_self:
        sender.send(" You cannot send a message to yourself.")
    if missing:
        sender.send(f"Not online: {', '.join(missing)}")
    if not found:
        sender.send(" Message not delivered (no valid recipients).")
        return

    recipient_names = [c.name for c in found]
    delivered = []
    for c in found:
        others = [n for n in recipient_names if n != c.name]
        label = "you" if not others else "you, " + ", ".join(others)
        if c.send(f"[{sender.name} -> {label}] {message}"):
            delivered.append(c.name)

    if delivered:
        sender.send(f"[sent to {', '.join(delivered)}]")
        log(f"{sender.name} -> {', '.join(delivered)}: {message}")
    failed = [n for n in recipient_names if n not in delivered]
    if failed:
        sender.send(f"[!] Delivery failed for: {', '.join(failed)}")


# ---------------------------------------------------------------------------
# Command handling
# ---------------------------------------------------------------------------
def handle_line(client, line):
    cmd, _, arg = line.partition(" ")
    cmd_l, arg = cmd.lower(), arg.strip()

    if line.lower() == "quit" or cmd_l == "/quit":
        client.send("Bye!")
        return False

    if cmd_l == "/help":
        client.send(HELP_TEXT)

    elif cmd_l == "/list":
        names = sorted((c.name for c in online_snapshot().values()), key=str.lower)
        shown = [f"{n} (you)" if n == client.name else n for n in names]
        client.send(f"Online ({len(names)}): {', '.join(shown)}")

    elif cmd_l == "/to":
        if not arg:
            current = ", ".join(client.default_targets) or "(none)"
            client.send(f"Default recipients: {current}")
        else:
            found, missing, to_self = resolve(client, parse_names(arg.replace(" ", ",")))
            if to_self:
                client.send("You cannot add yourself as a recipient.")
            if missing:
                client.send(f" Not online (ignored): {', '.join(missing)}")
            client.default_targets = [c.name for c in found]
            if found:
                client.send(f"Default recipients set to: {', '.join(client.default_targets)}"
                            " - plain messages now go to them.")
            else:
                client.send(" No valid recipients - default recipients cleared.")

    elif cmd_l == "/clear":
        client.default_targets = []
        client.send("Default recipients cleared.")

    elif cmd_l == "/all":
        if not arg:
            client.send("[!] Usage: /all message")
        else:
            n = broadcast(f"[{client.name} -> all] {arg}", exclude=client)
            client.send(f"[sent to all ({n} users)]")
            log(f"{client.name} -> ALL: {arg}")

    elif line.startswith("@"):
        names, message = split_recipients(line)
        if not names:
            client.send(" Usage: @name message")
        else:
            deliver(client, names, message)

    elif line.startswith("/"):
        client.send(f" Unknown command '{cmd}'. Type /help")

    else:  # plain text -> default recipients (if any)
        if client.default_targets:
            deliver(client, client.default_targets, line)
        else:
            client.send(" No recipient chosen. Use '@name message', "
                        "'/to name' or '/all message'. Type /help")
    return True


# ---------------------------------------------------------------------------
# Per-client thread
# ---------------------------------------------------------------------------
def register(client, reader):
    client.send("Enter your name:")
    for raw in reader:
        name = raw.strip()
        if not NAME_RE.match(name) or name.lower() in RESERVED_NAMES:
            client.send(" Invalid name. Try again:")
            continue
        with clients_lock:
            taken = name.lower() in clients
            if not taken:
                client.name = name
                clients[name.lower()] = client
        if taken:
            client.send(f"The name '{name}' is already taken. Try another:")
            continue
        return True
    return False


def handle_client(sock, addr):
    client = Client(sock, addr)
    log(f"New connection from {addr}")
    reader = sock.makefile("r", encoding="utf-8", errors="replace", newline="\n")
    try:
        if not register(client, reader):
            return
        log(f"{client.name} joined from {addr}")
        names = sorted((c.name for c in online_snapshot().values()), key=str.lower)
        client.send(f"Welcome {client.name}! Type /help for commands.\n"
                    f"Online ({len(names)}): {', '.join(names)}")
        broadcast(f"*** {client.name} has joined the chat ***", exclude=client)

        for raw in reader:
            line = raw.strip()
            if line and not handle_line(client, line):
                break
    except OSError as e:
        log(f"Connection error with {addr}: {e}")
    finally:
        if client.name:
            with clients_lock:
                clients.pop(client.name.lower(), None)
            broadcast(f"*** {client.name} has left the chat ***")
            log(f"{client.name} disconnected")
        try:
            reader.close()
        except OSError:
            pass
        sock.close()
        log(f"Connection closed for {addr}")


def run_server(host="127.0.0.1", port=5000):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(10)
    server_socket.settimeout(1.0)          # lets Ctrl+C work on Windows too

    print(f"Private Chat Server listening on {host}:{port}")
    print("Waiting for clients... (Ctrl+C to stop)")
    print("-" * 50)

    try:
        while True:
            try:
                client_socket, client_address = server_socket.accept()
            except socket.timeout:
                continue
            client_socket.settimeout(None)
            threading.Thread(target=handle_client,
                             args=(client_socket, client_address),
                             daemon=True).start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        for c in online_snapshot().values():
            c.send("*** Server is shutting down ***")
            c.sock.close()
        server_socket.close()
        print("Server stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-client private chat server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    run_server(args.host, args.port)
