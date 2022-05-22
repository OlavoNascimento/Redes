#!/usr/bin/python3

from enum import Enum
import logging
import select
import sys
import socket
from time import sleep
from typing import List

from node import Address, Node, NodeCommands


class GatewayCommands(Enum):
    """
    Commandos que podem ser executados por um gateway.
    """

    # Indica que um nó quer ser adicionado a rede.
    ADD = "ADD".encode("ascii")
    # Remove um nó da rede.
    REMOVE = "REM".encode("ascii")


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

    def stop(self):
        super().stop()
        self.network_users = []

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
                    node_sock, _ = self.server.accept()
                    action = self.on_command(node_sock)
                    if action in (GatewayCommands.ADD.value, NodeCommands.LINK.value):
                        sockets_to_watch.append(node_sock)
                # Um nó existente transmitiu uma mensagem.
                elif sock in self.connected_users:
                    logging.debug("Nova mensagem de nós conectados")
                    self.on_command(sock)
                # Existe um valor a ser lido no stdin.
                elif sock == sys.stdin:
                    logging.debug("Novo evento no stdin")
                    self.send_message(self.connected_users)

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)
            sleep(1)

    def send_current_users(self, new_user: socket.socket):
        """
        Envia a lista de usuários conectados para um novo nó.
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
        self.send_with_size(new_user, message)

    def on_command(self, node_sock: socket.socket) -> str:
        """
        Adiciona o comando add e remove ao método on_command.
        """
        action = super().on_command(node_sock)
        if action == GatewayCommands.ADD.value:
            self.on_add(node_sock)
        elif action == GatewayCommands.REMOVE.value:
            self.on_remove(node_sock)
        return action

    def on_add(self, node_sock: socket.socket) -> None:
        """
        Executado quando um usuário quer fazer parte da rede. Para isso o novo usuário é adicionado
        a lista de nós da rede.
        """
        address, _ = self.recv_with_size(node_sock)
        address = address.decode("ascii")
        self.send_current_users(node_sock)
        if address not in self.network_users:
            logging.debug("Adicionando endereço %s a lista de usuários!", address)
            self.network_users.append(address)

    def on_remove(self, node_sock: socket.socket) -> None:
        """
        Executado quando um usuário desconectar. O usuário que desconectou é retirado da lista de
        endereços disponíveis no gateway
        """
        address, _ = self.recv_with_size(node_sock)
        address = address.decode("ascii")
        if address in self.network_users:
            self.network_users.remove(address)
            logging.debug("Removendo endereço %s da lista de usuários!", address)
            logging.debug("Usuários ativos: %s", self.network_users)
