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
        self.type = None
        # Socket que gerencia a conexão ao outro usuários.
        self.connection = None
        self.server = None

    def handleConnection(self):
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
                    client = self.acceptConnection()
                    sockets_to_watch.append(client)
                else:
                    self.write()

            # Remove usuários caso uma exceção ocorra no socket.
            for notified_socket in exception_sockets:
                sockets_to_watch.remove(notified_socket)

    def acceptConnection(self):
        client, address = self.server.accept()
        self.connection = client
        print(f"{str(address)} se conectou com nick {nick}")
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

            if decoded_message == "NICK":
                # Envia o nick do usuário ao servidor.
                self.connection.send(self.nick.encode("utf-8"))
            else:
                print(decoded_message, end="")
        except:
            print("Erro! Fechando a conexão...")
            self.stop()

    def run(self, type, address, port):
        """
        Executa o cliente até ctrl+c ser pressionado.
        """
        try:
            self.start(type, address, port)
            self.handleConnection()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def start(self, type, address, port):
        """
        Conecta-se ao servidor no endereço e porta especificados.
        """
        self.type = type
        if self.type == ConnectionTypes.CLIENT:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.connect((address, port))
        elif self.type == ConnectionTypes.SERVER:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.bind((address, port))
            self.server.listen()

    def stop(self):
        """
        Finaliza a conexão com o servidor.
        """
        self.type = None
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


address = input("Endereço: ")
port = int(input("Porta: "))
type = input("Iniciar servidor(S) ou cliente(C)?: ")

if port < 1000 or port > 65535:
    print("Porta deve estar entre 1000 e 65535 (inclusivo)")
    sys.exit(1)


nick = input("Nome de usuário: ")
client = Client(nick)

if type.lower() == "c" or type.lower() == "cliente":
    type = ConnectionTypes.CLIENT
elif type.lower() == "s" or type.lower() == "servidor":
    type = ConnectionTypes.SERVER

client.run(type, address, port)
