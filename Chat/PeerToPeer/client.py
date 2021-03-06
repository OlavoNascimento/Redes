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
                # Um novo nó deseja executar um comando.
                if sock == self.server:
                    logging.debug("Novo evento no servidor/nós conectados/conexão")
                    node_sock, _ = self.server.accept()
                    action = self.on_command(node_sock)
                    # Novo nó dependente adicionado, é preciso observar eventos no socket.
                    if action == NodeCommands.LINK.value:
                        sockets_to_watch.append(node_sock)
                elif sock == self.connection or sock in self.connected_users:
                    logging.debug("Novo evento nos nós conectados")
                    action = self.on_command(sock)
                    # Nó se desconectou, os eventos não devem ser observados.
                    if action == NodeCommands.UNLINK.value:
                        sockets_to_watch.remove(sock)
                        # Caso o nó pai se desconectou é preciso atualizar o socket que está sendo
                        # observado.
                        if self.connection not in sockets_to_watch:
                            sockets_to_watch.append(self.connection)
                # Existe um valor a ser lido no stdin.
                elif sock == sys.stdin:
                    logging.debug("Novo evento no stdin")
                    self.send_message(self.connected_users + [self.connection])

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                logging.error("Erro no socket %s", notified_socket)
                sockets_to_watch.remove(notified_socket)
            sleep(1)

    def repeat_message(self, sender: socket.socket, message: str):
        """
        Repassa uma mensagem recebida para os nós conectados, exceto para o nó que enviou a
        mensagem.
        Também envia a mensagem para o nó pai.
        """
        super().repeat_message(sender, message)
        if self.connection != sender:
            self.connection.sendall(NodeCommands.MESSAGE.value)
            self.send_with_size(self.connection, message)

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

    def get_latency(self, address: Address) -> int:
        """
        Executa um teste de latência de conexão com outro nó.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            while True:
                try:
                    sock.connect(address)
                    break
                except ConnectionRefusedError:
                    return None
                    print("Falha ao se conectar ao outro usuário!")
                    sleep(1)
            start_time = datetime.now()
            logging.debug("Consultando latência desse nó até %s", address)
            # Indica que quer executar um teste de latência.
            sock.sendall(NodeCommands.PING.value)

            self.recvall(sock, 10)
            end_time = datetime.now()

            latency = end_time - start_time
            return latency

    def connect_to_lowest_latency(self):
        """
        Pede a lista de usuários ativos na rede para o gateway, testa a latência para cada nó e
        seleciona o nó com menor latência como a conexão principal desse nó.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as gateway:
            gateway.connect(self.gateway_addr)
            # Avisa o gateway que esse nó quer se conectar.
            gateway.sendall(GatewayCommands.ADD.value)
            # Envia o endereço desse nó.
            address = f"{self.address.host}:{self.address.port}".encode("ascii")
            self.send_with_size(gateway, address)

            # Recebe os usuários já conectados no gateway.
            serialized_users, message_size = self.recv_with_size(gateway)

        min_user = self.gateway_addr
        min_latency = self.get_latency(min_user)
        logging.debug(
            "Latência para o gateway %s é: %s",
            min_user,
            min_latency,
        )

        start_position = 0
        # Itera os usuários conectados e seleciona o com menor latência.
        while start_position < message_size:
            address, end_position = self.message_to_address(
                serialized_users, start_position, message_size
            )
            if address is None:
                logging.error("Falha ao decodificar endereço do outro usuário!")
                break
            start_position = end_position
            if address == self.address:
                continue

            latency = self.get_latency(address)
            if latency is None:
                break
            logging.debug(
                "Latência para o usuário %s é: %s",
                address,
                latency,
            )

            if latency < min_latency:
                min_user = address
                min_latency = latency

        logging.debug(
            "Usuário %s foi escolhido para conexão, latência: %s",
            min_user,
            min_latency,
        )

        if self.connection is not None:
            self.connection.close()
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect(min_user)
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
