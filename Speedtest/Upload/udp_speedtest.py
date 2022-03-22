import logging
from datetime import datetime, timedelta
from socket import timeout

from tqdm import tqdm

from generic_speedtest import Results, SpeedTest, Roles, SocketType


class UDPSpeedTest(SpeedTest):
    """
    Classe responsável por transmitir dados utilizando sockets UDP e calcular as velocidades de
    download e upload entre dois computadores.
    """

    # Pacote utilizado para confirmar que o outro usuário recebeu um pacote.
    CONFIRMATION_PACKET = b"\x01"

    def __init__(
        self,
        listen_address: str,
        connect_address: str,
        port: int,
        starting_role: Roles,
    ):
        super().__init__(
            listen_address,
            connect_address,
            port,
            starting_role,
            SocketType.UDP,
        )

    def receive_data(self) -> Results:
        """
        Recebe dados enviados por outro usuário, armazenando o número de bytes recebidos, ao final
        da transmissão envia o total recebido para o outro usuário.
        """
        self.connection.settimeout(1)

        waiting_message_presented = False
        packets_lost = 0
        current_packet = 0
        pbar = None
        received_data_size = 0

        next_tick = datetime.now() + timedelta(seconds=1)
        while True:
            try:
                packet = self.recvall(self.connection, self.PACKET_SIZE)
                # Um pacote vazio indica o fim da transmissão de dados.
                if packet == self.EMPTY_PACKET:
                    break

                if received_data_size == 0:
                    print("Testando velocidade de download...")
                    pbar = tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT)

                position, _ = self.decode_data_packet(packet)
                logging.debug(
                    "posição: %d, %d bytes recebidos, tamanho atual: %d",
                    position,
                    len(packet),
                    received_data_size,
                )

                received_data_size += len(packet)

                if position != current_packet:
                    packets_lost += abs(current_packet - position)
                    logging.debug(
                        "posição: %d, atual: %d, %d pacotes foram perdidos",
                        position,
                        current_packet,
                        abs(current_packet - position),
                    )
                    current_packet = position + 1
                else:
                    current_packet += 1

                current_time = datetime.now()
                # Atualiza a barra de progresso.
                if current_time >= next_tick:
                    pbar.update(1)
                    pbar.refresh()
                    next_tick = current_time + timedelta(seconds=1)
            except timeout:
                # Indica que está pronto para receber dados.
                self.connection.send(self.EMPTY_PACKET)
            except ConnectionRefusedError:
                # Outro usuário ainda não se conectou.
                if not waiting_message_presented:
                    print("Esperando o outro usuário estabelecer uma conexão...")
                    waiting_message_presented = True
        logging.debug("Fim do recebimento de dados")

        # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
        # execução.
        pbar.n = self.RUN_DURATION
        pbar.refresh()
        pbar.close()

        # Envia o total salvo para o outro usuário.
        while True:
            try:
                stats_packet = self.encode_stats_packet(received_data_size, packets_lost)
                self.connection.send(stats_packet)
                status = self.connection.recv(self.DATA_SIZE)
                if status == self.CONFIRMATION_PACKET:
                    break
            except timeout:
                pass
            except ConnectionRefusedError:
                break

        return Results(received_data_size, packets_lost)

    def send_data(self) -> Results:
        """
        Envia dados para outro usuário, ao final da transmissão recebe o total de bytes recebidos
        pelo o outro usuário.
        """
        # Uma mensagem vazia indica que o outro usuário está pronto para receber os dados.
        print("Esperando o outro usuário estabelecer uma conexão...")
        _, address = self.connection.recvfrom(self.DATA_SIZE)
        print("Testando velocidade de upload...")

        end_time = datetime.now() + timedelta(seconds=self.RUN_DURATION)
        next_tick = datetime.now() + timedelta(seconds=1)
        current_packet = 0

        logging.debug("Iniciando envio de dados")
        with tqdm(total=self.RUN_DURATION, bar_format=self.TQDM_FORMAT) as pbar:
            while (current_time := datetime.now()) < end_time:
                packet = self.encode_data_packet(current_packet)
                self.connection.sendto(packet, address)
                logging.debug("Enviando pacote: %d", current_packet)
                current_packet += 1
                # Atualiza a barra de progresso.
                if current_time >= next_tick:
                    next_tick = current_time + timedelta(seconds=1)
                    pbar.update(1)
                    pbar.refresh()

            # Garante que o tempo de execução da barra de progresso esteja correto ao fim da
            # execução.
            pbar.n = self.RUN_DURATION
            pbar.refresh()
        logging.debug("Fim do envio de dados")

        self.connection.settimeout(1)
        bytes_transmitted = 0
        lost_packets = 0
        # Recebe o total de bytes recebidos pelo o outro usuário.
        while bytes_transmitted == 0:
            try:
                self.connection.sendto(self.EMPTY_PACKET, address)
                stats_packet = self.recvall(self.connection, self.INT_BYTE_SIZE * 2)

                if len(stats_packet) == self.INT_BYTE_SIZE * 2:
                    bytes_transmitted, lost_packets = self.decode_stats_packet(stats_packet)
                    self.connection.sendto(self.CONFIRMATION_PACKET, address)
            except timeout:
                pass
        self.connection.settimeout(0)
        logging.debug("%d bytes foram recebidos pelo o outro usuário", bytes_transmitted)

        return Results(bytes_transmitted, lost_packets)
