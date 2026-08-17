#!/usr/bin/env python3
import argparse
import os
import select
import socket
import termios
import time


BAUDS = {
    9600: termios.B9600,
    115200: termios.B115200,
    460800: getattr(termios, "B460800", termios.B115200),
}


def hexdump(data):
    return " ".join(f"{byte:02x}" for byte in data)


def printable(data):
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)


def configure_serial(fd, baud):
    attrs = termios.tcgetattr(fd)
    attrs[0] = termios.IGNPAR
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
    attrs[3] = 0
    attrs[4] = BAUDS[baud]
    attrs[5] = BAUDS[baud]
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def log_packet(log, direction, data):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    millis = int((time.time() % 1) * 1000)
    log.write(f"{now}.{millis:03d} {direction} len={len(data)}\n")
    log.write(f"  hex: {hexdump(data)}\n")
    log.write(f"  txt: {printable(data)}\n")
    log.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--baud", type=int, default=9600, choices=sorted(BAUDS))
    parser.add_argument("--log", required=True)
    args = parser.parse_args()

    try:
        os.unlink(args.socket)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(args.socket)
    server.listen(1)
    print(f"waiting for VM on {args.socket}", flush=True)
    vm_sock, _ = server.accept()
    print("vm connected", flush=True)
    vm_sock.setblocking(False)

    serial_fd = os.open(args.serial, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    configure_serial(serial_fd, args.baud)
    print(f"serial opened {args.serial} at {args.baud}", flush=True)

    with open(args.log, "a", encoding="utf-8") as log:
        log.write(f"capture start socket={args.socket} serial={args.serial} baud={args.baud}\n")
        log.flush()
        while True:
            readable, _, _ = select.select([vm_sock, serial_fd], [], [])
            if vm_sock in readable:
                data = vm_sock.recv(4096)
                if not data:
                    break
                log_packet(log, "WIN->PM3", data)
                os.write(serial_fd, data)
            if serial_fd in readable:
                try:
                    data = os.read(serial_fd, 4096)
                except BlockingIOError:
                    data = b""
                if data:
                    log_packet(log, "PM3->WIN", data)
                    vm_sock.sendall(data)


if __name__ == "__main__":
    main()
