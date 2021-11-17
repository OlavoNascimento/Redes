#!/usr/bin/python3

import socket
import datetime
import select
import sys
from enum import Enum


class ConnectionTypes(Enum):
    CLIENT = 1
    SERVER = 2


class Client:
    """
    Classe que lida com a conexão com um servidor e gerencia o envio e recebimento de mensagens.
    """

    def __init__(self, nickname):
        self.nick = nickname
        # Endereço onde o servidor deve esperar por conexões.
        self.connection_type = None
        self.server = None
        # Socket que gerencia a conexão ao outro usuário.
        self.connection = None

    def handle_connection(self):
        """
        Gerencia o envio de mensagens do usuário ao servidor e o recebimento de mensagens do
        servidor.
        """
        sockets_to_watch = [sys.stdin]
        if self.connection is not None:
            sockets_to_watch.append(self.connection)
        if self.server is not None:
            sockets_to_watch.append(self.server)

        while self.connection is not None or self.server is not None:
            # Verifica se o stdin ou o servidor tem algum dado a ser lido.
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for socks in read_sockets:
                if socks == self.connection:
                    self.receive()
                elif socks == self.server:
                    client = self.accept_connection()
                    sockets_to_watch.append(client)
                else:
                    self.write()

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)

    def accept_connection(self):
        """
        Aceita a conexão de um outro usuário.
        """
        client, _ = self.server.accept()
        self.connection = client
        return client

    def receive(self):
        """
        Recebe uma mensagem do servidor.
        Caso o servidor feche a conexão ou um erro aconteça o cliente é finalizado corretamente.
        """
        try:
            message = self.connection.recv(1024)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if message == b"":
                self.stop()
                return
            decoded_message = message.decode("utf-8")
            print(decoded_message, end="")
        except (InterruptedError, UnicodeError):
            print("Erro! Fechando a conexão...")
            self.stop()

    def run(self, connection_type, address, port):
        """
        Executa o cliente até ctrl+c ser pressionado.
        """
        try:
            self.start(connection_type, address, port)
            self.handle_connection()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def start(self, connection_type, address, port):
        """
        Conecta-se ao servidor no endereço e porta especificados.
        """
        self.connection_type = connection_type
        if self.connection_type == ConnectionTypes.CLIENT:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect((address, port))
            message = f"{str(address)} se conectou com nick {self.nick}"
            print(message)
            self.connection.send(message.encode("utf-8"))
        elif self.connection_type == ConnectionTypes.SERVER:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.bind((address, port))
            self.server.listen()

    def stop(self):
        """
        Finaliza a conexão com o servidor.
        """
        self.connection_type = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.server is not None:
            self.server.close()
            self.server = None

    def write(self):
        """
        Lê uma mensagem do stdin e envia para o servidor.
        """
        message = sys.stdin.readline()
        if len(message) > 0:
            now = datetime.datetime.now()
            self.connection.send(
                f"[{now.hour}:{now.minute}] {self.nick}: {message}".encode("utf-8")
            )


app_address = input("Endereço: ")
app_port = int(input("Porta: "))
app_type = input("Iniciar servidor(S) ou cliente(C)?: ")

if app_port < 1000 or app_port > 65535:
    print("Porta deve estar entre 1000 e 65535 (inclusivo)")
    sys.exit(1)


user_nick = input("Nome de usuário: ")
app_client = Client(user_nick)

if app_type.lower() == "c" or app_type.lower() == "cliente":
    app_type = ConnectionTypes.CLIENT
elif app_type.lower() == "s" or app_type.lower() == "servidor":
    app_type = ConnectionTypes.SERVER

app_client.run(app_type, app_address, app_port)
