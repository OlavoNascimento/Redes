#!/usr/bin/python3

import abc
from enum import Enum
import socket
import logging
from datetime import datetime
import sys
from collections import namedtuple
from typing import List, Tuple


Address = namedtuple("address", ["host", "port"])


class NodeCommands(Enum):
    """
    Commandos que podem ser executados por um nó genérico.
    """

    # Realiza a latência desse nó com outro nó na rede.
    PING = "PIN".encode("ascii")
    # Indica que outro nó quer utilizar esse nó para receber dados.
    LINK = "LIN".encode("ascii")
    # O nó pai notificou que irá sair da rede.
    UNLINK = "UNL".encode("ascii")
    # Um nó enviou uma mensagem.
    MESSAGE = "MSG".encode("ascii")


class Node(metaclass=abc.ABCMeta):
    """
    Nó genérico que faz parte de uma rede. Possui nome, endereço, além de uma lista de nós que
    dependem dele para receber mensagens de outros usuários e um socket para se comunicar com novos
    usuários.
    """

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
        """
        Executa o programa até ctrl+c ser pressionado.
        """
        try:
            self.start()
            self.handle_connection()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    @abc.abstractmethod
    def handle_connection(self):
        """
        Reage a eventos em diferentes sockets e chama os métodos apropriados.
        """
        return NotImplementedError("Função handle_connection deve ser implementada!")

    def start(self):
        """
        Prepara o socket de escuta do nó.
        """
        self.server.bind(self.address)
        self.server.listen()

    def stop(self):
        """
        Fecha o socket de escuta do nó.
        """
        self.connected_users = []
        if self.server is not None:
            self.server.close()
            self.server = None

    def send_message(self, users: List[socket.socket]):
        """
        Envia uma mensagem de texto para vários usuários.
        """
        message = sys.stdin.readline()
        if len(message) <= 0:
            return
        now = datetime.now()
        message = f"[{now.hour}:{now.minute}] {self.name}: {message}"
        print(message, end="")

        message = message.encode("utf-8")
        for user in users:
            user.sendall(NodeCommands.MESSAGE.value)
            self.send_with_size(user, message)

    def on_message_received(self, sock: socket.socket) -> None:
        """
        Método executado toda vez que uma mensagem é recebida. Decodifica a mensagem, apresenta na
        saída padrão e repassa a mensagem para os usuários conectados a esse nó.
        """
        try:
            message, _ = self.recv_with_size(sock)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if message == b"":
                return
            decoded_message = message.decode("utf-8")
            print(decoded_message, end="")
            self.repeat_message(sock, message)
        except (InterruptedError, UnicodeError):
            print("ERRO: Fechando a conexão!", file=sys.stderr)
            self.stop()

    def repeat_message(self, sender: socket.socket, message: str):
        """
        Repassa uma mensagem recebida para os nós conectados, exceto para o nó que enviou a
        mensagem.
        """
        logging.debug("Retransmitindo mensagem")
        for user in self.connected_users:
            if user != sender:
                user.sendall(NodeCommands.MESSAGE.value)
                self.send_with_size(user, message)

    def on_command(self, node_sock: socket.socket) -> str:
        """
        Recebe e executa um comando especificado por um usuário.
        """
        action = self.recvall(node_sock, 3)
        logging.debug("Received action %s", action)
        if action == NodeCommands.LINK.value:
            self.on_link(node_sock)
        elif action == NodeCommands.PING.value:
            self.on_ping(node_sock)
            node_sock.close()
            node_sock = None
        elif action == NodeCommands.MESSAGE.value:
            self.on_message_received(node_sock)
        elif action == NodeCommands.UNLINK.value:
            self.on_unlink(node_sock)
        return action

    def on_ping(self, node_sock: socket.socket) -> None:
        """
        Método executado quando um usuário pede para esse nó realizar um teste de latência.
        """
        logging.debug(
            "Recebido pedido de latência",
        )
        byte = b"1" * 10
        self.send_with_size(node_sock, byte)

    def on_link(self, node_sock: socket.socket) -> None:
        """
        Indica que um usuário quer se conectar a esse nó. Para isso adiciona o novo nó a lista de
        nós conectados.
        """
        logging.debug("Adicionando nó como dependente")
        self.connected_users.append(node_sock)

    def on_unlink(self, node_sock: socket.socket) -> None:
        """
        Executado quando um nó dependente se desconecta, remove o nó que saiu da lista de usuário
        conectados.
        """
        logging.debug("Removendo nó como dependente")
        if node_sock in self.connected_users:
            self.connected_users.remove(node_sock)

    @staticmethod
    def send_with_size(sock: socket.socket, text: bytes) -> None:
        """
        Envia o tamanho de um texto e o texto para um socket.
        """
        text_size = len(text).to_bytes(8, "big", signed=False)
        sock.sendall(text_size)
        sock.sendall(text)

    def recv_with_size(self, sock: socket.socket) -> Tuple[bytes, int]:
        """
        Recebe uma mensagem com um tamanho variável em um socket.
        """
        size = self.recvall(sock, 8)
        size = int.from_bytes(size, "big", signed=False)
        value = self.recvall(sock, size)
        return value, size

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

    def notify_stop(self):
        """
        Indica para os usuários que dependem desse nó que eles devem buscar uma nova conexão para a
        rede.
        """
        if not self.connected_users:
            return
        logging.debug(
            "Avisando nós dependentes da saída desse nó!",
        )
        for user in self.connected_users:
            user.sendall(NodeCommands.UNLINK.value)
