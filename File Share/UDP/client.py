import abc
import hashlib
import select
import socket
from datetime import datetime
from math import ceil


class Client:
    """
    Classe que lida com a conexão com um outro usuário e gerencia o envio e recebimento de
    mensagens.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, packet_size: int):
        # Tamanho de cada pacote enviado.
        self.packet_size = packet_size
        # Socket que envia o arquivo ao outro usuário.
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Socket espera 1 segundo para reenviar um pacote.
        self.connection.settimeout(1)

    def __del__(self):
        """
        Fecha o socket ao destruir o objeto.
        """
        self.connection.close()

    @abc.abstractmethod
    def handle_connection(self):
        """
        Função que deve ser implementada para lidar com as conexões do cliente.
        """
        raise NotImplementedError("O método handle_connection deve ser implementado")

    @abc.abstractmethod
    def prepare_socket(self, address: str, port: int):
        """
        Função que deve ser implementada para preparar o socket para ser utilizado pelo programa.
        """
        raise NotImplementedError("O método prepare_socket deve ser implementado")

    @staticmethod
    def checksum(data: bytes):
        """
        Gera um checksum de um pacote de bytes.
        """
        checksum = hashlib.md5()
        checksum.update(data)
        return checksum.hexdigest()

    @staticmethod
    def format_bytes(size):
        """
        Transforma um número de bytes para uma representação textual.
        """
        index = 0
        values = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
        while size > 1024 and index < 4:
            size /= 1024
            index += 1
        return f"{round(size, 2)} {values[index]}"

    @staticmethod
    def print_progress_message(
        current_size: float, file_size: float, last_received: float, text: str
    ):
        """
        Escreve uma mensagem de porcentagem de envio/recebimento de um arquivo.
        """
        if file_size == 0:
            return 100

        sent = current_size / file_size
        # Porcentagem já enviada.
        sent = min(round(sent * 100), 100)
        if sent >= last_received + 5:
            print(f"{text} {sent}%")
            return sent
        return last_received

    def report(self, size: float, failed_packages: int, start_time: datetime, end_time: datetime):
        """
        Apresenta um relatório sobre a transmissão do arquivo.
        """
        delta = end_time - start_time
        delta = max(delta.seconds, 1)

        print(f"Relatório para um pacote de {self.packet_size} bytes")
        print(f"Tamanho do arquivo: {self.format_bytes(size)} ({size} bytes)")
        print(f"Número de pacotes: {ceil(size/self.packet_size)} pacotes")
        print(f"Velocidade de transmissão: {round((size * 8) / delta, 2)} b/s")
        print(f"Número de pacotes retransmitidos: {failed_packages}")

    def run(self, address: str, port: int):
        """
        Executa o cliente até ctrl+c ser pressionado ou a transferência do arquivo ser finalizada.
        """
        try:
            self.prepare_socket(address, port)
            running = True
            while running:
                # Verifica se o socket tem algum dado a ser lido.
                read_sockets, _, _ = select.select(
                    [self.connection],
                    [],
                    [],
                )
                for _ in read_sockets:
                    running = not self.handle_connection()
        except KeyboardInterrupt:
            pass
