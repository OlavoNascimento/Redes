#!/usr/bin/python3

from audioop import add
from email import message
import logging
import select
import socket
import sys
from time import sleep

from node import Address, Node


class Client(Node):
    def __init__(self, address: Address, name: str, gateway: Address) -> None:
        super().__init__(address, name)
        self.gateway_addr = gateway
        # Socket que gerencia a conexão ao outro nó.
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

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

    def start(self):
        super().start()
        logging.debug(
            "Conectando ao gateway %s",
            self.gateway_addr,
        )
        self.connection.connect(self.gateway_addr)

        message_size = self.recvall(self.connection, 8)
        message_size = int.from_bytes(message_size, "big", signed=False)
        logging.debug(
            "O tamanho da mensagem de endereços é: %d",
            message_size,
        )

        connected_users = self.recvall(self.connection, message_size)
        logging.debug(
            "A mensagem é: %s",
            connected_users,
        )
        start_position = 0
        while start_position < message_size:
            address_size = connected_users[start_position : start_position + 8]
            address_size = int.from_bytes(address_size, "big", signed=False)
            logging.debug(
                "O tamanho do endereço é: %d",
                address_size,
            )
            if address_size > message_size:
                logging.error(
                    "Tamanho do endereço (%d) é maior que o tamanho da mensagem (%d)",
                    address_size,
                    message_size,
                )
                logging.error("Mensagem: %s", connected_users)
                break

            start = start_position + 8
            end = start + address_size
            address = connected_users[start:end]
            logging.debug("Decodificando o endereço: %s", address)

            host = address[0:-8].decode("ascii")
            port = int.from_bytes(address[-7:], "big", signed=False)
            logging.debug(
                "Host e porta do usuário: (%s, %d)",
                host,
                port,
            )
            start_position = end

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
                    node_sock, node_addr = self.server.accept()
                    # sockets_to_watch.append(client)
                else:
                    self.write()

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)
            sleep(1)
