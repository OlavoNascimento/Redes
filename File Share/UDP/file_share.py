#!/usr/bin/python3

"""
Programa que envia um arquivo para outro usuário utilizando uma conexão UDP.
"""

import sys
import logging

from receiver import Receiver
from sender import Sender


def main():
    # Habilita mensagens de debug
    # logging.basicConfig(level=logging.DEBUG)

    app_address = input("Endereço: ")
    app_port = int(input("Porta: "))
    pack_size = int(input("Tamanho do pacote: "))
    app_type = input("Enviar(E) ou receber(R)?: ")

    if app_port < 1000 or app_port > 65535:
        print("Porta deve estar entre 1000 e 65535 (inclusivo)!")
        sys.exit(1)

    if app_type.lower() == "e" or app_type.lower() == "enviar":
        if len(sys.argv) <= 1:
            print("Forneça o caminho do arquivo a ser enviado como um argumento para o programa!")
            sys.exit(1)
        path = sys.argv[1]
        window_size = int(input("Tamanho da janela: "))
        app_client = Sender(path, pack_size, window_size)
    elif app_type.lower() == "r" or app_type.lower() == "receber":
        app_client = Receiver(pack_size)
    else:
        print("Opção inválida!")
        sys.exit(1)

    app_client.run(app_address, app_port)


if __name__ == "__main__":
    main()
