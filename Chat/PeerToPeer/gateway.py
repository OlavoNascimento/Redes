#!/usr/bin/python3

import logging
import select
import sys
from socket import socket
from time import sleep
from typing import Dict, List

from node import Address, Node


class Gateway(Node):
    def __init__(self, address: Address, name: str) -> None:
        super().__init__(address, name)
        self.current_users: Dict[str, socket] = {}

    def run(self):
        print("Agindo como host de entrada!")
        super().run()

    def send_current_users(self, new_user: socket):
        logging.debug("Enviando lista de usuários: %s", self.current_users)
        message: List[bytes] = b""
        for address in self.current_users:
            (host, port) = address.split(":")
            # Nome do host + porta do outro usuário.
            address = host.encode("ascii") + int(port).to_bytes(8, "big", signed=False)
            # Tamanho do endereço
            message += len(address).to_bytes(8, "big", signed=False)
            message += address

        logging.debug(
            "Mensagem final: %s",
            message,
        )
        message_size = len(message).to_bytes(8, "big", signed=False)
        new_user.sendall(message_size)
        new_user.sendall(message)

    def handle_connection(self):
        sockets_to_watch = [sys.stdin, self.server]

        while True:
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for sock in read_sockets:
                # Um novo nó quer se conectar.
                # Adiciona a lista de nós conectados.
                if sock == self.server:
                    node_sock = self.on_add()
                    if node_sock is not None:
                        sockets_to_watch.append(node_sock)
                elif sock in self.current_users.values():
                    self.on_command(sock)
                else:
                    self.write()

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)
            sleep(1)

    def on_add(self) -> socket | None:
        node_sock, _ = self.server.accept()
        action = self.recvall(node_sock, 3).decode("ascii")
        if action != "ADD":
            return None

        self.send_current_users(node_sock)
        address_size = self.recvall(node_sock, 8)
        address_size = int.from_bytes(address_size, "big", signed=False)

        address = self.recvall(node_sock, address_size).decode("ascii")
        logging.debug("Adicionando endereço %s a lista de usuários!", address)

        self.current_users[address] = node_sock
        return node_sock

    def on_command(self, node_sock: socket) -> None:
        action = self.recvall(node_sock, 3).decode("ascii")
        if action == "PIN":
            self.on_ping(node_sock)
        if action == "LIN":
            self.connected_users.append(node_sock)
