import datetime
import socket
import os

from client import Client


class Sender(Client):
    """
    Classe responsável por enviar um arquivo para outro usuário através de um socket.
    """

    def __init__(self, file_path, packet_size):
        super().__init__(packet_size)
        # Arquivo a ser enviado caso seja um servidor ou a ser criado caso seja um cliente.
        if not os.path.exists(file_path):
            print(f"Arquivo {file_path} não existe!")
            return
        self.file_path = file_path

    def accept_connection(self):
        """
        Aceita a conexão de um outro usuário.
        """
        client, _ = self.connection.accept()
        if self.connection:
            self.connection.close()
        self.connection = client
        return client

    def handle_connection(self):
        """
        Envia um arquivo para outro usuário.
        Retorna verdadeiro caso a conexão deva ser finalizada
        """

        # Conecta-se ao novo usuário
        if not self.accept_connection():
            return True

        try:
            size = os.path.getsize(self.file_path)
            start_time = datetime.datetime.now()

            # Envia o tamanho do arquivo
            self.connection.sendall(size.to_bytes(8, "big"))

            # Envia o nome do arquivo
            file_name = os.path.basename(self.file_path)
            self.connection.sendall(file_name.encode("utf-8"))

            print(f"Enviando arquivo: {self.file_path} ({self.format_bytes(size)})")

            with open(self.file_path, "rb") as file:
                data = file.read(self.packet_size)
                progress = 0
                packet_index = 1
                while data:
                    self.connection.send(data)
                    # Porcentagem já enviada.
                    progress = self.print_already_sent_message(
                        (self.packet_size * packet_index), size, progress, "Enviado"
                    )
                    data = file.read(self.packet_size)
                    packet_index += 1
            print("Arquivo enviado")

            end_time = datetime.datetime.now()
            self.report(size, start_time, end_time)
        except InterruptedError:
            print("Erro! Fechando a conexão...")
            return False
        return True

    def start(self, address, port):
        """
        Inicia o servidor no endereço e porta especificados.
        """
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.bind((address, port))
        self.connection.listen()

    def run(self, address, port):
        """
        Executa o cliente até ctrl+c ser pressionado.
        """
        print("Esperando um cliente se conectar...")
        super().run(address, port)
