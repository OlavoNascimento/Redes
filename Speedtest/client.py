import socket
import logging
from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from random import randbytes


class SocketType(Enum):
    """
    Tipos de sockets que um Client pode utilizar.
    """

    TCP = socket.SOCK_STREAM
    UDP = socket.SOCK_DGRAM


class Roles(Enum):
    """
    Funções que podem ser executadas por um Client.
    """

    SENDER = auto()
    RECEIVER = auto()


class Client(metaclass=ABCMeta):
    """
    Gerência a conexão entre dois computadores, alternando entre as funções de SENDER e RECEIVER.
    Apresenta um relatório com as velocidades de download e upload através do método report().
    Os métodos receive_data() e send_data() devem ser implementados de acordo com o tipo de socket.
    """

    # Tamanho de cada pacote enviado entre usuários.
    PACKET_SIZE = 1024
    # Tempo em segundos em que o programa transmite dados entre os usuários.
    RUN_DURATION = 20
    # Pacote indicando o fim da transmissão de dados.
    EMPTY_PACKET = b"\x00"
    # Formato da barra de progresso.
    TQDM_FORMAT = "{n}s {bar}"

    def __init__(
        self,
        connect_address: str,
        port: int,
        starting_role: Roles,
        socket_type: SocketType,
    ):
        self.connection = socket.socket(socket.AF_INET, socket_type.value)
        address = socket.gethostbyname(socket.gethostname())
        # Endereço para esperar a conexão do outro usuário.
        self.listen_address = (address, port)
        # Endereço para se conectar ao outro usuário.
        self.connect_address = (connect_address, port)
        # Tipo de socket.
        self.socket_type = socket_type
        # Função atual do cliente.
        self.role = starting_role
        # Dados enviados entre os usuários.
        self.data = randbytes(self.PACKET_SIZE)

    def __del__(self):
        """
        Fecha o socket ao destruir o objeto.
        """
        self.connection.close()

    def execute_role(self) -> int:
        """
        Prepara o socket e executa a função atual do cliente.
        """
        logging.debug("Executando função %s", self.role.name)
        data_transmitted = 0
        if self.role == Roles.RECEIVER:
            self.connection.connect(self.connect_address)
            data_transmitted = self.receive_data()
        elif self.role == Roles.SENDER:
            self.connection.bind(self.listen_address)
            data_transmitted = self.send_data()
        return data_transmitted

    def run(self) -> None:
        """
        Salva os resultados encontrados ao executar as funções de RECEIVER e SENDER e apresenta os
        dados em um relatório.
        """
        print(f"Iniciando teste de conexão com socket {self.socket_type.name}...")
        # Salva os dados retornados ao executar a função atual do cliente.
        report_data = {
            Roles.RECEIVER: 0,
            Roles.SENDER: 0,
        }
        report_data[self.role] = self.execute_role()
        self.swap_roles()
        report_data[self.role] = self.execute_role()
        self.report(report_data[Roles.SENDER], report_data[Roles.RECEIVER])

    def swap_roles(self) -> None:
        """
        Troca a função atual do cliente pela função oposta, para isso é necessário criar um novo
        socket.
        """
        logging.debug("Alterando função")
        if self.role == Roles.RECEIVER:
            self.role = Roles.SENDER
        elif self.role == Roles.SENDER:
            self.role = Roles.RECEIVER
        self.connection.close()
        self.connection = socket.socket(socket.AF_INET, self.socket_type.value)

    def get_connection_speed(self, bytes_transmitted: int) -> int:
        """
        Calcula a velocidade da conexão em MB/s utilizando o número de bytes transmitidos em um
        período de tempo.
        """
        # Quantos bytes recebe em média a cada 1 segundo.
        bytes_transmitted /= self.RUN_DURATION
        return self.format_bytes(bytes_transmitted)

    @staticmethod
    def format_bytes(size) -> int:
        """
        Transforma um número de bytes para uma representação textual.
        """
        index = 0
        values = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
        while size > 1024 and index < 4:
            size /= 1024
            index += 1
        return f"{round(size, 2)} {values[index]}"

    def report(self, download_speed: int, upload_speed: int) -> None:
        """
        Apresenta um relatório sobre as velocidades de download e upload entre duas máquinas.
        """
        print(f"Resultados para o teste utilizando socket {self.socket_type.name}")
        print(f"Tempo de execução do teste: {self.RUN_DURATION}s")
        print(f"Velocidade de download: {self.get_connection_speed(download_speed)}/s")
        print(f"Velocidade de upload: {self.get_connection_speed(upload_speed)}/s")

    @abstractmethod
    def receive_data(self) -> int:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """
        raise NotImplementedError("O método receive_data() deve ser implementado")

    @abstractmethod
    def send_data(self) -> int:
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        raise NotImplementedError("O método send_data() deve ser implementado")
