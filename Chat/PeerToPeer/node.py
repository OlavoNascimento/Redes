#!/usr/bin/python3

import socket
import datetime
import sys
from collections import namedtuple
from typing import List


Address = namedtuple("address", ["host", "port"])


class Node:
    def __init__(self, address: Address, name: str):
        self.name = name
        # Endereço onde o nó vai ouvir os nós dependentes.
        self.address = address
        # Socket que gerencia a conexão com os nós dependentes.
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Usuários conectados a este nó.
        self.connected_users: List[socket.socket] = []

    def __del__(self):
        self.stop()

    def run(self):
        try:
            self.start()
            self.handle_connection()
        except KeyboardInterrupt:
            pass
        except OSError as err:
            print("ERRO: Não foi possível se conectar ao host de entrada!", file=sys.stderr)
            print(err, file=sys.stderr)
            sys.exit(1)
        finally:
            self.stop()

    def handle_connection(self):
        # TODO Abstract
        return NotImplementedError()

    def start(self):
        self.server.bind(self.address)
        self.server.listen()

    def stop(self):
        if self.server is not None:
            self.server.close()
            self.server = None

    @staticmethod
    def recvall(sock, size):
        """
        Espera receber um número de bytes através de um socket.
        """
        message = b""
        while len(message) < size:
            buffer = sock.recv(size - len(message))
            message += buffer
        return message

    def write(self):
        message = sys.stdin.readline()
        if len(message) > 0:
            now = datetime.datetime.now()
            for node in self.connected_users:
                message = f"[{now.hour}:{now.minute}] {self.name}: {message}"
                node.send(message.encode("utf-8"))
