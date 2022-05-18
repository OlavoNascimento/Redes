#!/usr/bin/python3

import logging
import select
import sys
from socket import socket
from time import sleep
from typing import List

from node import Address, Node


class Gateway(Node):
    def __init__(self, address: Address, name: str) -> None:
        super().__init__(address, name)
        self.current_users: List[socket] = []

    def run(self):
        print("Agindo como host de entrada!")
        super().run()

    def send_current_users(self, new_user: socket):
        logging.debug(
            "Enviando lista de usuários: %s",
            list(map(lambda sock: sock.getsockname(), self.current_users)),
        )
        # Número de usuários conectados.
        # message_size = len(self.current_users).to_bytes(8, "big", signed=False)

        message: List[bytes] = b""
        for sock in self.current_users:
            (host, port) = sock.getsockname()
            # Nome do host + porta do outro usuário.
            address = host.encode("ascii") + port.to_bytes(8, "big", signed=False)
            # Tamanho do endereço
            addr_message = len(address).to_bytes(8, "big", signed=False) + address
            message += addr_message
            logging.debug(
                "Usuário (%s, %d) convertido para %s",
                host,
                port,
                addr_message,
            )

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
                    node_sock, _ = self.server.accept()
                    logging.debug(
                        "Novo endereço conectado a esse gateway: %s",
                        node_sock.getsockname(),
                    )
                    self.send_current_users(node_sock)
                    sockets_to_watch.append(node_sock)
                    self.current_users.append(node_sock)
                else:
                    self.write()

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)
            sleep(1)
