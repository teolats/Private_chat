#!/usr/bin/env python3
"""
Automated test: starts the server, connects 3 raw-socket clients
(alice, bob, carol) and checks that messages reach ONLY the chosen recipients.

Run:  python3 test_private_chat.py
"""

import socket
import subprocess
import sys
import time
import os

PORT = 5099
HERE = os.path.dirname(os.path.abspath(__file__))


class TestClient:
    def __init__(self, name):
        self.sock = socket.create_connection(("127.0.0.1", PORT))
        self.sock.settimeout(0.3)
        self.buf = ""
        self.read()                          # "Enter your name:"
        self.say(name)
        self.read()                          # welcome text

    def say(self, line):
        self.sock.sendall((line + "\n").encode("utf-8"))
        time.sleep(0.15)

    def read(self):
        """Return everything received since the last read."""
        out = ""
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                out += data.decode("utf-8")
            except socket.timeout:
                break
        return out


def check(desc, cond):
    print(("  PASS  " if cond else "  FAIL  ") + desc)
    return cond


def main():
    server = subprocess.Popen([sys.executable, os.path.join(HERE, "private_chat_server.py"),
                               "--port", str(PORT)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    time.sleep(0.8)
    ok = True
    try:
        a, b, c = TestClient("alice"), TestClient("bob"), TestClient("carol")
        for x in (a, b, c):
            x.read()                         # drain join notifications

        print("1. Private message @bob")
        a.say("@bob hi bob")
        ra, rb, rc = a.read(), b.read(), c.read()
        ok &= check("bob receives it", "[alice -> you] hi bob" in rb)
        ok &= check("carol does NOT receive it", "hi bob" not in rc)
        ok &= check("alice gets delivery report", "[sent to bob]" in ra)

        print("2. Multiple recipients @bob,carol (BONUS)")
        a.say("@bob,carol hello both")
        ra, rb, rc = a.read(), b.read(), c.read()
        ok &= check("bob receives it (sees carol too)", "[alice -> you, carol] hello both" in rb)
        ok &= check("carol receives it (sees bob too)", "[alice -> you, bob] hello both" in rc)
        ok &= check("alice report lists both", "[sent to bob, carol]" in ra)

        print("3. Alternative syntax @bob @carol")
        c.say("@alice @bob yo")
        ra, rb = a.read(), b.read()
        ok &= check("alice and bob receive it", "yo" in ra and "yo" in rb)

        print("4. Default recipients with /to")
        b.say("/to carol")
        b.read()
        b.say("plain text to carol")
        ra, rc = a.read(), c.read()
        ok &= check("carol receives plain text", "[bob -> you] plain text to carol" in rc)
        ok &= check("alice does NOT", "plain text" not in ra)

        print("5. Offline / unknown recipient")
        a.say("@bob,dave partial")
        ra, rb = a.read(), b.read()
        ok &= check("sender warned about dave", "Not online: dave" in ra)
        ok &= check("bob still receives it", "partial" in rb)

        print("6. /all broadcast and /list")
        c.say("/all everyone")
        ra, rb = a.read(), b.read()
        ok &= check("everyone receives broadcast", "[carol -> all] everyone" in ra and "everyone" in rb)
        a.say("/list")
        ok &= check("/list shows 3 users", "Online (3)" in a.read())

        print("7. Duplicate name is rejected")
        d = socket.create_connection(("127.0.0.1", PORT)); d.settimeout(0.3)
        time.sleep(0.1); d.recv(4096)
        d.sendall(b"alice\n"); time.sleep(0.15)
        ok &= check("server asks for another name", "already taken" in d.recv(4096).decode())
        d.close()

        print("8. Disconnect notification")
        c.say("quit")
        time.sleep(0.2)
        ok &= check("others are told carol left", "carol has left" in a.read())
        a.say("@carol are you there?")
        ok &= check("message to departed user reported", "Not online: carol" in a.read())
    finally:
        server.terminate()
        server.wait()

    print("\nALL TESTS PASSED" if ok else "\nSOME TESTS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
