#!/usr/bin/python3

import logging
import select
import socket
import sys
from datetime import datetime
from time import sleep
from typing import List

from node import Address, Node


class Client(Node):
    def __init__(self, address: Address, name: str, gateway: Address) -> None:
        super().__init__(address, name)
        self.gateway_addr = gateway
        # Socket que gerencia a conexão ao outro nó.
        self.connection = None

    def receive(self):
        try:
            message = self.recvall(self.connection, 1024)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if message == b"":
                print("O servidor fechou a conexão!", file=sys.stderr)
                # TODO
                # Encontrar um novo nó para se conectar
                return
            decoded_message = message.decode("utf-8")
            print(decoded_message, end="")
        except (InterruptedError, UnicodeError):
            print("ERRO: Fechando a conexão!", file=sys.stderr)
            self.stop()

    def message_to_address(
        self, serialized_users: List[bytes], start_position: int, message_size: int
    ):
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
        logging.debug(
            "Host e porta do usuário: (%s, %d)",
            host,
            port,
        )
        return Address(host, port), end

    def get_latency(self, sock: socket.socket) -> int:
        sock.sendall("PIN".encode("ascii"))
        start_time = datetime.now()
        end_time = self.recvall(sock, self.TIMESTAMP_SIZE)
        end_time = datetime.fromisoformat(end_time.decode("ascii"))
        latency = end_time - start_time
        return latency

    def connect_to_best_user(self):
        gateway = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        gateway.connect(self.gateway_addr)

        # Avisa o gateway que esse nó quer se conectar.
        gateway.sendall("ADD".encode("ascii"))
        # Envia o endereço desse nó.
        address = f"{self.address.host}:{self.address.port}".encode("ascii")
        address_size = len(address).to_bytes(8, "big", signed=False)
        gateway.sendall(address_size)
        gateway.sendall(address)

        # Recebe os usuários já conectados no gateway.
        message_size = self.recvall(gateway, 8)
        message_size = int.from_bytes(message_size, "big", signed=False)
        logging.debug(
            "O tamanho da mensagem de endereços é: %d",
            message_size,
        )
        serialized_users = self.recvall(gateway, message_size)

        start_position = 0
        min_user = gateway
        min_latency = self.get_latency(min_user)
        logging.debug(
            "Latência para o gateway %s é: %s",
            min_user.getsockname(),
            min_latency,
        )

        # Itera os usuários conectados e seleciona o com menor latência.
        while start_position < message_size:
            address, end_position = self.message_to_address(
                serialized_users, start_position, message_size
            )
            if address is None:
                logging.error("Falha ao decodificar endereço do outro usuário!")
                break
            start_position = end_position

            user_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            user_sock.connect(address)
            latency = self.get_latency(user_sock)
            logging.debug(
                "Latência para o usuário %s é: %s",
                address,
                latency,
            )

            if latency < min_latency:
                min_user.close()
                min_user = user_sock
                min_latency = latency
            else:
                user_sock.close()

        if min_user != gateway:
            gateway.close()
        logging.debug(
            "Usuário %s foi escolhido para conexão, latência: %s",
            min_user.getsockname()[0],
            min_latency,
        )
        self.connection = min_user

    def start(self):
        super().start()
        self.connect_to_best_user()

    def stop(self):
        self.notify_stop()
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        super().stop()

    def notify_stop(self):
        # TODO
        # Implementar notificação de saída.
        pass

    def handle_connection(self):
        sockets_to_watch = [sys.stdin, self.connection, self.server]

        while True:
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for sock in read_sockets:
                # Nó de contato enviou uma mensagem.
                # Lê e redistribui.
                if sock == self.connection:
                    self.receive()
                # Um novo nó quer se conectar.
                # Adiciona a lista de nós conectados.
                elif sock == self.server:
                    new_user = self.on_command()
                    if new_user is not None:
                        sockets_to_watch.append(new_user)
                elif sock == sys.stdin:
                    self.write()

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)
            sleep(1)

    def on_command(self) -> socket.socket | None:
        node_sock, _ = self.server.accept()

        action = self.recvall(node_sock, 3).decode("ascii")
        if action == "LIN":
            logging.debug("Adicionando endereço aos nós dependentes!")
            return node_sock
        if action == "PIN":
            self.on_ping(node_sock)
            return None
        return None
