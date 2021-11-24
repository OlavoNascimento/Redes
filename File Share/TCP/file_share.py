#!/usr/bin/python3

"""
Programa que envia um arquivo para outro usuário utilizando uma conexão TCP.
"""

import sys

from receiver import Receiver
from sender import Sender

app_address = input("Endereço: ")
app_port = int(input("Porta: "))
app_type = input("Enviar(E) ou receber(R)?: ")
pack_size = int(input("Tamanho do pacote: "))

if app_port < 1000 or app_port > 65535:
    print("Porta deve estar entre 1000 e 65535 (inclusivo)!")
    sys.exit(1)

if app_type.lower() == "e" or app_type.lower() == "enviar":
    if len(sys.argv) <= 1:
        print("Forneça o caminho do arquivo a ser enviado para o programa!")
        sys.exit(1)
    path = sys.argv[1]
    app_client = Sender(path, pack_size)
elif app_type.lower() == "r" or app_type.lower() == "receber":
    app_client = Receiver(pack_size)
else:
    print("Opção inválida!")
    sys.exit(1)

app_client.run(app_address, app_port)
