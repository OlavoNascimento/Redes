#!/usr/bin/python3

import socket
import datetime
from math import ceil
import os
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

    def __init__(self):
        # Endereço onde o servidor deve esperar por conexões.
        self.connection_type = None
        self.server = None
        # Socket que gerencia a conexão ao outro usuário.
        self.connection = None

    def handle_connection(self, filename):
        """
        Gerencia o envio de mensagens do usuário ao servidor e o recebimento de mensagens do
        servidor.
        """
        sockets_to_watch = []
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
                    self.receive(filename)
                elif socks == self.server and self.connection is None:
                    client = self.accept_connection()
                    sockets_to_watch.append(client)
                    self.send_file(filename)

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

    def receive(self, filename):
        """
        Recebe uma mensagem do servidor.
        Caso o servidor feche a conexão ou um erro aconteça o cliente é finalizado corretamente.
        """
        try:
            size = self.connection.recv(4)
            # Se a mensagem possui zero bytes o servidor fechou a conexão.
            # Veja: https://docs.python.org/3/howto/sockets.html#using-a-socket
            if size == b"":
                self.stop()
                return
            # Socket foi aberto, ainda não foi iniciado a transmissão do arquivo.
            if size == b"\x00\x00\x00\x00":
                return
            size = int.from_bytes(size, "big")

            print("Recebendo arquivo")
            buffer = b""
            last_received = 0
            while len(buffer) < size:
                data = self.connection.recv(size - len(buffer))

                received = round((len(buffer) / size) * 100, 2)
                if int(received) >= last_received + 5:
                    print(f"Recebido {received}%")
                    last_received = received

                if not data:
                    print("Arquivo incompleto recebido")
                    break
                buffer += data

            with open(filename, "wb") as output:
                output.write(buffer)
            print("Arquivo recebido")
        except InterruptedError:
            print("Erro! Fechando a conexão...")
            self.stop()

    def run(self, connection_type, address, port, file_path):
        """
        Executa o cliente até ctrl+c ser pressionado.
        """
        try:
            self.start(connection_type, address, port)
            self.handle_connection(file_path)
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
        elif self.connection_type == ConnectionTypes.SERVER:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.bind((address, port))
            self.server.listen()

    def send_file(self, file_path):
        """
        Envia um arquivo ao outro usuário.
        """
        if not os.path.exists(file_path):
            print("Arquivo não existe")
            return

        size = os.path.getsize(file_path)
        start_time = datetime.datetime.now()

        # Envia o tamanho do arquivo
        self.connection.sendall(size.to_bytes(8, "big"))

        print("Iniciando envio do arquivo")
        with open(file_path, "rb") as file:
            data = file.read(1000)
            last_sent = 0
            packet_index = 1
            while data:
                self.connection.send(data)

                sent = round(((1000 * packet_index) / size) * 100, 2)
                if int(sent) >= last_sent + 5:
                    print(f"Enviado {sent}%")
                    last_sent = sent

                data = file.read(1000)
                packet_index += 1
        print("Arquivo enviado")

        end_time = datetime.datetime.now()
        delta = end_time - start_time
        delta = max(delta.seconds, 1)

        for packet_size in [100, 500, 1000, 1500]:
            print(f"Relatório para um pacote de {packet_size} bytes")
            print(f"Tamanho do arquivo: {size} bytes")
            print(f"Número de pacotes: {ceil(size/packet_size)}")
            print(f"Velocidade de transmissão: {round((size * 8) / delta, 2)} Mb/s\n")
        self.stop()

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


app_address = input("Endereço: ")
app_port = int(input("Porta: "))
app_type = input("Iniciar servidor(S) ou cliente(C)?: ")

if app_port < 1000 or app_port > 65535:
    print("Porta deve estar entre 1000 e 65535 (inclusivo)")
    sys.exit(1)


app_client = Client()

if app_type.lower() == "c" or app_type.lower() == "cliente":
    path = input("Nome do arquivo a ser criado: ")
    app_type = ConnectionTypes.CLIENT
elif app_type.lower() == "s" or app_type.lower() == "servidor":
    path = input("Caminho do arquivo a ser enviado: ")
    app_type = ConnectionTypes.SERVER

app_client.run(app_type, app_address, app_port, path)
