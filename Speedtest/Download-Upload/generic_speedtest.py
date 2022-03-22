import socket
import logging
from abc import ABCMeta, abstractmethod
from enum import Enum
from random import randbytes
from time import sleep
from typing import Tuple, Dict


class SocketType(Enum):
    """
    Tipos de sockets que um SpeedTest pode utilizar.
    """

    TCP = socket.SOCK_STREAM
    UDP = socket.SOCK_DGRAM


class Roles(Enum):
    """
    Funções que podem ser executadas por um SpeedTest.
    """

    SENDER = "upload"
    RECEIVER = "download"


class SpeedTest(metaclass=ABCMeta):
    """
    Gerência a conexão entre dois computadores, alternando entre as funções de SENDER e RECEIVER.
    Apresenta um relatório com as velocidades de download e upload através do método report().
    Os métodos receive_data() e send_data() devem ser implementados de acordo com o tipo de socket.
    """

    # Tamanho da representação de um inteiro como bytes.
    INT_BYTE_SIZE = 8
    # Tamanho dos dados presentes em um pacote.
    DATA_SIZE = 1024
    # Tamanho de cada pacote enviado entre usuários.
    PACKET_SIZE = INT_BYTE_SIZE + DATA_SIZE
    # Duração dos testes.
    RUN_DURATION = 20
    # Pacote indicando o fim da transmissão de dados.
    EMPTY_PACKET = b"\x00" * PACKET_SIZE
    # Formato da barra de progresso.
    TQDM_FORMAT = "{n}s {bar}"

    def __init__(
        self,
        listen_address: str,
        connect_address: str,
        port: int,
        starting_role: Roles,
        socket_type: SocketType,
    ):
        self.connection = socket.socket(socket.AF_INET, socket_type.value)
        # Endereço para esperar a conexão do outro usuário.
        self.listen_address = (listen_address, port)
        # Endereço para se conectar ao outro usuário.
        self.connect_address = (connect_address, port)
        # Tipo de socket.
        self.socket_type = socket_type
        # Função atual do cliente.
        self.role = starting_role
        # Dados enviados entre os usuários.
        self.data = randbytes(self.DATA_SIZE)

    def __del__(self):
        """
        Fecha o socket ao destruir o objeto.
        """
        self.connection.close()

    def execute_role(self) -> Tuple[int, int]:
        """
        Prepara o socket e executa a função atual do cliente.
        """
        logging.debug("Executando função %s", self.role.name)
        data_transmitted = (0, 0)
        if self.role == Roles.RECEIVER:
            sleep(2)
            self.connection.connect(self.connect_address)
            data_transmitted = self.receive_data()
        elif self.role == Roles.SENDER:
            sleep(1)
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
            Roles.RECEIVER: (0, 0),
            Roles.SENDER: (0, 0),
        }
        report_data[self.role] = self.execute_role()
        self.swap_roles()
        report_data[self.role] = self.execute_role()
        self.report(report_data)

    def encode_data_packet(self, position: int) -> bytes:
        """
        Cria um pacote para ser enviado ao outro usuário, contendo o número do pacote e dados.
        """
        return position.to_bytes(self.INT_BYTE_SIZE, "big", signed=False) + self.data

    def decode_data_packet(self, packet: bytes) -> Tuple[int, bytes]:
        """
        Decodifica um pacote para ser enviado ao outro usuário, contendo o número do pacote e dados.
        """
        position = int.from_bytes(packet[0 : self.INT_BYTE_SIZE], "big", signed=False)
        data = packet[self.INT_BYTE_SIZE :]
        return position, data

    def encode_stats_packet(self, received_data_size: int, packets_lost: int) -> bytes:
        """
        Cria um pacote de estatísticas, contendo bytes transmitidos e o número de pacotes
        perdidos.
        """
        bytes_transmitted = received_data_size.to_bytes(self.INT_BYTE_SIZE, "big", signed=False)
        packets_lost = packets_lost.to_bytes(self.INT_BYTE_SIZE, "big", signed=False)
        return bytes_transmitted + packets_lost

    def decode_stats_packet(self, stats_packet: bytes) -> Tuple[int, bytes]:
        """
        Decodifica um pacote de estatísticas, contendo bytes transmitidos e o número de pacotes
        perdidos.
        """
        bytes_transmitted = int.from_bytes(
            stats_packet[0 : self.INT_BYTE_SIZE], "big", signed=False
        )
        packets_lost = int.from_bytes(stats_packet[self.INT_BYTE_SIZE :], "big", signed=False)
        return bytes_transmitted, packets_lost

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

    @staticmethod
    def format_bytes(size) -> int:
        """
        Transforma um número de bytes para uma representação textual.
        """
        index = 0
        values = {0: "b", 1: "Kb", 2: "Mb", 3: "Gb", 4: "Tb"}
        while size > 1024 and index < 4:
            size /= 1024
            index += 1
        return f"{round(size, 2)} {values[index]}"

    def report(self, report_data: Dict[Roles, Tuple[int, int]]) -> None:
        """
        Apresenta um relatório sobre as velocidades de download e upload entre duas máquinas.
        """
        print("-----------------------------------------------------------------\n")
        print(f"Resultados para o teste utilizando socket {self.socket_type.name}")
        for role, (transmitted, lost) in report_data.items():
            self.report_role(role, transmitted, lost)
            print()
        print("-----------------------------------------------------------------\n")

    def report_role(self, role: Roles, transmitted_bytes: int, lost_packets: int) -> None:
        """
        Apresenta um relatório sobre uma função executada pelo cliente.
        """
        packets_per_second = int(transmitted_bytes / (self.RUN_DURATION * self.PACKET_SIZE))
        transmitted_bits_per_second = (transmitted_bytes * 8) / self.RUN_DURATION
        transmitted_bits_formated = self.format_bytes(transmitted_bits_per_second)

        print(f"{str(role.value).capitalize()}")
        print(f"Tamanho do header: {self.INT_BYTE_SIZE} bytes")
        print(f"Tamanho do payload: {self.DATA_SIZE} bytes")
        print(f"Tempo de execução do teste: {self.RUN_DURATION}s")
        print(f"Total de bytes transmitidos: {transmitted_bytes:,}")
        print(f"Taxa de transmissão de pacotes: {packets_per_second:,}p/s")
        print(f"Pacotes perdidos: {lost_packets:,}")
        print(f"Taxa de perda de pacotes: {round((lost_packets / transmitted_bytes ) * 100, 2)}%")
        print(f"Velocidade de {role.value}: {transmitted_bits_formated}/s")

    @abstractmethod
    def receive_data(self) -> Tuple[int]:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """
        raise NotImplementedError("O método receive_data() deve ser implementado")

    @abstractmethod
    def send_data(self) -> Tuple[int]:
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        raise NotImplementedError("O método send_data() deve ser implementado")