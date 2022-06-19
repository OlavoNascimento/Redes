#!/usr/bin/python3

import logging
import select
import socket
import sys
from datetime import datetime
from time import sleep
from typing import List
from gateway import GatewayCommands

from node import Address, Node, NodeCommands


class Client(Node):
    """
    Nó que utiliza um gateway para se conectar ao usuário com menor latência na rede.
    Para isso possui um socket adicional, o qual é responsável por gerenciar a comunicação com o nó
    pai.
    """

    def __init__(self, address: Address, name: str, gateway: Address) -> None:
        super().__init__(address, name)
        self.gateway_addr = gateway
        # Socket que gerencia a conexão ao outro nó.
        self.connection = None

    def start(self):
        super().start()
        self.connect_to_lowest_latency()
        print("Conectado ao gateway")

    def stop(self):
        self.notify_stop()
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        super().stop()

    def handle_connection(self):
        sockets_to_watch = [sys.stdin, self.connection, self.server]

        while True:
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for sock in read_sockets:
                # Existe um valor a ser lido no stdin.
                if sock == sys.stdin:
                    logging.debug("Novo evento no stdin")
                    self.send_message(self.connection)

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                logging.error("Erro no socket %s", notified_socket)
                sockets_to_watch.remove(notified_socket)
            sleep(1)


    @staticmethod
    def message_to_address(serialized_users: List[bytes], start_position: int, message_size: int):
        """
        Converte um endereço serializado para uma tupla nomeada Address.
        O endereço serializado possui o formato: $tamanho_do_endereço$host$port
        """
        address_size = serialized_users[start_position : start_position + 8]
        address_size = int.from_bytes(address_size, "big", signed=False)

        if address_size > message_size:
            logging.error(
                "Tamanho do endereço (%d) é maior que o tamanho da mensagem (%d)",
                address_size,
                message_size,
            )
            logging.error("Mensagem: %s", serialized_users)
            return None, None

        start = start_position + 8
        end = start + address_size
        address = serialized_users[start:end]

        host = address[0:-8].decode("ascii")
        port = int.from_bytes(address[-7:], "big", signed=False)
        return Address(host, port), end

    def connect_to_lowest_latency(self):
        if self.connection is not None:
            self.connection.close()
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect(self.gateway_addr)
        # Indica que esse nó quer se tornar dependente do nó com menor latência.
        self.connection.sendall(NodeCommands.LINK.value)

    def on_unlink(self, node_sock: socket.socket) -> None:
        """
        Executado quando um nó dependente se desconecta, remove o nó que saiu da lista de usuário
        conectados.
        Caso o nó pai tenha se desconectado da rede esse nó busca uma nova conexão com a rede.
        """
        super().on_unlink(node_sock)
        # Nó pai se desconectou, é preciso encontrar outro nó de conexão.
        if node_sock == self.connection:
            logging.debug("Procurando uma nova conexão com a rede")
            self.connect_to_lowest_latency()

    def notify_stop(self):
        """
        Indica para os usuários que dependem desse nó que eles devem buscar uma nova conexão para a
        rede.
        """
        if self.connection is None:
            return
        super().notify_stop()
        logging.debug(
            "Avisando nó pai da saída desse nó!",
        )
        self.connection.sendall(NodeCommands.UNLINK.value)

        logging.debug(
            "Avisando gateway da saída desse nó!",
        )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as gateway:
            # Avisa ao ao gateway que está havendo uma remoção
            gateway.connect(self.gateway_addr)
            gateway.sendall(GatewayCommands.REMOVE.value)

            address = f"{self.address.host}:{self.address.port}".encode("ascii")
            self.send_with_size(gateway, address)
