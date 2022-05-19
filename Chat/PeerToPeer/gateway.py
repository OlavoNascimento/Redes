#!/usr/bin/python3

import logging
import select
import sys
import socket
from time import sleep
from typing import List, Tuple

from node import Address, Node


class Gateway(Node):
    """
    Nó que serve como entrada para uma rede. Além de atuar como um nó genérico, ele também mantêm
    uma lista de usuários ativos na rede.
    """

    def __init__(self, address: Address, name: str) -> None:
        super().__init__(address, name)
        self.network_users: List[str] = []

    def run(self):
        print(
            "Esse nó é o host de entrada!"
            f" Conecte-se através do endereço: {self.address.host}:{self.address.port}"
        )
        super().run()

    def handle_connection(self):
        sockets_to_watch = [sys.stdin, self.server]

        while True:
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for sock in read_sockets:
                # Um novo nó deseja executar um comando.
                if sock == self.server:
                    logging.debug("Novo evento no servidor")
                    node_sock, _ = self.on_command()
                    if node_sock is not None:
                        sockets_to_watch.append(node_sock)
                # Um nó existente transmitiu uma mensagem.
                elif sock in self.connected_users:
                    logging.debug("Nova mensagem de nós conectados")
                    self.on_message_received(sock)
                # Existe um valor a ser lido no stdin.
                elif sock == sys.stdin:
                    logging.debug("Novo evento no stdin")
                    self.write(self.connected_users)

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)
            sleep(1)

    def send_current_users(self, new_user: socket.socket):
        """
        Envia a lista de usuários conectados para um nóvo nó.
        """
        logging.debug("Enviando lista de usuários: %s", self.network_users)
        message: List[bytes] = b""
        for address in self.network_users:
            (host, port) = address.split(":")
            # Nome do host + porta do outro usuário.
            address = host.encode("ascii") + int(port).to_bytes(8, "big", signed=False)
            # Tamanho do endereço
            message += len(address).to_bytes(8, "big", signed=False)
            message += address

        logging.debug(
            "Lista de usuários serializada: %s",
            message,
        )
        message_size = len(message).to_bytes(8, "big", signed=False)
        new_user.sendall(message_size)
        new_user.sendall(message)

    def on_command(self) -> Tuple[socket.socket, str]:
        """
        Adiciona o comando add ao método on_command, o qual é responsável por adicionar novos nó a
        rede.
        """
        node_sock, action = super().on_command()
        if action == "ADD":
            self.on_add(node_sock)
        # TODO Implementar ação REM para lidar com a saída de um usuário.
        return node_sock, action

    def on_add(self, node_sock: socket.socket) -> None:
        """
        Executado quando um usuário quer fazer parte da rede. Para isso o novo usuário é adicionado
        a lista de nós da redes.
        """
        self.send_current_users(node_sock)
        address_size = self.recvall(node_sock, 8)
        address_size = int.from_bytes(address_size, "big", signed=False)

        address = self.recvall(node_sock, address_size).decode("ascii")
        logging.debug("Adicionando endereço %s a lista de usuários!", address)

        self.network_users.append(address)
