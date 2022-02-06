#!/usr/bin/env python3

"""
Programa que calcula as velocidades de download e upload entre dois computadores.
"""

import logging
import sys

from generic_speedtest import Roles
from udp_speedtest import UDPSpeedTest
from tcp_speedtest import TCPSpeedTest


def main():
    FORMAT = (
        "%(levelname)s - [%(filename)s:%(lineno)s - %(funcName)s()] - %(asctime)s - %(message)s"
    )
    # Habilita mensagens de debug
    # logging.basicConfig(level=logging.DEBUG, format=FORMAT)

    listen_address = input("Seu endereço: ")
    connect_address = input("Endereço do outro usuário: ")
    port = int(input("Porta: "))
    client_type = input("Enviar(E) ou receber(R)?: ")

    if port < 1000 or port > 65535:
        print("Porta deve estar entre 1000 e 65535 (inclusivo)!")
        sys.exit(1)

    if client_type.lower() == "e" or client_type.lower() == "enviar":
        starting_role = Roles.SENDER
    elif client_type.lower() == "r" or client_type.lower() == "receber":
        starting_role = Roles.RECEIVER
    else:
        print("Opção inválida!")
        sys.exit(1)

    tcp_tester = TCPSpeedTest(listen_address, connect_address, port, starting_role)
    tcp_tester.run()
    udp_tester = UDPSpeedTest(listen_address, connect_address, port, starting_role)
    udp_tester.run()


if __name__ == "__main__":
    main()
