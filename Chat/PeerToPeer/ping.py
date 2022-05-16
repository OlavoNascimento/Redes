#!/usr/bin/python3

import logging
import socket
from datetime import datetime
import select
import sys
from enum import Enum


class ConnectionTypes(Enum):
    CLIENT = 1
    SERVER = 2


TIMESTAMP_SIZE = 26


class Client:
    """
    Classe que lida com a conexão com um servidor e gerencia o envio e recebimento de mensagens.
    """

    def __init__(self):
        self.connection_type = None
        # Socket que gerencia a conexão ao outro usuário.
        self.connection = None

    def handle_connection(self):
        """
        Gerencia o envio de mensagens do usuário ao servidor e o recebimento de mensagens do
        servidor.
        """
        sockets_to_watch = [self.connection]

        while self.connection is not None:
            read_sockets, _, exception_sockets = select.select(
                sockets_to_watch,
                [],
                [],
            )
            for sock in read_sockets:
                if self.connection_type == ConnectionTypes.SERVER:
                    self.send_ping()
                    self.stop()
                elif self.connection_type == ConnectionTypes.CLIENT:
                    timesend = datetime.now()
                    logging.debug(
                        "Tempo de envio: %s",
                        timesend,
                    )
                    timereceive = self.receive_ping()
                    latency = timereceive - timesend
                    logging.debug(
                        "Delta de tempo: %s",
                        latency,
                    )
                    self.stop()

            # Remove usuários caso uma exceção ocorra no socket.
            for sock in exception_sockets:
                sockets_to_watch.remove(sock)

    def send_ping(self):
        client, _ = self.connection.accept()
        self.connection = client
        timestamp = str(datetime.now()).encode("ascii")
        self.connection.sendall(timestamp)
        return client

    def receive_ping(self):
        timestamp = None
        try:
            message = self.connection.recv(TIMESTAMP_SIZE)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if message == b"":
                self.stop()
                return
            timestamp = datetime.fromisoformat(message.decode("ascii"))
            logging.debug(
                "Timestamp recebido: %s",
                timestamp,
            )
        except (InterruptedError, UnicodeError):
            print("Erro! Fechando a conexão...", file=sys.stderr)
            self.stop()
        return timestamp

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
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.connection_type == ConnectionTypes.CLIENT:
            self.connection.connect((address, port))
        elif self.connection_type == ConnectionTypes.SERVER:
            self.connection.bind((address, port))
            self.connection.listen()

    def stop(self):
        """
        Finaliza a conexão com o servidor.
        """
        self.connection_type = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __del__(self):
        self.stop()


FORMAT = "%(levelname)s - [%(filename)s:%(lineno)s - %(funcName)s()] - %(asctime)s - %(message)s"
# Habilita mensagens de debug
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

app_address = input("Endereço: ")
app_port = int(input("Porta: "))
app_type = input("Iniciar servidor(S) ou cliente(C)?: ")

if app_port < 1000 or app_port > 65535:
    print("Porta deve estar entre 1000 e 65535 (inclusivo)")
    sys.exit(1)


app_client = Client()

if app_type.lower() == "c" or app_type.lower() == "cliente":
    app_type = ConnectionTypes.CLIENT
elif app_type.lower() == "s" or app_type.lower() == "servidor":
    app_type = ConnectionTypes.SERVER

app_client.run(app_type, app_address, app_port)
