import logging
import socket
from abc import ABCMeta, abstractmethod
from enum import Enum
from random import randbytes
from time import sleep
from typing import Dict


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


class Results:
    """
    Armazena os resultados de um teste de velocidade de rede.
    """

    def __init__(self, transmitted_bytes: int, received_bytes: int) -> None:
        self.transmitted_bytes = transmitted_bytes
        self.received_bytes = received_bytes

    @staticmethod
    def format_bytes(size) -> str:
        """
        Transforma um número de bytes para uma representação textual.
        """
        index = 0
        values = {0: "b", 1: "Kb", 2: "Mb", 3: "Gb", 4: "Tb"}
        while size > 1024 and index < 4:
            size /= 1024
            index += 1
        return f"{round(size, 2)} {values[index]}"

    def report(self, packet_size: int, run_duration: int, header_size: int, role: Roles) -> None:
        """
        Apresenta um relatório sobre uma função executada pelo cliente.
        """
        lost_bytes = self.transmitted_bytes - self.received_bytes
        lost_packets = lost_bytes / packet_size

        packets_per_second = int(self.received_bytes / (run_duration * packet_size))
        transmitted_bits_per_second = (self.received_bytes * 8) / run_duration
        transmitted_bits_formated = self.format_bytes(transmitted_bits_per_second)

        print(f"{str(role.value).capitalize()}")
        print("Tamanho do header: {header_size} bytes")
        print(f"Tamanho do payload: {packet_size - header_size} bytes")
        print(f"Tempo de execução do teste: {run_duration}s")
        print(f"Total de bytes transmitidos: {self.transmitted_bytes:,}")
        print(f"Taxa de transmissão de pacotes: {packets_per_second:,}p/s")
        print(f"Pacotes perdidos: {lost_packets:,}")
        print(
            f"Taxa de perda de pacotes: {round((lost_packets / self.transmitted_bytes ) * 100, 2)}%"
        )
        print(f"Velocidade de {role.value}: {transmitted_bits_formated}/s")


class SpeedTest(metaclass=ABCMeta):
    """
    Gerência a conexão entre dois computadores, alternando entre as funções de SENDER e RECEIVER.
    Apresenta um relatório com as velocidades de download e upload através do método report().
    Os métodos receive_data() e send_data() devem ser implementados de acordo com o tipo de socket.
    """

    # Duração dos testes.
    RUN_DURATION = 20
    # Formato da barra de progresso.
    TQDM_FORMAT = "{n}s {bar}"
    # Tamanho da representação de um inteiro como bytes.
    INT_BYTE_SIZE = 8
    # Tamanho de cada pacote enviado entre usuários.
    PACKET_SIZE = 1024
    # Pacote indicando o fim da transmissão de dados.
    EMPTY_PACKET = b"\x00" * PACKET_SIZE

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
        self.data = randbytes(self.PACKET_SIZE)

    def __del__(self):
        """
        Fecha o socket ao destruir o objeto.
        """
        self.connection.close()

    def execute_role(self) -> Results:
        """
        Prepara o socket e executa a função atual do cliente.
        """
        logging.debug("Executando função %s", self.role.name)
        if self.role == Roles.RECEIVER:
            sleep(2)
            self.connection.connect(self.connect_address)
            results = self.receive_data()
            return results
        if self.role == Roles.SENDER:
            sleep(1)
            self.connection.bind(self.listen_address)
            results = self.send_data()
            return results
        return Results(0, 0)

    def run(self) -> None:
        """
        Salva os resultados encontrados ao executar as funções de RECEIVER e SENDER e apresenta os
        dados em um relatório.
        """
        print(f"Iniciando teste de conexão com socket {self.socket_type.name}...")
        # Salva os dados retornados ao executar a função atual do cliente.
        report_data = {
            Roles.RECEIVER: None,
            Roles.SENDER: None,
        }
        report_data[self.role] = self.execute_role()
        self.swap_roles()
        report_data[self.role] = self.execute_role()
        self.report_roles(report_data)

    def report_roles(
        self,
        results: Dict[Roles, Results],
    ) -> None:
        """
        Apresenta um relatório sobre as velocidades de download e upload entre duas máquinas.
        """
        print("-----------------------------------------------------------------\n")
        print(f"Resultados para o teste utilizando socket {self.socket_type.name}")
        for role, result in results.items():
            result.report(self.PACKET_SIZE, self.RUN_DURATION, self.INT_BYTE_SIZE, role)
            print()
        print("-----------------------------------------------------------------\n")

    def encode_stats_packet(self, value: int) -> bytes:
        """
        Cria um pacote de estatísticas, contendo bytes transmitidos e o número de pacotes
        perdidos.
        """
        return value.to_bytes(self.INT_BYTE_SIZE, "big", signed=False)

    def decode_stats_packet(self, stats_packet: bytes) -> int:
        """
        Decodifica um pacote de estatísticas, contendo bytes transmitidos e o número de pacotes
        perdidos.
        """
        return int.from_bytes(stats_packet, "big", signed=False)

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

    @abstractmethod
    def receive_data(self) -> Results:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """
        raise NotImplementedError("O método receive_data() deve ser implementado")

    @abstractmethod
    def send_data(self) -> Results:
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        raise NotImplementedError("O método send_data() deve ser implementado")
