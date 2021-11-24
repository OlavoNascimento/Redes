import abc
import select
import socket
from math import ceil


class Client:
    """
    Classe que lida com a conexão com um servidor e gerencia o envio e recebimento de mensagens.
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, packet_size):
        # Socket que envia o arquivo ao outro usuário.
        self.connection = None
        # Tamanho do pacote
        self.packet_size = packet_size

    @abc.abstractmethod
    def handle_connection(self):
        """
        Função que deve ser implementada para lidar com as conexões do cliente.
        """
        return

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
        return f"{size} {values[index]}"

    @staticmethod
    def print_already_sent_message(current_size, file_size, last_received, text):
        """
        Escreve uma mensagem de porcentagem de envio/recebimento de um arquivo.
        """
        if file_size == 0:
            return 100

        sent = current_size / file_size
        # Porcentagem já enviada.
        sent = min(round(sent * 100, 2), 100)
        if sent >= last_received + 5:
            print(f"{text} {sent}%")
            return sent
        return last_received

    def report(self, size, start_time, end_time):
        """
        Apresenta um relatório sobre a transmissão do arquivo.
        """
        delta = end_time - start_time
        delta = max(delta.seconds, 1)

        print(f"Relatório para um pacote de {self.packet_size} bytes")
        print(f"Tamanho do arquivo: {size} bytes")
        print(f"Número de pacotes: {ceil(size/self.packet_size)} pacotes")
        print(f"Velocidade de transmissão: {round((size * 8) / delta, 2)} b/s")

    def run(self, address, port):
        """
        Executa o cliente até ctrl+c ser pressionado.
        """
        try:
            self.start(address, port)

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
        finally:
            self.stop()

    def start(self, address, port):
        """
        Conecta-se ao servidor no endereço e porta especificados.
        """
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((address, port))

    def stop(self):
        """
        Finaliza a conexão com o servidor.
        """
        if self.connection is not None:
            self.connection.close()
            self.connection = None

